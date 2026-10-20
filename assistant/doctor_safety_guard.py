from __future__ import annotations

from assistant.safety_guard import SafetyGuard


class DoctorSafetyGuard(SafetyGuard):
    """Same scope limits as the patient assistant, with doctor-oriented suggestions."""

    SUGGESTED_QUESTIONS = [
        "Summarize this analysis",
        "Explain the model uncertainty",
        "Compare with the previous analysis",
        "Explain the cluster",
    ]
