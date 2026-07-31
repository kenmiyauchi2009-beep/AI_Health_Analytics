from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PredictionRequest:
    """User-selected symptoms to send to the disease model."""

    selected_symptoms: list[str]
