import unittest

import streamlit as st

from app_pages.dashboard_page import get_user_role
from app_pages.registration_page import (
    authenticate_user,
    get_registration_wizard_state,
    hash_password,
    normalize_registration_role,
    normalize_user_record,
    validate_registration,
)


class RegistrationValidationTests(unittest.TestCase):
    def test_patient_requires_required_fields(self):
        errors = validate_registration(
            {
                "role": "Patient",
                "first_name": "",
                "last_name": "Doe",
                "email": "patient@example.com",
                "password": "Secret123!",
                "confirm_password": "Secret123!",
                "phone_number": "",
                "date_of_birth": "",
                "address": "",
            },
            email_exists=lambda email: False,
        )

        self.assertIn("First name cannot be empty.", errors)
        self.assertIn("Date of Birth is required.", errors)
        self.assertIn("Address is required.", errors)

    def test_duplicate_email_is_rejected(self):
        errors = validate_registration(
            {
                "role": "Patient",
                "first_name": "Jane",
                "last_name": "Patient",
                "email": "existing@example.com",
                "password": "Secret123!",
                "confirm_password": "Secret123!",
                "phone_number": "",
                "date_of_birth": "1990-01-01",
                "address": "123 Main St",
            },
            email_exists=lambda email: True,
        )

        self.assertIn("Email must be unique.", errors)

    def test_passwords_must_match(self):
        errors = validate_registration(
            {
                "role": "Doctor",
                "first_name": "Dr.",
                "last_name": "Smith",
                "email": "doctor@example.com",
                "password": "Secret123!",
                "confirm_password": "Different123!",
                "phone_number": "",
                "medical_license_number": "MC-123",
                "speciality": "Cardiology",
                "yoe": 10,
                "clinic_or_hospital": "City Care",
            },
            email_exists=lambda email: False,
        )

        self.assertIn("Password and Confirm Password should match.", errors)

    def test_doctor_requires_role_specific_fields(self):
        errors = validate_registration(
            {
                "role": "Doctor",
                "first_name": "Dr.",
                "last_name": "Smith",
                "email": "doctor@example.com",
                "password": "Secret123!",
                "confirm_password": "Secret123!",
                "phone_number": "",
                "medical_license_number": "",
                "speciality": "",
                "yoe": 0,
                "clinic_or_hospital": "",
            },
            email_exists=lambda email: False,
        )

        self.assertIn("Medical License Number is required.", errors)
        self.assertIn("Speciality is required.", errors)
        self.assertIn("Degree is required.", errors)
        self.assertIn("Clinic / Hospital is required.", errors)

    def test_registration_wizard_starts_on_role_selection(self):
        st.session_state["registration_step"] = "role"
        st.session_state["registration_role"] = "Doctor"

        state = get_registration_wizard_state()

        self.assertEqual(state["step"], "role")
        self.assertEqual(state["role"], "Doctor")

    def test_doctor_role_detection_handles_legacy_record_values(self):
        self.assertEqual(get_user_role({"role": "Doctor"}), "Doctor")
        self.assertEqual(get_user_role({"speciality": "Cardiology"}), "Doctor")
        self.assertEqual(get_user_role({"role": "doctor"}), "Doctor")
        self.assertEqual(get_user_role({"role": "DR"}), "Doctor")

    def test_normalize_user_record_sets_doctor_role_when_missing(self):
        user = {"email": "doctor@example.com", "speciality": "Cardiology"}
        normalized = normalize_user_record(user)

        self.assertEqual(normalized["role"], "Doctor")

    def test_normalize_user_record_handles_doctor_aliases(self):
        self.assertEqual(normalize_user_record({"role": "dr"})["role"], "Doctor")
        self.assertEqual(normalize_user_record({"role": " physician "})["role"], "Doctor")

    def test_registration_role_is_not_fallen_back_to_patient_for_doctor_accounts(self):
        self.assertEqual(
            normalize_registration_role("Patient", doctor_fields={"medical_license_number": "123", "speciality": "Cardiology"}),
            "Doctor",
        )
        self.assertEqual(normalize_registration_role("Doctor", doctor_fields={}), "Doctor")

    def test_hash_password_is_not_plaintext(self):
        password_hash = hash_password("Secret123!")
        self.assertNotEqual(password_hash, "Secret123!")
        self.assertTrue(password_hash.startswith("$2b$"))

    def test_authenticate_user_accepts_valid_credentials(self):
        stored_hash = hash_password("Secret123!")
        collection = type(
            "UsersCollection",
            (),
            {"find_one": lambda self, query: {"_id": "x", "email": "user@example.com", "password_hash": stored_hash}},
        )()

        user = authenticate_user("user@example.com", "Secret123!", collection)
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "user@example.com")

    def test_authenticate_user_rejects_invalid_password(self):
        stored_hash = hash_password("Secret123!")
        collection = type(
            "UsersCollection",
            (),
            {"find_one": lambda self, query: {"_id": "x", "email": "user@example.com", "password_hash": stored_hash}},
        )()

        user = authenticate_user("user@example.com", "WrongPassword!", collection)
        self.assertIsNone(user)


if __name__ == "__main__":
    unittest.main()
