from __future__ import annotations

from dataclasses import dataclass, field

from assistant.patient_analysis_context import PatientAnalysisContext


@dataclass
class DoctorAnalysisContext(PatientAnalysisContext):
    """One saved patient analysis plus the patient's earlier analyses, for the doctor assistant."""

    analysis_date: str = ""
    known_conditions: list[str] = field(default_factory=list)
    # Earlier analyses as plain dicts: date, symptoms, predicted_disease, confidence, top_predictions.
    previous_analyses: list[dict] = field(default_factory=list)

    def to_prompt_dict(self) -> dict:
        payload = super().to_prompt_dict()
        payload["analysis_date"] = self.analysis_date
        payload["patient_known_conditions"] = self.known_conditions
        payload["previous_analyses"] = self.previous_analyses
        return payload
