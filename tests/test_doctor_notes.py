import unittest
from datetime import datetime

from app_pages.doctor_notes_service import DoctorNote, get_doctor_notes, save_doctor_note
from app_pages.patient_overview_service import get_patient_overview
from tests.test_practitioner import FakeCollection

PATIENT = {"id": 7, "email": "Pat@Example.com", "name": "Pat Lee"}


class DoctorNoteTests(unittest.TestCase):
    def setUp(self):
        self.notes = FakeCollection()

    def test_save_stores_note_separately_with_patient_id(self):
        note, error = save_doctor_note(self.notes, PATIENT, "Doc@Example.com", "  Follow up in 2 weeks  ", 501)

        self.assertIsNone(error)
        self.assertIsInstance(note, DoctorNote)
        stored = self.notes.docs[0]
        self.assertEqual(stored["_id"], note.id)
        self.assertEqual(stored["patient_id"], 7)
        self.assertEqual(stored["patient_email"], "pat@example.com")
        self.assertEqual(stored["doctor_email"], "doc@example.com")
        self.assertEqual(stored["analysis_id"], 501)
        self.assertEqual(stored["text"], "Follow up in 2 weeks")

    def test_rejects_empty_note_and_missing_patient(self):
        self.assertEqual(save_doctor_note(self.notes, PATIENT, "doc@example.com", "   ")[1], "Please write a note before saving.")
        self.assertIsNotNone(save_doctor_note(self.notes, {"email": "pat@example.com"}, "doc@example.com", "Hi")[1])
        self.assertIsNotNone(save_doctor_note(None, PATIENT, "doc@example.com", "Hi")[1])
        self.assertEqual(self.notes.docs, [])

    def test_lists_newest_first_and_filters_by_analysis(self):
        first, _ = save_doctor_note(self.notes, PATIENT, "doc@example.com", "First", 501)
        save_doctor_note(self.notes, PATIENT, "doc@example.com", "Other analysis", 502)
        save_doctor_note(self.notes, {"id": 8, "email": "x@example.com"}, "doc@example.com", "Other patient", 501)
        last, _ = save_doctor_note(self.notes, PATIENT, "doc@example.com", "Second", 501)
        next(doc for doc in self.notes.docs if doc["_id"] == first.id)["created_at"] = datetime(2020, 1, 1)

        notes = get_doctor_notes(self.notes, 7, 501)

        self.assertEqual([note.text for note in notes], ["Second", "First"])
        self.assertEqual(notes[0].id, last.id)
        self.assertEqual(len(get_doctor_notes(self.notes, 7)), 3)

    def test_patient_overview_exposes_patient_id(self):
        users = FakeCollection(
            [{"_id": 7, "email": "pat@example.com", "role": "Patient", "primary_doctor_email": "doc@example.com"}]
        )
        overview = get_patient_overview(users, FakeCollection(), "doc@example.com", "pat@example.com")
        self.assertEqual(overview["id"], 7)


if __name__ == "__main__":
    unittest.main()
