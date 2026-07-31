from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, BinaryIO

import joblib

from prediction.symptoms import Symptoms


class ModelLoader:
    """Loads model and symptom assets from pickle/joblib files."""

    def load_model(self, source: str | Path | BinaryIO) -> Any:
        try:
            if hasattr(source, "read"):
                return joblib.load(source)
            return joblib.load(source)
        except Exception as error:
            raise ValueError(f"Could not load model file: {error}") from error

    def load_symptoms(self, source: str | Path | BinaryIO) -> Symptoms:
        try:
            return Symptoms.from_pickle(source)
        except Exception as error:
            raise ValueError(f"Could not load symptoms file: {error}") from error

    def load_metadata(self, source: str | Path | BinaryIO) -> dict:
        try:
            if hasattr(source, "read"):
                loaded = pickle.load(source)
            else:
                with open(source, "rb") as handle:
                    loaded = pickle.load(handle)
        except Exception as error:
            raise ValueError(f"Could not load metadata file: {error}") from error

        if not isinstance(loaded, dict):
            raise ValueError("model_metadata.pkl must contain a dictionary.")
        return loaded
