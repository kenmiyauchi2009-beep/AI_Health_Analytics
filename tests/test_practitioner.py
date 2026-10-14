import itertools
import unittest
from datetime import datetime, timedelta

from app_pages.practitioner_service import (
    REQUEST_TYPE_CHANGE,
    REQUEST_TYPE_ENROLL,
    cancel_practitioner_request,
    get_pending_practitioner_request,
    get_primary_practitioner_email,
    get_unseen_decisions,
    list_doctors,
    mark_decisions_seen,
    request_primary_practitioner,
    respond_to_practitioner_request,
)


class _Result:
    def __init__(self, matched_count=0, inserted_id=None):
        self.matched_count = matched_count
        self.inserted_id = inserted_id


class _Cursor(list):
    def sort(self, field, direction=1):
        return _Cursor(sorted(self, key=lambda doc: doc.get(field) or datetime.min, reverse=direction < 0))


def _matches(doc, query):
    for field, expected in query.items():
        value = doc.get(field)
        if isinstance(expected, dict):
            if "$in" in expected and value not in expected["$in"]:
                return False
            if "$ne" in expected and value == expected["$ne"]:
                return False
        elif value != expected:
            return False
    return True


class FakeCollection:
    """Minimal in-memory stand-in for the pymongo calls the service makes."""

    _ids = itertools.count(1)

    def __init__(self, docs=None):
        self.docs = [dict(doc, _id=doc.get("_id", next(self._ids))) for doc in (docs or [])]

    def find(self, query=None):
        return _Cursor(dict(doc) for doc in self.docs if _matches(doc, query or {}))

    def find_one(self, query):
        found = self.find(query)
        return found[0] if found else None

    def insert_one(self, doc):
        doc["_id"] = next(self._ids)
        self.docs.append(dict(doc))
        return _Result(inserted_id=doc["_id"])

    def update_one(self, query, update):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update["$set"])
                return _Result(matched_count=1)
        return _Result()

    def update_many(self, query, update):
        matched = [doc for doc in self.docs if _matches(doc, query)]
        for doc in matched:
            doc.update(update["$set"])
        return _Result(matched_count=len(matched))


PATIENT = {"email": "pat@example.com", "role": "Patient", "first_name": "Pat", "last_name": "Lee"}
DOCTOR_A = {"email": "a@example.com", "role": "Doctor", "first_name": "Ann", "last_name": "Ito", "speciality": "Cardiology", "degree": "MD"}
DOCTOR_B = {"email": "b@example.com", "role": "Doctor", "first_name": "Ben", "last_name": "Ota", "speciality": "Family Medicine", "degree": "MBBS"}


class PrimaryPractitionerTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeCollection([PATIENT, DOCTOR_A, DOCTOR_B])
        self.requests = FakeCollection()

    def _request(self, doctor_email):
        return request_primary_practitioner(self.users, self.requests, PATIENT, doctor_email)

    def _respond(self, request, doctor_email, accept):
        return respond_to_practitioner_request(self.users, self.requests, request["_id"], doctor_email, accept)

    def test_list_doctors_returns_only_doctors(self):
        emails = [doctor["email"] for doctor in list_doctors(self.users)]
        self.assertEqual(emails, ["a@example.com", "b@example.com"])

    def test_first_request_is_an_enrollment_sent_to_that_doctor(self):
        request, error = self._request("a@example.com")
        self.assertIsNone(error)
        self.assertEqual(request["request_type"], REQUEST_TYPE_ENROLL)
        self.assertEqual(request["doctor_email"], "a@example.com")
        self.assertEqual(request["status"], "pending")

    def test_only_one_pending_request_at_a_time(self):
        self._request("a@example.com")
        request, error = self._request("b@example.com")
        self.assertIsNone(request)
        self.assertIn("pending", error)

    def test_cannot_request_non_doctor(self):
        request, error = self._request("pat@example.com")
        self.assertIsNone(request)
        self.assertIsNotNone(error)

    def test_accept_sets_primary_practitioner_and_notifies_patient(self):
        request, _ = self._request("a@example.com")
        self.assertTrue(self._respond(request, "a@example.com", accept=True))

        self.assertEqual(get_primary_practitioner_email(self.users, self.requests, "pat@example.com"), "a@example.com")
        unseen = get_unseen_decisions(self.requests, "pat@example.com")
        self.assertEqual([decision["status"] for decision in unseen], ["accepted"])

        mark_decisions_seen(self.requests, "pat@example.com")
        self.assertEqual(get_unseen_decisions(self.requests, "pat@example.com"), [])

    def test_decline_notifies_patient_and_leaves_no_practitioner(self):
        request, _ = self._request("a@example.com")
        self.assertTrue(self._respond(request, "a@example.com", accept=False))

        self.assertIsNone(get_primary_practitioner_email(self.users, self.requests, "pat@example.com"))
        unseen = get_unseen_decisions(self.requests, "pat@example.com")
        self.assertEqual([decision["status"] for decision in unseen], ["declined"])
        # Patient may now try another doctor.
        _, error = self._request("b@example.com")
        self.assertIsNone(error)

    def test_other_doctor_cannot_respond(self):
        request, _ = self._request("a@example.com")
        self.assertFalse(self._respond(request, "b@example.com", accept=True))
        self.assertIsNotNone(get_pending_practitioner_request(self.requests, "pat@example.com"))

    def test_change_replaces_previous_practitioner(self):
        first, _ = self._request("a@example.com")
        self._respond(first, "a@example.com", accept=True)

        _, error = self._request("a@example.com")
        self.assertIn("already", error)

        second, error = self._request("b@example.com")
        self.assertIsNone(error)
        self.assertEqual(second["request_type"], REQUEST_TYPE_CHANGE)
        self.assertEqual(second["previous_doctor_email"], "a@example.com")

        self._respond(second, "b@example.com", accept=True)
        self.assertEqual(get_primary_practitioner_email(self.users, self.requests, "pat@example.com"), "b@example.com")
        # Old doctor's relationship is ended, so only one accepted connection remains.
        accepted = self.requests.find({"patient_email": "pat@example.com", "status": "accepted"})
        self.assertEqual([request["doctor_email"] for request in accepted], ["b@example.com"])

    def test_declined_change_keeps_current_practitioner(self):
        first, _ = self._request("a@example.com")
        self._respond(first, "a@example.com", accept=True)
        second, _ = self._request("b@example.com")
        self._respond(second, "b@example.com", accept=False)
        self.assertEqual(get_primary_practitioner_email(self.users, self.requests, "pat@example.com"), "a@example.com")

    def test_patient_can_cancel_pending_request(self):
        request, _ = self._request("a@example.com")
        self.assertTrue(cancel_practitioner_request(self.requests, request["_id"], "pat@example.com"))
        self.assertIsNone(get_pending_practitioner_request(self.requests, "pat@example.com"))
        self.assertFalse(self._respond(request, "a@example.com", accept=True))

    def test_legacy_accepted_request_counts_as_primary(self):
        self.requests.insert_one({
            "patient_email": "pat@example.com",
            "doctor_email": "a@example.com",
            "status": "accepted",
            "updated_at": datetime.utcnow() - timedelta(days=1),
        })
        self.assertEqual(get_primary_practitioner_email(self.users, self.requests, "pat@example.com"), "a@example.com")


if __name__ == "__main__":
    unittest.main()
