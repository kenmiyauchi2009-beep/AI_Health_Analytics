from __future__ import annotations

import pickle
from pathlib import Path
from typing import BinaryIO


class Symptoms:
    """Expandable symptom feature names loaded from a pickle file."""

    def __init__(self, names: list[str]) -> None:
        if not names:
            raise ValueError("Symptom list cannot be empty.")
        self.names = list(names)

    @classmethod
    def from_pickle(cls, source: str | Path | BinaryIO) -> Symptoms:
        if hasattr(source, "read"):
            loaded = pickle.load(source)
        else:
            with open(source, "rb") as handle:
                loaded = pickle.load(handle)

        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise ValueError("symptoms.pkl must contain a list of symptom name strings.")

        return cls(loaded)

    def to_feature_vector(self, selected_symptoms: list[str]) -> list[float]:
        """Convert selected symptom names into a model-ready binary feature vector."""
        selected = set(selected_symptoms)
        return [1.0 if name in selected else 0.0 for name in self.names]
