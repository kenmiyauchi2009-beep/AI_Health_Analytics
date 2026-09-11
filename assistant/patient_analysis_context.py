from __future__ import annotations

from dataclasses import dataclass, field

from prediction.cluster_result import ClusterAssignmentResult
from prediction.prediction_result import PredictionResult


@dataclass
class PatientAnalysisContext:
    """ML pipeline outputs the assistant is allowed to explain."""

    selected_symptoms: list[str] = field(default_factory=list)
    prediction: PredictionResult | None = None
    cluster_assignment: ClusterAssignmentResult | None = None

    def has_analysis(self) -> bool:
        return self.prediction is not None or self.cluster_assignment is not None

    def to_prompt_dict(self) -> dict:
        payload: dict = {
            "selected_symptoms": self.selected_symptoms,
        }
        if self.prediction is not None:
            payload["disease_prediction"] = {
                "predicted_disease": self.prediction.top_disease,
                "confidence": self.prediction.top_probability,
                "top_predictions": [
                    {
                        "disease": item.disease,
                        "probability": item.probability,
                    }
                    for item in self.prediction.ranked
                ],
                "is_low_confidence": self.prediction.is_low_confidence,
            }
        if self.cluster_assignment is not None:
            assignment = self.cluster_assignment
            payload["clustering"] = {
                "assigned_cluster": assignment.cluster_id,
                "cluster_similarity_confidence": assignment.confidence,
                "common_symptoms": [
                    {"symptom": item.name, "frequency": item.score}
                    for item in assignment.summary.top_symptoms
                ],
                "common_diseases": [
                    {"disease": item.name, "share": item.score}
                    for item in assignment.summary.top_diseases
                ],
                "patient_count": assignment.summary.patient_count,
            }
        return payload
