from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from .schemas import Idea, Rule, Verdict


PROMPT_TEMPLATE = (
    "You are a rigorous startup idea evaluator. Use the provided redline rules as the primary logic. "
    "Return only a strict JSON object with keys: decision (deny|caution|go), conf_level (0-1), "
    "reasons (array of short strings), redlines (array of rule ids), next_steps (array).\n\n"
    "Idea:\n{idea_json}\n\nRedlines (id [severity:decision] - condition - rationale):\n{rubric}\n\n"
    "Output JSON schema:\n{\n  \"decision\": \"deny|caution|go\",\n  \"conf_level\": 0.0,\n  \"reasons\": [\"...\"],\n  \"redlines\": [\"RL-001\"],\n  \"next_steps\": [\"...\"]\n}"
)


def _rubric(rules: List[Rule]) -> str:
    lines = []
    for r in rules:
        lines.append(
            " - ".join(
                [
                    f"{r.id} [{r.severity}:{r.decision}]",
                    r.condition,
                    f"rationale: {r.rationale}",
                ]
            )
        )
    return "\n".join(lines)


async def _agent_query_async(prompt: str, system_prompt: str | None = None, max_turns: int = 1) -> str:
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock  # type: ignore
    except Exception as e:
        raise RuntimeError("claude-agent-sdk is not installed. Add it to requirements and pip install.") from e

    opts = ClaudeAgentOptions(system_prompt=system_prompt or "", max_turns=max_turns)
    text_chunks: List[str] = []
    async for message in query(prompt=prompt, options=opts):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_chunks.append(block.text)
    return "\n".join(text_chunks)


def evaluate_with_claude_agent(idea: Idea, rules: List[Rule]) -> Verdict:
    idea_d: Dict[str, Any] = {
        "intent": idea.intent,
        "user": idea.user,
        "scenario": idea.scenario,
        "triggers": idea.triggers,
        "alts": idea.alts,
        "assumptions": list(idea.assumptions or []),
        "risks": list(idea.risks or []),
    }
    prompt = PROMPT_TEMPLATE.format(
        idea_json=json.dumps(idea_d, ensure_ascii=False, indent=2),
        rubric=_rubric(rules),
    )
    raw = asyncio.run(_agent_query_async(prompt))
    text = raw.strip()
    if text.startswith("```"):
        # best-effort strip code fence
        try:
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        except Exception:
            pass
    try:
        data = json.loads(text)
    except Exception:
        data = {
            "decision": "caution",
            "conf_level": 0.5,
            "reasons": ["Claude Agent response parsing fallback"],
            "redlines": [],
            "next_steps": [],
        }

    decision = str(data.get("decision", "caution")).lower()
    if decision not in {"deny", "caution", "go"}:
        decision = "caution"
    conf = float(data.get("conf_level", 0.6) or 0.6)
    reasons = [str(x) for x in (data.get("reasons") or [])]
    redlines = [str(x) for x in (data.get("redlines") or [])]
    next_steps = [str(x) for x in (data.get("next_steps") or [])]
    return Verdict(decision=decision, reasons=reasons, conf_level=conf, redlines=redlines, next_steps=next_steps)
