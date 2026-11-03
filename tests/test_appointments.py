import unittest
from datetime import date, datetime, timedelta

from app_pages.appointment_service import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_NO_SHOW,
    STATUS_PENDING,
    STATUS_REJECTED,
    accept_appointment,
    cancel_appointment,
    doctor_busy,
    list_for_doctor,
    list_for_patient,
    propose_reschedule,
    record_outcome,
    reject_appointment,
    request_appointment,
    respond_to_reschedule,
)
from app_pages.availability_service import (
    available_dates,
    default_availability,
    generate_slots,
    save_availability,
    validate_availability,
)
from tests.test_practitioner import FakeCollection

NOW = datetime(2026, 11, 2, 12, 0)  # Monday 07:00 in New York (EST, UTC-5)
TUESDAY = date(2026, 11, 3)
TUE_9AM = datetime(2026, 11, 3, 14, 0)  # 09:00 EST in UTC
TUE_930 = datetime(2026, 11, 3, 14, 30)
TUE_10AM = datetime(2026, 11, 3, 15, 0)

DOCTOR = {"_id": 1, "email": "doc@example.com", "role": "Doctor", "first_name": "Ann", "last_name": "Ito"}
PATIENT = {"_id": 2, "email": "pat@example.com", "role": "Patient", "first_name": "Pat", "last_name": "Lee",
           "primary_doctor_email": "doc@example.com"}
PATIENT_2 = {"_id": 3, "email": "sam@example.com", "role": "Patient", "first_name": "Sam", "last_name": "Kim",
             "primary_doctor_email": "doc@example.com"}
STRANGER = {"_id": 4, "email": "eve@example.com", "role": "Patient", "first_name": "Eve"}


def _availability(**overrides):
    availability = default_availability("doc@example.com")
    availability.update(timezone="America/New_York", slot_minutes=30, break_minutes=0)
    for day in range(5):
        availability["weekly"][str(day)] = [{"start": "09:00", "end": "12:00"}, {"start": "13:00", "end": "17:00"}]
    availability.update(overrides)
    return availability


class AvailabilityTests(unittest.TestCase):
    def test_valid_settings(self):
        self.assertEqual(validate_availability(_availability()), [])

    def test_rejects_overlap_reversed_times_short_intervals_and_bad_values(self):
        availability = _availability(slot_minutes=60, break_minutes=-5, timezone="Mars/Base")
        availability["weekly"]["0"] = [{"start": "09:00", "end": "12:00"}, {"start": "11:00", "end": "13:00"}]
        availability["weekly"]["1"] = [{"start": "12:00", "end": "09:00"}]
        availability["weekly"]["2"] = [{"start": "09:00", "end": "09:30"}]
        availability["blocked"] = [{"start": "2026-11-05T10:00", "end": "2026-11-05T09:00"}]
        errors = " | ".join(validate_availability(availability))

        for expected in ["valid timezone", "Break", "Monday: 11:00-13:00 overlaps",
                         "Tuesday: start time 12:00 must be before", "Wednesday: 09:00-09:30 is shorter",
                         "must end after it starts"]:
            self.assertIn(expected, errors)
        self.assertIn("must be one of", " ".join(validate_availability(_availability(slot_minutes=20))))

    def test_touching_intervals_are_allowed(self):
        availability = _availability()
        availability["weekly"]["0"] = [{"start": "09:00", "end": "12:00"}, {"start": "12:00", "end": "13:00"}]
        self.assertEqual(validate_availability(availability), [])

    def test_slots_respect_duration_break_blocks_and_busy(self):
        availability = _availability(slot_minutes=45, break_minutes=15)
        availability["weekly"]["1"] = [{"start": "09:00", "end": "11:30"}]
        availability["blocked"] = [{"start": "2026-11-03T10:00", "end": "2026-11-03T10:30"}]

        slots = generate_slots(availability, TUESDAY, NOW)
        # 09:00-09:45, (10:00 blocked), 11:00 would end 11:45 > 11:30 -> only one slot.
        self.assertEqual(slots, [(TUE_9AM, TUE_9AM + timedelta(minutes=45))])
        self.assertEqual(generate_slots(availability, TUESDAY, NOW, busy=[(TUE_9AM, TUE_930)]), [])

    def test_past_slots_and_blocked_days_are_not_offered(self):
        availability = _availability()
        today = generate_slots(availability, date(2026, 11, 2), datetime(2026, 11, 2, 21, 0))  # 16:00 EST
        self.assertEqual([start.hour for start, _ in today], [21])  # only 16:30 EST is left
        availability["blocked"] = [{"start": "2026-11-03T00:00", "end": "2026-11-04T00:00", "reason": "Holiday"}]
        self.assertNotIn(TUESDAY, available_dates(availability, NOW))
        self.assertIn(date(2026, 11, 4), available_dates(availability, NOW))
        self.assertNotIn(date(2026, 11, 7), available_dates(availability, NOW))  # Saturday

    def test_save_is_per_doctor_and_updates_in_place(self):
        collection = FakeCollection()
        self.assertEqual(save_availability(collection, DOCTOR, _availability()), [])
        self.assertEqual(save_availability(collection, DOCTOR, _availability(slot_minutes=60)), [])
        self.assertEqual(len(collection.docs), 1)
        self.assertEqual(collection.docs[0]["slot_minutes"], 60)
        self.assertEqual(collection.docs[0]["doctor_id"], 1)
        self.assertTrue(save_availability(collection, DOCTOR, _availability(slot_minutes=7)))


class AppointmentTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeCollection([DOCTOR, PATIENT, PATIENT_2, STRANGER])
        self.requests = FakeCollection()
        self.availability = FakeCollection()
        save_availability(self.availability, DOCTOR, _availability())
        self.appointments = FakeCollection()

    def _request(self, start=TUE_9AM, patient=PATIENT, now=NOW, reason="Follow-up"):
        return request_appointment(
            self.appointments, self.availability, self.users, self.requests,
            patient_user=patient, doctor_email="doc@example.com", start=start, reason=reason, now=now,
        )

    def _get(self, appointment):
        return self.appointments.find_one({"_id": appointment["_id"]})

    def test_request_creates_pending_with_expiry(self):
        appointment, errors = self._request()

        self.assertEqual(errors, [])
        stored = self._get(appointment)
        self.assertEqual(stored["status"], STATUS_PENDING)
        self.assertEqual((stored["start_at"], stored["end_at"]), (TUE_9AM, TUE_930))
        self.assertEqual(stored["duration_minutes"], 30)
        self.assertEqual(stored["expires_at"], NOW + timedelta(hours=24))
        self.assertEqual(stored["doctor_name"], "Dr. Ann Ito")
        self.assertEqual(stored["timezone"], "America/New_York")

    def test_request_expires_at_start_when_sooner(self):
        appointment, _ = self._request(start=datetime(2026, 11, 2, 15, 0))  # today 10:00 EST
        self.assertEqual(self._get(appointment)["expires_at"], datetime(2026, 11, 2, 15, 0))

    def test_request_rules(self):
        self.assertIn("connected doctor", self._request(patient=STRANGER)[1][0])
        self.assertIn("reason", self._request(reason="  ")[1][0])
        self.assertIn("past", self._request(start=NOW - timedelta(hours=1))[1][0])
        self.assertIn("not available", self._request(start=datetime(2026, 11, 3, 14, 10))[1][0])  # off-grid
        self.assertIn("not available", self._request(start=datetime(2026, 11, 7, 14, 0))[1][0])  # Saturday

    def test_pending_reserves_slot_and_patient_cannot_double_book(self):
        self._request()
        self.assertIn("not available", self._request(patient=PATIENT_2)[1][0])
        self.assertNotIn((TUE_9AM, TUE_930), generate_slots(
            self.availability.docs[0], TUESDAY, NOW, doctor_busy(self.appointments, "doc@example.com", NOW)))

    def test_patient_cannot_hold_overlapping_appointments_across_doctors(self):
        self._request()
        # Same patient, another doctor at the same time: build a second doctor with the same hours.
        other = {"_id": 9, "email": "other@example.com", "role": "Doctor", "first_name": "Ben"}
        self.users.insert_one(other)
        save_availability(self.availability, other, _availability())
        self.users.update_one({"email": "pat@example.com"}, {"$set": {"primary_doctor_email": "other@example.com"}})
        _, errors = request_appointment(
            self.appointments, self.availability, self.users, self.requests,
            patient_user=PATIENT, doctor_email="other@example.com", start=TUE_9AM, reason="x", now=NOW,
        )
        self.assertIn("overlaps", errors[0])

    def test_accept_and_reject(self):
        first, _ = self._request()
        second, _ = self._request(start=TUE_10AM, patient=PATIENT_2)

        self.assertIn("Only the requested doctor", accept_appointment(self.appointments, first["_id"], "x@example.com", NOW)[0])
        self.assertEqual(accept_appointment(self.appointments, first["_id"], "doc@example.com", NOW), [])
        self.assertEqual(self._get(first)["status"], STATUS_CONFIRMED)
        self.assertIsNone(self._get(first)["expires_at"])

        self.assertEqual(reject_appointment(self.appointments, second["_id"], "doc@example.com", "Fully booked", NOW), [])
        self.assertEqual(self._get(second)["status"], STATUS_REJECTED)
        self.assertEqual(self._get(second)["rejection_reason"], "Fully booked")
        # The rejected slot is free again; the confirmed one stays reserved.
        self.assertEqual(self._request(start=TUE_10AM)[1], [])
        self.assertIn("not available", self._request(start=TUE_9AM, patient=PATIENT_2)[1][0])

    def test_expired_request_releases_slot_and_cannot_be_accepted(self):
        appointment, _ = self._request()
        later = NOW + timedelta(hours=25)

        self.assertIn("expired", accept_appointment(self.appointments, appointment["_id"], "doc@example.com", later)[0])
        self.assertEqual(self._get(appointment)["status"], STATUS_EXPIRED)
        self.assertEqual(self._request(patient=PATIENT_2, now=later)[1], [])
        self.assertEqual([entry["action"] for entry in self._get(appointment)["history"]], ["requested", "expired"])

    def test_cancel(self):
        appointment, _ = self._request()
        self.assertEqual(cancel_appointment(self.appointments, appointment["_id"], "eve@example.com", "", NOW),
                         ["Appointment not found."])
        self.assertEqual(cancel_appointment(self.appointments, appointment["_id"], "pat@example.com", "Feeling better", NOW), [])
        stored = self._get(appointment)
        self.assertEqual((stored["status"], stored["cancelled_by"]), (STATUS_CANCELLED, "patient"))
        self.assertEqual(self._request(patient=PATIENT_2)[1], [])

    def test_reschedule_proposal_holds_new_slot_until_accepted(self):
        appointment, _ = self._request()
        accept_appointment(self.appointments, appointment["_id"], "doc@example.com", NOW)

        self.assertEqual(propose_reschedule(self.appointments, self.availability, appointment["_id"],
                                            "pat@example.com", TUE_10AM, NOW), [])
        stored = self._get(appointment)
        self.assertEqual(stored["start_at"], TUE_9AM)  # unchanged until accepted
        self.assertIn("not available", self._request(start=TUE_10AM, patient=PATIENT_2)[1][0])  # new slot held
        self.assertIn("already waiting", propose_reschedule(self.appointments, self.availability, appointment["_id"],
                                                            "doc@example.com", TUE_930, NOW)[0])
        self.assertIn("other party", respond_to_reschedule(self.appointments, self.availability, appointment["_id"],
                                                           "pat@example.com", True, NOW)[0])

        self.assertEqual(respond_to_reschedule(self.appointments, self.availability, appointment["_id"],
                                               "doc@example.com", True, NOW), [])
        stored = self._get(appointment)
        self.assertEqual((stored["start_at"], stored["status"], stored["reschedule"]), (TUE_10AM, STATUS_CONFIRMED, None))
        self.assertEqual(self._request(start=TUE_9AM, patient=PATIENT_2)[1], [])  # original released

    def test_rejected_or_expired_proposal_releases_new_slot(self):
        appointment, _ = self._request()
        propose_reschedule(self.appointments, self.availability, appointment["_id"], "doc@example.com", TUE_10AM, NOW)
        self.assertEqual(respond_to_reschedule(self.appointments, self.availability, appointment["_id"],
                                               "pat@example.com", False, NOW), [])
        self.assertIsNone(self._get(appointment)["reschedule"])
        self.assertEqual(self._get(appointment)["status"], STATUS_PENDING)

        propose_reschedule(self.appointments, self.availability, appointment["_id"], "pat@example.com", TUE_10AM, NOW)
        later = NOW + timedelta(hours=1)
        self.assertEqual(self._request(start=TUE_10AM, patient=PATIENT_2, now=later)[1][0][:4], "That")
        # Proposal on the pending appointment expires 24h later, along with the request itself.
        self.assertEqual(self._request(start=TUE_10AM, patient=PATIENT_2, now=NOW + timedelta(hours=25))[1], [])

    def test_accepting_proposal_on_pending_appointment_confirms_it(self):
        appointment, _ = self._request()
        propose_reschedule(self.appointments, self.availability, appointment["_id"], "pat@example.com", TUE_10AM, NOW)
        respond_to_reschedule(self.appointments, self.availability, appointment["_id"], "doc@example.com", True, NOW)
        stored = self._get(appointment)
        self.assertEqual((stored["status"], stored["start_at"]), (STATUS_CONFIRMED, TUE_10AM))

    def test_outcome_only_after_start(self):
        appointment, _ = self._request()
        self.assertIn("confirmed", record_outcome(self.appointments, appointment["_id"], "doc@example.com",
                                                  STATUS_COMPLETED, NOW)[0])
        accept_appointment(self.appointments, appointment["_id"], "doc@example.com", NOW)
        self.assertIn("started", record_outcome(self.appointments, appointment["_id"], "doc@example.com",
                                                STATUS_COMPLETED, NOW)[0])
        after = TUE_9AM + timedelta(minutes=5)
        self.assertIn("Only the appointment's doctor", record_outcome(self.appointments, appointment["_id"],
                                                                      "pat@example.com", STATUS_NO_SHOW, after)[0])
        self.assertEqual(record_outcome(self.appointments, appointment["_id"], "doc@example.com", STATUS_NO_SHOW, after), [])
        self.assertEqual(self._get(appointment)["status"], STATUS_NO_SHOW)

    def test_lists(self):
        pending, _ = self._request()
        confirmed, _ = self._request(start=TUE_10AM, patient=PATIENT_2)
        accept_appointment(self.appointments, confirmed["_id"], "doc@example.com", NOW)
        rejected, _ = self._request(start=TUE_930, patient=PATIENT_2)
        reject_appointment(self.appointments, rejected["_id"], "doc@example.com", "", NOW)

        requests, upcoming, history = list_for_doctor(self.appointments, "doc@example.com", NOW)
        self.assertEqual([a["_id"] for a in requests], [pending["_id"]])
        self.assertEqual([a["_id"] for a in upcoming], [confirmed["_id"]])
        self.assertEqual([a["_id"] for a in history], [rejected["_id"]])

        upcoming, history = list_for_patient(self.appointments, "sam@example.com", NOW)
        self.assertEqual([a["_id"] for a in upcoming], [confirmed["_id"]])
        self.assertEqual([a["_id"] for a in history], [rejected["_id"]])

        after = TUE_10AM + timedelta(minutes=1)
        _, upcoming, history = list_for_doctor(self.appointments, "doc@example.com", after)
        self.assertEqual(upcoming, [])
        self.assertEqual(history[0]["_id"], confirmed["_id"])  # awaiting outcome first


if __name__ == "__main__":
    unittest.main()
