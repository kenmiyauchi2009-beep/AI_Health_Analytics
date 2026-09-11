from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIResponse:
    answer: str
    refused: bool = False
    refusal_reason: str | None = None
    suggested_questions: list[str] = field(default_factory=list)
