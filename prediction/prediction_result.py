from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiseaseProbability:
    disease: str
    probability: float


@dataclass(frozen=True)
class PredictionResult:
    """Prediction output for UI display."""

    top_disease: str
    top_probability: float
    ranked: list[DiseaseProbability]
    is_low_confidence: bool
