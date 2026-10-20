import unittest
from datetime import date, datetime

from app_pages.patient_overview_service import (
    calculate_age,
    get_patient_analyses,
    get_patient_overview,
    parse_known_conditions,
    review_analysis,
    save_analysis,
)
from prediction.prediction_result import DiseaseProbability, PredictionResult
from tests.test_practitioner import FakeCollection


def _result(disease="Flu", probability=0.72):
    return PredictionResult(
        top_disease=disease,
        top_probability=probability,
        ranked=[DiseaseProbability(disease, probability), DiseaseProbability("Cold", 0.2)],
        is_low_confidence=probability < 0.5,
    )


class CalculateAgeTests(unittest.TestCase):
    def test_age_before_and_after_birthday(self):
        self.assertEqual(calculate_age("2000-06-15", today=date(2026, 6, 14)), 25)
        self.assertEqual(calculate_age("2000-06-15", today=date(2026, 6, 15)), 26)

    def test_invalid_or_future_dates_return_none(self):
        self.assertIsNone(calculate_age("", today=date(2026, 1, 1)))
        self.assertIsNone(calculate_age("not-a-date", today=date(2026, 1, 1)))
        self.assertIsNone(calculate_age("2030-01-01", today=date(2026, 1, 1)))


class KnownConditionsTests(unittest.TestCase):
    def test_accepts_lists_and_comma_strings(self):
        self.assertEqual(parse_known_conditions(["Asthma", " "]), ["Asthma"])
        self.assertEqual(parse_known_conditions("Asthma, Diabetes ,"), ["Asthma", "Diabetes"])
        self.assertEqual(parse_known_conditions(None), [])


class AnalysisHistoryTests(unittest.TestCase):
    def test_save_and_list_newest_first(self):
        analyses = FakeCollection()
        older = save_analysis(analyses, "Pat@Example.com", ["cough"], _result("Cold", 0.4))
        newer = save_analysis(analyses, "pat@example.com", ["fever", "headache"], _result())
        older_doc = next(doc for doc in analyses.docs if doc["_id"] == older["_id"])
        older_doc["created_at"] = datetime(2020, 1, 1)

        history = get_patient_analyses(analyses, "pat@example.com")

        self.assertEqual([doc["_id"] for doc in history], [newer["_id"], older["_id"]])
        self.assertEqual(history[0]["symptoms"], ["fever", "headache"])
        self.assertEqual(history[0]["ranked"][0], {"disease": "Flu", "probability": 0.72})
        self.assertTrue(history[1]["is_low_confidence"])
        self.assertFalse(history[0]["reviewed"])

    def test_review_is_scoped_to_patient(self):
        analyses = FakeCollection()
        analysis = save_analysis(analyses, "pat@example.com", ["fever"], _result())

        self.assertFalse(review_analysis(analyses, analysis["_id"], "other@example.com", "doc@example.com"))
        self.assertTrue(review_analysis(analyses, analysis["_id"], "pat@example.com", "Doc@Example.com", " ok "))

        saved = get_patient_analyses(analyses, "pat@example.com")[0]
        self.assertTrue(saved["reviewed"])
        self.assertEqual(saved["reviewed_by"], "doc@example.com")
        self.assertEqual(saved["review_notes"], "ok")


class PatientOverviewTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeCollection(
            [
                {
                    "email": "pat@example.com",
                    "role": "Patient",
                    "first_name": "Pat",
                    "last_name": "Lee",
                    "date_of_birth": "1990-01-01",
                    "known_conditions": ["Asthma"],
                    "primary_doctor_email": "doc@example.com",
                },
                {"email": "doc@example.com", "role": "Doctor", "speciality": "GP"},
                {"email": "other@example.com", "role": "Doctor", "speciality": "GP"},
            ]
        )
        self.requests = FakeCollection()

    def test_primary_doctor_sees_profile(self):
        overview = get_patient_overview(self.users, self.requests, "doc@example.com", "pat@example.com")

        self.assertEqual(overview["name"], "Pat Lee")
        self.assertEqual(overview["known_conditions"], ["Asthma"])
        self.assertEqual(overview["age"], calculate_age("1990-01-01"))

    def test_other_doctor_is_denied(self):
        self.assertIsNone(get_patient_overview(self.users, self.requests, "other@example.com", "pat@example.com"))


if __name__ == "__main__":
    unittest.main()
