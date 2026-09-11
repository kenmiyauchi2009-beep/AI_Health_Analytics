from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from assistant.ai_query import AIQuery
from assistant.ai_result_assistant import AIResultAssistant
from assistant.patient_analysis_context import PatientAnalysisContext
from assistant.safety_guard import SafetyGuard
from prediction.cluster_result import ClusterAssignmentResult, ClusterSummary, RankedItem
from prediction.prediction_result import DiseaseProbability, PredictionResult


def _sample_context() -> PatientAnalysisContext:
    prediction = PredictionResult(
        top_disease="Common Cold",
        top_probability=0.82,
        ranked=[
            DiseaseProbability(disease="Common Cold", probability=0.82),
            DiseaseProbability(disease="Allergy", probability=0.10),
            DiseaseProbability(disease="Pneumonia", probability=0.05),
        ],
        is_low_confidence=False,
    )
    cluster = ClusterAssignmentResult(
        cluster_id=4,
        confidence=0.61,
        distances=[1.0, 2.0, 3.0, 4.0, 0.5, 2.2, 2.5, 2.8],
        summary=ClusterSummary(
            cluster_id=4,
            patient_count=120,
            top_symptoms=[RankedItem(name="runny_nose", score=1.0)],
            top_diseases=[RankedItem(name="Common Cold", score=1.0)],
        ),
    )
    return PatientAnalysisContext(
        selected_symptoms=["runny_nose", "congestion"],
        prediction=prediction,
        cluster_assignment=cluster,
    )


class SafetyGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = SafetyGuard()

    def test_allows_suggested_style_question(self) -> None:
        ok, reason = self.guard.check("Why was this disease predicted?")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_rejects_independent_diagnosis(self) -> None:
        ok, reason = self.guard.check("Diagnose me without using the model")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)

    def test_rejects_unrelated_question(self) -> None:
        ok, reason = self.guard.check("What is the weather today?")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)


class AIResultAssistantTests(unittest.TestCase):
    def test_requires_analysis_context(self) -> None:
        llm = MagicMock()
        assistant = AIResultAssistant(llm_client=llm)
        response = assistant.ask(
            AIQuery(text="Why was this disease predicted?"),
            PatientAnalysisContext(),
        )
        self.assertTrue(response.refused)
        llm.complete.assert_not_called()

    def test_safety_refusal_does_not_call_llm(self) -> None:
        llm = MagicMock()
        assistant = AIResultAssistant(llm_client=llm)
        response = assistant.ask(
            AIQuery(text="Diagnose me independently"),
            _sample_context(),
        )
        self.assertTrue(response.refused)
        llm.complete.assert_not_called()

    def test_allowed_question_calls_llm(self) -> None:
        llm = MagicMock()
        llm.complete.return_value = "Because the model ranked Common Cold highest."
        assistant = AIResultAssistant(llm_client=llm)
        response = assistant.ask(
            AIQuery(text="Why was this disease predicted?"),
            _sample_context(),
        )
        self.assertFalse(response.refused)
        self.assertIn("Common Cold", response.answer)
        llm.complete.assert_called_once()
        self.assertEqual(len(assistant.conversation.messages), 2)


class ContextTests(unittest.TestCase):
    def test_prompt_dict_includes_prediction_and_cluster(self) -> None:
        payload = _sample_context().to_prompt_dict()
        self.assertEqual(payload["disease_prediction"]["predicted_disease"], "Common Cold")
        self.assertEqual(payload["clustering"]["assigned_cluster"], 4)
        self.assertEqual(payload["selected_symptoms"], ["runny_nose", "congestion"])


if __name__ == "__main__":
    unittest.main()
