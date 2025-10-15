from __future__ import annotations

from typing import List, Optional, Literal

try:
    from pydantic import BaseModel, Field
except Exception:  # minimal fallback if pydantic is unavailable
    from dataclasses import dataclass, field

    class BaseModel:  # type: ignore
        pass

    def Field(default=None, **_):  # type: ignore
        return default

    def dataclass_model(cls):
        return dataclass(cls)


class Rule(BaseModel):
    id: str
    scope: str = Field(default="core")
    condition: str  # human-readable expression
    severity: Literal["critical", "high", "medium", "low"] = "high"
    rationale: str
    sources: List[str] = []
    owner: Optional[str] = None
    version: Optional[str] = None
    sunset: Optional[str] = None
    # Optional helpers for MVP evaluation
    decision: Optional[Literal["deny", "caution", "continue"]] = None
    keywords: Optional[List[str]] = None
    category: Optional[str] = None
    next_steps: Optional[List[str]] = None


class Idea(BaseModel):
    intent: str
    user: str
    scenario: str
    triggers: str
    alts: str
    assumptions: List[str] = []
    risks: List[str] = []


class Evidence(BaseModel):
    type: Literal["primary", "secondary", "tertiary"]
    provenance: str
    weight: float = 1.0
    sample_size: Optional[int] = None
    excerpts: List[str] = []
    timestamp: Optional[str] = None


class Verdict(BaseModel):
    decision: Literal["deny", "caution", "go"]
    reasons: List[str] = []
    conf_level: float = 0.5
    redlines: List[str] = []
    next_steps: List[str] = []
