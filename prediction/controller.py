from __future__ import annotations

from typing import Any

import pandas as pd

from prediction.prediction_request import PredictionRequest
from prediction.prediction_result import DiseaseProbability, PredictionResult
from prediction.symptoms import Symptoms


class DiseasePredictionController:
    """Business logic for converting symptoms into disease predictions."""

    CONFIDENCE_THRESHOLD = 0.50
    TOP_N = 3

    def __init__(self, model: Any, symptoms: Symptoms) -> None:
        self.model = model
        self.symptoms = symptoms

    def predict(self, request: PredictionRequest) -> PredictionResult:
        if not request.selected_symptoms:
            raise ValueError("Please select at least one symptom before predicting.")

        unknown = [
            name for name in request.selected_symptoms if name not in self.symptoms.names
        ]
        if unknown:
            raise ValueError(f"Unknown symptoms: {', '.join(unknown)}")

        feature_vector = self.symptoms.to_feature_vector(request.selected_symptoms)
        features = pd.DataFrame([feature_vector], columns=self.symptoms.names)

        if not hasattr(self.model, "predict_proba"):
            raise ValueError("Loaded model does not support probability prediction.")

        probabilities = self.model.predict_proba(features)[0]
        class_labels = list(self.model.classes_)

        ranked_pairs = sorted(
            zip(class_labels, probabilities),
            key=lambda item: item[1],
            reverse=True,
        )
        top_disease, top_probability = ranked_pairs[0]
        top_n = [
            DiseaseProbability(disease=disease, probability=float(probability))
            for disease, probability in ranked_pairs[: self.TOP_N]
        ]

        return PredictionResult(
            top_disease=str(top_disease),
            top_probability=float(top_probability),
            ranked=top_n,
            is_low_confidence=float(top_probability) < self.CONFIDENCE_THRESHOLD,
        )
