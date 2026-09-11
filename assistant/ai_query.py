from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIQuery:
    """A natural-language question from the user."""

    text: str
