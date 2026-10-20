"""Rebuild the full ML output for a saved patient analysis, for the doctor's Review Analysis page.

Saved analyses store the symptoms and the disease prediction. The patient
subgroup (K-Means cluster) is recomputed from the saved symptoms, so older
analyses get one too.
"""

from __future__ import annotations

from assistant.doctor_analysis_context import DoctorAnalysisContext
from prediction.cluster_controller import ClusterController
from prediction.cluster_result import ClusterAssignmentResult
from prediction.prediction_request import PredictionRequest
from prediction.prediction_result import DiseaseProbability, PredictionResult


def format_analysis_date(value) -> str:
    return value.strftime("%b %d, %Y %I:%M %p") if hasattr(value, "strftime") else "Unknown date"


def analysis_to_prediction_result(analysis: dict) -> PredictionResult:
    """Turn a saved analysis document back into the PredictionResult the pipeline produced."""
    return PredictionResult(
        top_disease=str(analysis.get("top_disease") or "Unknown"),
        top_probability=float(analysis.get("top_probability") or 0),
        ranked=[
            DiseaseProbability(str(item.get("disease")), float(item.get("probability") or 0))
            for item in analysis.get("ranked") or []
        ],
        is_low_confidence=bool(analysis.get("is_low_confidence")),
    )


def assign_cluster(controller: ClusterController, symptoms: list[str]) -> ClusterAssignmentResult | None:
    """Assign the saved symptoms to a cluster, ignoring any the cluster model doesn't know."""
    known = [symptom for symptom in symptoms if symptom in controller.symptoms.names]
    if not known:
        return None
    return controller.assign(PredictionRequest(selected_symptoms=known))


def explain_cluster_match(
    controller: ClusterController,
    symptoms: list[str],
    assignment: ClusterAssignmentResult,
) -> dict:
    """Explain a cluster match: symptom overlap with the cluster and the closest alternative cluster."""
    cluster_symptoms = [item.name for item in assignment.summary.top_symptoms]
    reported = set(symptoms)

    similarities = controller.similarity_scores(assignment.distances)
    runner_up = None
    for cluster_id in sorted(range(len(similarities)), key=lambda index: similarities[index], reverse=True):
        if cluster_id != assignment.cluster_id:
            runner_up = {"cluster_id": cluster_id, "similarity": similarities[cluster_id]}
            break

    return {
        "shared_symptoms": [name for name in cluster_symptoms if name in reported],
        "cluster_symptoms_not_reported": [name for name in cluster_symptoms if name not in reported],
        "reported_symptoms_not_typical": sorted(reported - set(cluster_symptoms)),
        "runner_up": runner_up,
    }


def _analysis_summary(analysis: dict) -> dict:
    return {
        "date": format_analysis_date(analysis.get("created_at")),
        "symptoms": list(analysis.get("symptoms") or []),
        "predicted_disease": analysis.get("top_disease"),
        "confidence": float(analysis.get("top_probability") or 0),
        "top_predictions": list(analysis.get("ranked") or []),
        "is_low_confidence": bool(analysis.get("is_low_confidence")),
    }


def build_doctor_context(
    analysis: dict,
    all_analyses: list[dict],
    assignment: ClusterAssignmentResult | None,
    known_conditions: list[str] | None = None,
) -> DoctorAnalysisContext:
    """Assistant context for one analysis, with the patient's earlier analyses for comparison."""
    created_at = analysis.get("created_at")
    previous = [
        _analysis_summary(other)
        for other in all_analyses
        if other.get("_id") != analysis.get("_id")
        and (created_at is None or other.get("created_at") is None or other["created_at"] < created_at)
    ]
    return DoctorAnalysisContext(
        selected_symptoms=list(analysis.get("symptoms") or []),
        prediction=analysis_to_prediction_result(analysis),
        cluster_assignment=assignment,
        analysis_date=format_analysis_date(created_at),
        known_conditions=list(known_conditions or []),
        previous_analyses=previous,
    )
