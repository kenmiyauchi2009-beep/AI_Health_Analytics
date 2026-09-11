from __future__ import annotations

import re


class SafetyGuard:
    """Reject diagnosis-outside-pipeline and unrelated questions."""

    SUGGESTED_QUESTIONS = [
        "Why was this disease predicted?",
        "Why am I in this cluster?",
        "What does confidence mean?",
        "How is my symptom profile similar to this cluster?",
    ]

    _DIAGNOSIS_PATTERNS = [
        r"\bdiagnose me\b",
        r"\bwhat do i (really )?have\b",
        r"\bdo i have\b",
        r"\bis it (cancer|covid|hiv|aids)\b",
        r"\bshould i take\b",
        r"\bprescribe\b",
        r"\btreatment plan\b",
        r"\bignore (the )?(model|prediction|cluster)\b",
        r"\bwithout (using )?(the )?(model|prediction|ml|pipeline)\b",
    ]

    _UNRELATED_PATTERNS = [
        r"\bweather\b",
        r"\bstock\b",
        r"\bjoke\b",
        r"\brecipe\b",
        r"\bcapital of\b",
        r"\bwrite (me )?code\b",
        r"\btranslate\b",
    ]

    def check(self, question: str) -> tuple[bool, str | None]:
        text = question.strip().lower()
        if not text:
            return False, "Please enter a question about your analysis results."

        for pattern in self._DIAGNOSIS_PATTERNS:
            if re.search(pattern, text):
                return (
                    False,
                    "I can only explain the app’s ML results (predicted disease and cluster match). "
                    "I cannot give a medical diagnosis outside that pipeline. "
                    "Try a suggested question, or ask why the model/cluster result looks the way it does.",
                )

        for pattern in self._UNRELATED_PATTERNS:
            if re.search(pattern, text):
                return (
                    False,
                    "That question is outside this assistant’s scope. "
                    "Ask about your selected symptoms, predicted disease, confidence, or cluster results.",
                )

        return True, None
