import unittest
from datetime import datetime

from app_pages.analysis_review_service import (
    analysis_to_prediction_result,
    assign_cluster,
    build_doctor_context,
    explain_cluster_match,
)
from assistant.ai_query import AIQuery
from assistant.ai_result_assistant import AIResultAssistant
from assistant.doctor_prompt_builder import DoctorPromptBuilder
from assistant.doctor_safety_guard import DoctorSafetyGuard
from prediction.cluster_controller import (
    DEFAULT_CLUSTER_METADATA_PATH,
    DEFAULT_CLUSTER_SYMPTOMS_PATH,
    DEFAULT_KMEANS_PATH,
    ClusterController,
)
from prediction.model_loader import ModelLoader


def _analysis(_id, created_at, disease="Flu", probability=0.72, symptoms=None):
    return {
        "_id": _id,
        "patient_email": "pat@example.com",
        "symptoms": symptoms or ["high_fever", "headache"],
        "top_disease": disease,
        "top_probability": probability,
        "ranked": [{"disease": disease, "probability": probability}, {"disease": "Cold", "probability": 0.2}],
        "is_low_confidence": probability < 0.5,
        "created_at": created_at,
    }


class _FakeLLM:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return "ok"


class AnalysisReviewServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = ModelLoader()
        cls.controller = ClusterController(
            model=loader.load_model(DEFAULT_KMEANS_PATH),
            symptoms=loader.load_symptoms(DEFAULT_CLUSTER_SYMPTOMS_PATH),
            metadata=loader.load_metadata(DEFAULT_CLUSTER_METADATA_PATH),
        )

    def test_rebuilds_prediction_result(self):
        result = analysis_to_prediction_result(_analysis(1, datetime(2026, 10, 5), probability=0.4))

        self.assertEqual(result.top_disease, "Flu")
        self.assertEqual([item.disease for item in result.ranked], ["Flu", "Cold"])
        self.assertTrue(result.is_low_confidence)

    def test_assign_cluster_ignores_unknown_symptoms(self):
        symptoms = self.controller.symptoms.names[:3]
        assignment = assign_cluster(self.controller, symptoms + ["not_a_symptom"])

        self.assertIn(assignment.cluster_id, self.controller.cluster_ids)
        self.assertIsNone(assign_cluster(self.controller, ["not_a_symptom"]))

    def test_explain_cluster_match(self):
        top = self.controller.get_summary(0).top_symptoms
        symptoms = [top[0].name, top[1].name]
        assignment = assign_cluster(self.controller, symptoms)
        explanation = explain_cluster_match(self.controller, symptoms, assignment)

        cluster_symptoms = {item.name for item in assignment.summary.top_symptoms}
        self.assertEqual(set(explanation["shared_symptoms"]), cluster_symptoms & set(symptoms))
        self.assertEqual(
            set(explanation["shared_symptoms"]) | set(explanation["cluster_symptoms_not_reported"]),
            cluster_symptoms,
        )
        self.assertNotEqual(explanation["runner_up"]["cluster_id"], assignment.cluster_id)
        self.assertLessEqual(explanation["runner_up"]["similarity"], assignment.confidence)

    def test_doctor_context_includes_only_earlier_analyses(self):
        september = _analysis(1, datetime(2026, 9, 5), disease="Cold", probability=0.6)
        october = _analysis(2, datetime(2026, 10, 5))
        november = _analysis(3, datetime(2026, 11, 5))

        context = build_doctor_context(october, [november, october, september], None, ["Asthma"])
        payload = context.to_prompt_dict()

        self.assertEqual(payload["analysis_date"], "Oct 05, 2026 12:00 AM")
        self.assertEqual(payload["patient_known_conditions"], ["Asthma"])
        self.assertEqual([item["predicted_disease"] for item in payload["previous_analyses"]], ["Cold"])
        self.assertEqual(payload["disease_prediction"]["predicted_disease"], "Flu")


class DoctorAssistantTests(unittest.TestCase):
    def test_uses_doctor_prompt_and_suggestions(self):
        llm = _FakeLLM()
        assistant = AIResultAssistant(
            llm_client=llm,
            prompt_builder=DoctorPromptBuilder(),
            safety_guard=DoctorSafetyGuard(),
        )
        context = build_doctor_context(_analysis(1, datetime(2026, 10, 5)), [], None)

        response = assistant.ask(AIQuery(text="Summarize this analysis"), context)

        self.assertFalse(response.refused)
        self.assertIn("doctor", llm.messages[0]["content"])
        self.assertIn("previous_analyses", llm.messages[1]["content"])
        self.assertEqual(response.suggested_questions, DoctorSafetyGuard.SUGGESTED_QUESTIONS)

    def test_doctor_suggestions_pass_safety_guard(self):
        guard = DoctorSafetyGuard()
        for question in DoctorSafetyGuard.SUGGESTED_QUESTIONS:
            self.assertEqual(guard.check(question), (True, None))


if __name__ == "__main__":
    unittest.main()
