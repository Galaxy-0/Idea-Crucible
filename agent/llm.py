from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import yaml


class LLMConfig:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.provider = cfg.get("provider", "openai")
        self.model = cfg.get("model", "gpt-4o-mini")
        # Prefer explicit key and base_url from model.yaml
        self.api_key = cfg.get("api_key")
        self.base_url = cfg.get("base_url")
        self.headers: Dict[str, str] = cfg.get("headers") or {}
        # Backward-compat fallback: env name
        self.api_key_env = cfg.get("api_key_env")
        self.temperature = float(cfg.get("temperature", 0.2))
        self.max_tokens = int(cfg.get("max_tokens", 800))
        self.timeout_s = int(cfg.get("timeout_s", 30))
        self.retries = int(cfg.get("retries", 2))
        self.language = cfg.get("language", "auto")


def load_model_config(path: str) -> LLMConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return LLMConfig(data)


class OpenAIClient:
    def __init__(self, cfg: LLMConfig) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError("openai package not installed. Add it to requirements and pip install.") from e

        # Source credentials and base URL from model.yaml
        api_key = cfg.api_key
        if not api_key and cfg.api_key_env:
            api_key = os.environ.get(cfg.api_key_env)
        if not api_key:
            raise RuntimeError("Missing API key. Set `api_key` in config/model.yaml (preferred), or define `api_key_env` and export it in your shell.")

        # Build client with explicit Authorization header (for OpenRouter compatibility)
        headers: Dict[str, str] = {}
        if cfg.headers:
            headers.update(cfg.headers)
        headers.setdefault("Authorization", f"Bearer {api_key}")

        kwargs: Dict[str, Any] = {"api_key": api_key, "default_headers": headers}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        self._client = OpenAI(**kwargs)
        self._cfg = cfg

    def complete_json(self, system: str, user: str) -> str:
        # Use JSON response format when available
        for attempt in range(self._cfg.retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._cfg.model,
                    temperature=self._cfg.temperature,
                    max_tokens=self._cfg.max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or "{}"
            except Exception as e:
                # On auth or 4xx errors, try raw HTTPX fallback once
                if attempt == self._cfg.retries:
                    try:
                        return self._complete_json_httpx(system, user)
                    except Exception:
                        raise
                time.sleep(0.5 * (attempt + 1))
        return "{}"

    def _complete_json_httpx(self, system: str, user: str) -> str:
        import httpx
        url = (self._cfg.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self._cfg.api_key}", "Content-Type": "application/json"}
        headers.update(getattr(self._cfg, "headers", {}) or {})
        payload = {
            "model": self._cfg.model,
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self._cfg.timeout_s) as client:
            r = client.post(url, headers=headers, json=payload)
            if r.status_code >= 400:
                # Surface server error for easier debugging
                raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text}")
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return content or "{}"


def get_client(cfg: LLMConfig):
    if cfg.provider == "openai":
        return OpenAIClient(cfg)
    raise NotImplementedError(f"Unsupported provider: {cfg.provider}")


def build_rubric(rules: List[Dict[str, Any]]) -> str:
    lines = []
    for r in rules:
        lines.append(
            " - ".join(
                [
                    f"{r.get('id','')} [{r.get('severity','')}:{r.get('decision','')}]",
                    r.get("condition", ""),
                    f"rationale: {r.get('rationale','')}",
                ]
            )
        )
    return "\n".join(lines)


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if "```" in t:
            t = t.rsplit("```", 1)[0]
    return t.strip()


def llm_verdict_json(idea: Dict[str, Any], rules: List[Dict[str, Any]], cfg: LLMConfig) -> Dict[str, Any]:
    client = get_client(cfg)

    system = (
        "You are a rigorous startup idea evaluator. Use the provided redline rules as the primary logic. "
        "Return only a strict JSON object with keys: decision (deny|caution|go), conf_level (0-1), "
        "reasons (array of short strings), redlines (array of rule ids), next_steps (array)."
    )

    rubric = build_rubric(rules)
    language_hint = cfg.language
    user = (
        f"Language: {language_hint}.\n"
        "Evaluate this Idea against Redlines. Be conservative.\n\n"
        f"Idea:\n{json.dumps(idea, ensure_ascii=False, indent=2)}\n\n"
        f"Redlines:\n{rubric}\n\n"
        "Output JSON schema:\n"
        "{\n  \"decision\": \"deny|caution|go\",\n  \"conf_level\": 0.0,\n  \"reasons\": [\"...\"],\n  \"redlines\": [\"RL-001\"],\n  \"next_steps\": [\"...\"]\n}"
    )

    raw = client.complete_json(system, user)
    raw = strip_code_fences(raw)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Non-object JSON from LLM")
        return data
    except Exception as e:
        # Fallback minimal object
        return {
            "decision": "caution",
            "conf_level": 0.5,
            "reasons": ["LLM parsing fallback"],
            "redlines": [],
            "next_steps": [],
        }
