import re
import unittest
import zlib

from app_pages.prescription_pdf import build_prescription_pdf, prescription_pdf_filename
from app_pages.prescription_service import (
    STATUS_DRAFT,
    STATUS_FINALIZED,
    STATUS_VOIDED,
    clean_medications,
    create_draft,
    finalize_prescription,
    generate_prescription_id,
    get_prescription_for_doctor,
    list_prescriptions_for_doctor,
    list_prescriptions_for_patient,
    update_draft,
    void_prescription,
)
from tests.test_practitioner import FakeCollection

DOCTOR = {"_id": 1, "email": "doc@example.com", "role": "Doctor", "first_name": "Ann", "last_name": "Ito"}
OTHER_DOCTOR = {"_id": 3, "email": "other@example.com", "role": "Doctor", "first_name": "Ben", "last_name": "Ota"}
PATIENT = {"id": 2, "email": "pat@example.com", "name": "Pat Lee"}
MEDICATION = {"name": "Demo-med", "dosage": "10 mg", "frequency": "Once daily", "duration": "5 days"}


class PrescriptionServiceTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeCollection(
            [
                DOCTOR,
                OTHER_DOCTOR,
                {"_id": 2, "email": "pat@example.com", "role": "Patient", "primary_doctor_email": "doc@example.com"},
                {"_id": 4, "email": "eve@example.com", "role": "Patient", "primary_doctor_email": "other@example.com"},
            ]
        )
        self.requests = FakeCollection()
        self.rx = FakeCollection()

    def _create(self, doctor=DOCTOR, patient=PATIENT, medications=None, **kwargs):
        return create_draft(
            self.rx, self.users, self.requests,
            patient=patient, doctor=doctor, medications=medications or [MEDICATION], **kwargs
        )

    def _finalize(self, prescription, doctor_email="doc@example.com"):
        return finalize_prescription(self.rx, self.users, self.requests, prescription["_id"], doctor_email)

    def _stored(self, prescription):
        return self.rx.find_one({"_id": prescription["_id"]})

    def test_generated_ids_are_labelled_simulated_and_unique(self):
        ids = {generate_prescription_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(value.startswith("SIM-RX-") for value in ids))

    def test_clean_medications_drops_blank_rows_and_requires_fields(self):
        medications, errors = clean_medications([{"name": " A ", "dosage": "1", "frequency": "2", "duration": "3"}, {}])
        self.assertEqual(errors, [])
        self.assertEqual(medications[0]["name"], "A")
        self.assertEqual(len(medications), 1)

        _, errors = clean_medications([{"name": "A"}])
        self.assertEqual(errors, ["Medication 1: Dosage, Frequency, Duration required."])
        self.assertEqual(clean_medications([{}])[1], ["Add at least one medication."])

    def test_create_draft_fills_ids_and_audit(self):
        prescription, errors = self._create(
            medications=[MEDICATION, {**MEDICATION, "name": "Second", "instructions": "With water"}],
            doctor_note="Demo", analysis_id=501, prescription_id="SIM-RX-TEST",
        )

        self.assertEqual(errors, [])
        stored = self._stored(prescription)
        self.assertEqual(stored["status"], STATUS_DRAFT)
        self.assertEqual(stored["prescription_id"], "SIM-RX-TEST")
        self.assertEqual((stored["patient_id"], stored["doctor_id"]), (2, 1))
        self.assertEqual(stored["doctor_name"], "Dr. Ann Ito")
        self.assertEqual(len(stored["medications"]), 2)
        self.assertTrue(stored["is_simulated"])
        self.assertEqual([entry["action"] for entry in stored["audit_history"]], ["created"])

    def test_only_primary_practitioner_can_create(self):
        prescription, errors = self._create(doctor=OTHER_DOCTOR)
        self.assertIsNone(prescription)
        self.assertIn("Primary Health Practitioner", errors[0])
        self.assertEqual(self.rx.docs, [])

    def test_drafts_are_private_to_their_author(self):
        draft, _ = self._create()

        self.assertEqual(len(list_prescriptions_for_doctor(self.rx, "doc@example.com", "pat@example.com")), 1)
        self.assertEqual(list_prescriptions_for_doctor(self.rx, "other@example.com", "pat@example.com"), [])
        self.assertIsNone(get_prescription_for_doctor(self.rx, draft["_id"], "other@example.com"))
        self.assertEqual(list_prescriptions_for_patient(self.rx, "pat@example.com"), [])

    def test_author_edits_draft_and_others_cannot(self):
        draft, _ = self._create()

        self.assertEqual(update_draft(self.rx, draft["_id"], "other@example.com", medications=[MEDICATION]),
                         ["Prescription not found."])
        self.assertEqual(update_draft(self.rx, draft["_id"], "doc@example.com",
                                      medications=[{**MEDICATION, "dosage": "20 mg"}], doctor_note="Updated"), [])

        stored = self._stored(draft)
        self.assertEqual(stored["medications"][0]["dosage"], "20 mg")
        self.assertEqual(stored["doctor_note"], "Updated")
        self.assertEqual([entry["action"] for entry in stored["audit_history"]], ["created", "edited"])

    def test_finalize_then_read_only_then_void(self):
        draft, _ = self._create()

        self.assertEqual(self._finalize(draft, "other@example.com"), ["Prescription not found."])
        self.assertEqual(self._finalize(draft), [])
        self.assertEqual(self._stored(draft)["status"], STATUS_FINALIZED)
        self.assertEqual(self._finalize(draft), ["Only draft prescriptions can be finalized."])
        self.assertEqual(update_draft(self.rx, draft["_id"], "doc@example.com", medications=[MEDICATION]),
                         ["Only draft prescriptions can be edited."])

        self.assertEqual(void_prescription(self.rx, draft["_id"], "doc@example.com", "  "),
                         ["Please give a reason for voiding."])
        self.assertEqual(void_prescription(self.rx, draft["_id"], "other@example.com", "x"),
                         ["Only the prescribing doctor can void this prescription."])
        self.assertEqual(void_prescription(self.rx, draft["_id"], "doc@example.com", "Entered in error"), [])

        stored = self._stored(draft)
        self.assertEqual(stored["status"], STATUS_VOIDED)
        self.assertEqual(stored["void_reason"], "Entered in error")
        self.assertEqual([entry["action"] for entry in stored["audit_history"]], ["created", "finalized", "voided"])
        self.assertEqual(void_prescription(self.rx, draft["_id"], "doc@example.com", "again"),
                         ["Only finalized prescriptions can be voided."])

    def test_cannot_void_a_draft(self):
        draft, _ = self._create()
        self.assertEqual(void_prescription(self.rx, draft["_id"], "doc@example.com", "x"),
                         ["Only finalized prescriptions can be voided."])

    def test_finalize_requires_still_being_primary_practitioner(self):
        draft, _ = self._create()
        self.users.update_one({"email": "pat@example.com"}, {"$set": {"primary_doctor_email": "other@example.com"}})
        self.assertIn("Primary Health Practitioner", self._finalize(draft)[0])

    def test_patient_sees_only_own_finalized_and_voided(self):
        finalized, _ = self._create(medications=[{**MEDICATION, "name": "Finalized"}])
        self._finalize(finalized)
        voided, _ = self._create(medications=[{**MEDICATION, "name": "Voided"}])
        self._finalize(voided)
        void_prescription(self.rx, voided["_id"], "doc@example.com", "Mistake")
        self._create(medications=[{**MEDICATION, "name": "Draft"}])
        eve_rx, _ = self._create(doctor=OTHER_DOCTOR, patient={"id": 4, "email": "eve@example.com", "name": "Eve"})
        self._finalize(eve_rx, "other@example.com")

        names = {rx["medications"][0]["name"] for rx in list_prescriptions_for_patient(self.rx, "pat@example.com")}
        self.assertEqual(names, {"Finalized", "Voided"})

    def test_doctor_status_filter(self):
        finalized, _ = self._create()
        self._finalize(finalized)
        self._create()

        drafts = list_prescriptions_for_doctor(self.rx, "doc@example.com", "pat@example.com", [STATUS_DRAFT])
        self.assertEqual([rx["status"] for rx in drafts], [STATUS_DRAFT])
        self.assertEqual(len(list_prescriptions_for_doctor(self.rx, "doc@example.com", "pat@example.com", [])), 0)
        # Another doctor sees the finalized record in the patient's history, but not the draft.
        self.assertEqual(
            [rx["status"] for rx in list_prescriptions_for_doctor(self.rx, "other@example.com", "pat@example.com")],
            [STATUS_FINALIZED],
        )


class PrescriptionPdfTests(unittest.TestCase):
    def _text(self, pdf: bytes) -> str:
        chunks = []
        for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
            try:
                chunks.append(zlib.decompress(stream).decode("latin-1"))
            except zlib.error:
                chunks.append(stream.decode("latin-1"))
        return "".join(chunks)

    def test_pdf_is_labelled_simulated_on_every_page(self):
        prescription = {
            "prescription_id": "SIM-RX-TEST", "status": STATUS_VOIDED, "void_reason": "Wrong dose — fixed",
            "patient_name": "Pat Lee", "patient_id": 2, "doctor_name": "Dr. Ann Ito", "doctor_id": 1,
            "medications": [MEDICATION] * 40,
        }
        pdf = build_prescription_pdf(prescription)
        text = self._text(pdf)

        self.assertTrue(pdf.startswith(b"%PDF"))
        pages = text.count("SIMULATED PRESCRIPTION - EDUCATIONAL DEMONSTRATION ONLY")
        self.assertGreater(pages, 1)
        self.assertEqual(text.count("Not a legally valid prescription"), pages)
        self.assertIn("VOIDED - SIMULATED", text)
        self.assertIn("Wrong dose - fixed", text)
        self.assertEqual(prescription_pdf_filename(prescription), "SIM-RX-TEST_SIMULATED.pdf")


if __name__ == "__main__":
    unittest.main()
