from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

# Load environment variables from a local .env if present
load_dotenv()


class LLMConfig:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.provider = cfg.get("provider", "openai")
        self.model = cfg.get("model", "gpt-4o-mini")
        self.api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
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

        # Prefer generic envs from .env: LLM_API_KEY and LLM_API_URL
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get(cfg.api_key_env)
        base_url = os.environ.get("LLM_API_URL")
        if not api_key:
            raise RuntimeError(f"Missing API key env: {cfg.api_key_env}")

        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
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
                if attempt >= self._cfg.retries:
                    raise
                time.sleep(0.5 * (attempt + 1))
        return "{}"


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
