from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from prediction.controller import DiseasePredictionController
from prediction.model_loader import ModelLoader
from prediction.prediction_request import PredictionRequest
from prediction.symptoms import Symptoms


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models" / "model.pkl"
DEFAULT_SYMPTOMS = ROOT / "models" / "symptoms.pkl"
DEFAULT_METADATA = ROOT / "models" / "model_metadata.pkl"


class SymptomsTests(unittest.TestCase):
    def test_loads_symptoms_from_pickle_not_hardcoded(self) -> None:
        symptoms = Symptoms.from_pickle(DEFAULT_SYMPTOMS)
        self.assertGreater(len(symptoms.names), 1)
        self.assertIn("itching", symptoms.names)
        self.assertIn("skin_rash", symptoms.names)

    def test_feature_vector_matches_symptom_order(self) -> None:
        symptoms = Symptoms(["a", "b", "c"])
        vector = symptoms.to_feature_vector(["c", "a"])
        self.assertEqual(vector, [1.0, 0.0, 1.0])


class ControllerValidationTests(unittest.TestCase):
    def test_empty_selection_raises_clear_error(self) -> None:
        symptoms = Symptoms(["itching", "skin_rash"])
        model = MagicMock()
        controller = DiseasePredictionController(model=model, symptoms=symptoms)

        with self.assertRaises(ValueError) as context:
            controller.predict(PredictionRequest(selected_symptoms=[]))

        self.assertIn("select at least one symptom", str(context.exception).lower())
        model.predict_proba.assert_not_called()


class RealModelPredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        loader = ModelLoader()
        cls.model = loader.load_model(DEFAULT_MODEL)
        cls.symptoms = loader.load_symptoms(DEFAULT_SYMPTOMS)
        cls.metadata = loader.load_metadata(DEFAULT_METADATA)
        cls.controller = DiseasePredictionController(cls.model, cls.symptoms)

    def test_predicts_top_disease_and_top_n(self) -> None:
        result = self.controller.predict(
            PredictionRequest(
                selected_symptoms=["itching", "skin_rash", "nodal_skin_eruptions"]
            )
        )
        self.assertTrue(result.top_disease)
        self.assertEqual(len(result.ranked), DiseasePredictionController.TOP_N)
        self.assertEqual(result.ranked[0].disease, result.top_disease)
        self.assertAlmostEqual(result.ranked[0].probability, result.top_probability)
        self.assertGreaterEqual(result.top_probability, 0.50)
        self.assertFalse(result.is_low_confidence)

    def test_low_confidence_flag_when_below_threshold(self) -> None:
        # Use a mock model so we can force a low max probability.
        symptoms = Symptoms(["itching", "skin_rash"])
        model = MagicMock()
        model.classes_ = ["A", "B", "C"]
        model.predict_proba.return_value = [[0.20, 0.15, 0.10]]
        controller = DiseasePredictionController(model=model, symptoms=symptoms)

        result = controller.predict(PredictionRequest(selected_symptoms=["itching"]))

        self.assertTrue(result.is_low_confidence)
        self.assertEqual(result.top_disease, "A")
        self.assertEqual(len(result.ranked), 3)

    def test_metadata_disease_labels_match_model_classes(self) -> None:
        self.assertEqual(list(self.model.classes_), self.metadata["disease_labels"])


if __name__ == "__main__":
    unittest.main()
