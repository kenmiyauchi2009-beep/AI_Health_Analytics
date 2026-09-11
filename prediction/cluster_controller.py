from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prediction.cluster_result import (
    ClusterAssignmentResult,
    ClusterComparison,
    ClusterSummary,
    RankedItem,
)
from prediction.prediction_request import PredictionRequest
from prediction.symptoms import Symptoms

DEFAULT_KMEANS_PATH = Path("models/kmeans_model.pkl")
DEFAULT_CLUSTER_METADATA_PATH = Path("models/cluster_metadata.pkl")
DEFAULT_CLUSTER_SYMPTOMS_PATH = Path("models/cluster_symptom_columns.pkl")


class ClusterController:
    """Assign symptoms to the nearest K-Means cluster and support browse/compare."""

    TOP_ITEMS = 5

    def __init__(self, model: Any, symptoms: Symptoms, metadata: dict) -> None:
        self.model = model
        self.symptoms = symptoms
        self.metadata = metadata
        self._summaries = self._build_summaries(metadata)

    @property
    def cluster_ids(self) -> list[int]:
        return sorted(self._summaries.keys())

    def get_summary(self, cluster_id: int) -> ClusterSummary:
        if cluster_id not in self._summaries:
            raise ValueError(f"Unknown cluster id: {cluster_id}")
        return self._summaries[cluster_id]

    def assign(self, request: PredictionRequest) -> ClusterAssignmentResult:
        if not request.selected_symptoms:
            raise ValueError("Please select at least one symptom before predicting.")

        unknown = [
            name for name in request.selected_symptoms if name not in self.symptoms.names
        ]
        if unknown:
            raise ValueError(f"Unknown symptoms: {', '.join(unknown)}")

        if not hasattr(self.model, "predict") or not hasattr(self.model, "transform"):
            raise ValueError("Loaded model does not look like a fitted K-Means model.")

        feature_vector = self.symptoms.to_feature_vector(request.selected_symptoms)
        features = pd.DataFrame([feature_vector], columns=self.symptoms.names)

        cluster_id = int(self.model.predict(features)[0])
        distances = np.asarray(self.model.transform(features)[0], dtype=float)
        confidence_scores = self._softmax_inverse_distances(distances)
        confidence = float(confidence_scores[cluster_id])

        return ClusterAssignmentResult(
            cluster_id=cluster_id,
            confidence=confidence,
            distances=[float(value) for value in distances],
            summary=self.get_summary(cluster_id),
        )

    def compare(self, left_id: int, right_id: int) -> ClusterComparison:
        left = self.get_summary(left_id)
        right = self.get_summary(right_id)
        left_symptoms = {item.name for item in left.top_symptoms}
        right_symptoms = {item.name for item in right.top_symptoms}
        left_diseases = {item.name for item in left.top_diseases}
        right_diseases = {item.name for item in right.top_diseases}
        return ClusterComparison(
            left=left,
            right=right,
            shared_symptoms=sorted(left_symptoms & right_symptoms),
            shared_diseases=sorted(left_diseases & right_diseases),
        )

    @staticmethod
    def _softmax_inverse_distances(distances: np.ndarray) -> np.ndarray:
        inverse = 1.0 / (distances + 1e-9)
        total = float(inverse.sum())
        if total <= 0:
            return np.full_like(inverse, 1.0 / len(inverse))
        return inverse / total

    def _build_summaries(self, metadata: dict) -> dict[int, ClusterSummary]:
        if "cluster_summaries" not in metadata:
            raise ValueError("cluster metadata is missing 'cluster_summaries'.")

        summaries: dict[int, ClusterSummary] = {}
        raw_summaries = metadata["cluster_summaries"]
        sizes = metadata.get("cluster_sizes", {})

        for key, payload in raw_summaries.items():
            cluster_id = int(key)
            patient_count = int(
                payload.get("patient_count", sizes.get(key, sizes.get(cluster_id, 0)))
            )
            summaries[cluster_id] = ClusterSummary(
                cluster_id=cluster_id,
                patient_count=patient_count,
                top_symptoms=self._rank_items(payload.get("top_symptoms", {})),
                top_diseases=self._rank_items(payload.get("top_diseases", {})),
            )
        return summaries

    def _rank_items(self, mapping: dict) -> list[RankedItem]:
        ranked = [
            RankedItem(name=str(name), score=float(score))
            for name, score in mapping.items()
            if float(score) > 0
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: self.TOP_ITEMS]
