from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from prediction.cluster_controller import ClusterController
from prediction.model_loader import ModelLoader
from prediction.prediction_request import PredictionRequest
from prediction.symptoms import Symptoms


ROOT = Path(__file__).resolve().parents[1]
KMEANS_MODEL = ROOT / "models" / "kmeans_model.pkl"
CLUSTER_METADATA = ROOT / "models" / "cluster_metadata.pkl"
CLUSTER_SYMPTOMS = ROOT / "models" / "cluster_symptom_columns.pkl"


class ClusterControllerValidationTests(unittest.TestCase):
    def test_empty_selection_raises_clear_error(self) -> None:
        symptoms = Symptoms(["itching", "skin_rash"])
        model = MagicMock()
        metadata = {
            "cluster_sizes": {0: 10},
            "cluster_summaries": {
                0: {
                    "patient_count": 10,
                    "top_symptoms": {"itching": 0.9},
                    "top_diseases": {"Allergy": 1.0},
                }
            },
        }
        controller = ClusterController(model=model, symptoms=symptoms, metadata=metadata)

        with self.assertRaises(ValueError) as context:
            controller.assign(PredictionRequest(selected_symptoms=[]))

        self.assertIn("select at least one symptom", str(context.exception).lower())
        model.predict.assert_not_called()


class RealKMeansClusterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        loader = ModelLoader()
        cls.model = loader.load_model(KMEANS_MODEL)
        cls.symptoms = loader.load_symptoms(CLUSTER_SYMPTOMS)
        cls.metadata = loader.load_metadata(CLUSTER_METADATA)
        cls.controller = ClusterController(cls.model, cls.symptoms, cls.metadata)

    def test_assigns_cluster_with_confidence_and_summary(self) -> None:
        result = self.controller.assign(
            PredictionRequest(
                selected_symptoms=["congestion", "runny_nose", "loss_of_smell", "phlegm"]
            )
        )
        self.assertIn(result.cluster_id, self.controller.cluster_ids)
        self.assertGreater(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertEqual(result.summary.cluster_id, result.cluster_id)
        self.assertGreater(result.summary.patient_count, 0)
        self.assertTrue(result.summary.top_symptoms)
        self.assertTrue(result.summary.top_diseases)

    def test_browse_all_clusters(self) -> None:
        self.assertEqual(self.controller.cluster_ids, list(range(8)))
        for cluster_id in self.controller.cluster_ids:
            summary = self.controller.get_summary(cluster_id)
            self.assertEqual(summary.cluster_id, cluster_id)
            self.assertGreater(summary.patient_count, 0)

    def test_compare_two_clusters(self) -> None:
        comparison = self.controller.compare(4, 6)
        self.assertEqual(comparison.left.cluster_id, 4)
        self.assertEqual(comparison.right.cluster_id, 6)
        self.assertIsInstance(comparison.shared_symptoms, list)
        self.assertIsInstance(comparison.shared_diseases, list)

    def test_softmax_confidence_sums_near_one(self) -> None:
        distances = np.array([1.0, 2.0, 3.0])
        scores = ClusterController._softmax_inverse_distances(distances)
        self.assertAlmostEqual(float(scores.sum()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
