"""Appointments between patients and their connected doctor: request, accept/reject, expire,
cancel, reschedule and record the outcome.

Times are stored as naive UTC datetimes. A PENDING appointment, and a pending
reschedule proposal, temporarily reserve their slot until they are answered or
expire (24 hours, or the slot's start time if that is sooner). Expiry is applied
lazily whenever appointments are read or changed, so no background job is
needed.

Functions take the MongoDB collections as arguments so they can be unit tested
without a live database.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app_pages.availability_service import generate_slots, get_availability, to_local
from app_pages.practitioner_service import format_person_name, get_primary_practitioner_email

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"
STATUS_CANCELLED = "cancelled"
STATUS_COMPLETED = "completed"
STATUS_NO_SHOW = "no_show"
ACTIVE_STATUSES = [STATUS_PENDING, STATUS_CONFIRMED]
OUTCOME_STATUSES = [STATUS_COMPLETED, STATUS_NO_SHOW]

ROLE_PATIENT = "patient"
ROLE_DOCTOR = "doctor"

REQUEST_EXPIRY = timedelta(hours=24)
MAX_REASON_LENGTH = 500


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def _now(now: datetime | None) -> datetime:
    return now or datetime.utcnow()


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def _event(action: str, actor_email: str, now: datetime, details: str = "") -> dict:
    return {"action": action, "by": _normalize_email(actor_email), "at": now, "details": details}


def _with_event(appointment: dict, action: str, actor_email: str, now: datetime, details: str = "") -> list[dict]:
    return list(appointment.get("history") or []) + [_event(action, actor_email, now, details)]


def expiry_for(start: datetime, now: datetime) -> datetime:
    """A request or proposal expires after 24 hours, or at the slot's start if that is sooner."""
    return min(now + REQUEST_EXPIRY, start)


def format_slot(start: datetime, tz_name: str) -> str:
    local = to_local(start, tz_name)
    return f"{local:%a %b %d, %Y %I:%M %p} ({tz_name})"


def role_of(appointment: dict, email: str) -> str | None:
    email = _normalize_email(email)
    if email and email == appointment.get("patient_email"):
        return ROLE_PATIENT
    if email and email == appointment.get("doctor_email"):
        return ROLE_DOCTOR
    return None


def active_proposal(appointment: dict, now: datetime | None = None) -> dict | None:
    proposal = appointment.get("reschedule")
    if proposal and appointment.get("status") in ACTIVE_STATUSES and proposal["expires_at"] > _now(now):
        return proposal
    return None


def is_active(appointment: dict, now: datetime | None = None) -> bool:
    status = appointment.get("status")
    if status == STATUS_CONFIRMED:
        return True
    return status == STATUS_PENDING and appointment.get("expires_at") is not None and appointment["expires_at"] > _now(now)


# ---------------------------------------------------------------- expiry


def expire_stale(appointments_collection, now: datetime | None = None) -> None:
    """Mark overdue PENDING requests EXPIRED and drop overdue reschedule proposals, releasing their slots."""
    if appointments_collection is None:
        return
    now = _now(now)
    for appointment in appointments_collection.find({"status": {"$in": ACTIVE_STATUSES}}):
        if appointment["status"] == STATUS_PENDING and appointment.get("expires_at") and appointment["expires_at"] <= now:
            appointments_collection.update_one(
                {"_id": appointment["_id"], "status": STATUS_PENDING},
                {"$set": {
                    "status": STATUS_EXPIRED,
                    "reschedule": None,
                    "updated_at": now,
                    "history": _with_event(appointment, "expired", "system", now, "Request was not answered in time"),
                }},
            )
        elif appointment.get("reschedule") and appointment["reschedule"]["expires_at"] <= now:
            appointments_collection.update_one(
                {"_id": appointment["_id"]},
                {"$set": {
                    "reschedule": None,
                    "updated_at": now,
                    "history": _with_event(appointment, "reschedule_expired", "system", now,
                                           "Reschedule proposal was not answered in time"),
                }},
            )


# ---------------------------------------------------------------- reservations


def _reservations(appointments_collection, query: dict, now: datetime, exclude_id=None) -> list[dict]:
    """Slots held by active appointments and their pending proposals: {appointment_id, start, end, since}."""
    reservations = []
    for appointment in appointments_collection.find({**query, "status": {"$in": ACTIVE_STATUSES}}):
        if appointment["_id"] == exclude_id or not is_active(appointment, now):
            continue
        reservations.append({
            "appointment_id": appointment["_id"],
            "start": appointment["start_at"],
            "end": appointment["end_at"],
            "since": (appointment["created_at"], str(appointment["_id"])),
        })
        proposal = active_proposal(appointment, now)
        if proposal:
            reservations.append({
                "appointment_id": appointment["_id"],
                "start": proposal["start_at"],
                "end": proposal["end_at"],
                "since": (proposal["created_at"], str(appointment["_id"])),
            })
    return reservations


def doctor_busy(appointments_collection, doctor_email: str, now: datetime | None = None, exclude_id=None):
    """(start, end) intervals the doctor already has reserved, for slot generation."""
    if appointments_collection is None:
        return []
    return [
        (item["start"], item["end"])
        for item in _reservations(appointments_collection, {"doctor_email": _normalize_email(doctor_email)},
                                  _now(now), exclude_id)
    ]


def _patient_conflict(appointments_collection, patient_email: str, start, end, now, exclude_id=None) -> bool:
    return any(
        _overlaps(start, end, item["start"], item["end"])
        for item in _reservations(appointments_collection, {"patient_email": patient_email}, now, exclude_id)
    )


def _lost_race(appointments_collection, doctor_email: str, appointment_id, start, end, since, now) -> bool:
    """After writing a reservation, check nobody else reserved an overlapping slot first."""
    return any(
        _overlaps(start, end, item["start"], item["end"]) and item["since"] < since
        for item in _reservations(appointments_collection, {"doctor_email": doctor_email}, now)
        if item["appointment_id"] != appointment_id
    )


def check_slot(
    appointments_collection,
    availability_collection,
    doctor_email: str,
    start: datetime,
    now: datetime | None = None,
    exclude_id=None,
) -> tuple[datetime | None, str | None]:
    """Return (end, None) if ``start`` is a free, bookable slot for the doctor, else (None, error)."""
    now = _now(now)
    if start <= now:
        return None, "Appointments can't be booked in the past."
    availability = get_availability(availability_collection, doctor_email)
    if availability is None:
        return None, "This doctor hasn't set their availability yet."
    local_date = to_local(start, availability["timezone"]).date()
    busy = doctor_busy(appointments_collection, doctor_email, now, exclude_id)
    for slot_start, slot_end in generate_slots(availability, local_date, now, busy):
        if slot_start == start:
            return slot_end, None
    return None, "That time slot is not available. Please pick another one."


# ---------------------------------------------------------------- patient booking


def request_appointment(
    appointments_collection,
    availability_collection,
    users_collection,
    requests_collection,
    *,
    patient_user: dict,
    doctor_email: str,
    start: datetime,
    reason: str,
    now: datetime | None = None,
) -> tuple[dict | None, list[str]]:
    """A patient asks their connected doctor for a slot. The new appointment is PENDING."""
    if appointments_collection is None or availability_collection is None:
        return None, ["The database is not available right now."]
    now = _now(now)
    patient_email = _normalize_email((patient_user or {}).get("email"))
    doctor_email = _normalize_email(doctor_email)
    reason = (reason or "").strip()

    if get_primary_practitioner_email(users_collection, requests_collection, patient_email) != doctor_email:
        return None, ["You can only book appointments with your connected doctor."]
    if not reason:
        return None, ["Please enter the reason for the appointment."]
    if len(reason) > MAX_REASON_LENGTH:
        return None, [f"Please keep the reason under {MAX_REASON_LENGTH} characters."]

    expire_stale(appointments_collection, now)
    end, error = check_slot(appointments_collection, availability_collection, doctor_email, start, now)
    if error:
        return None, [error]
    if _patient_conflict(appointments_collection, patient_email, start, end, now):
        return None, ["You already have an active appointment that overlaps this time."]

    availability = get_availability(availability_collection, doctor_email)
    doctor = users_collection.find_one({"email": doctor_email}) or {}
    appointment = {
        "patient_email": patient_email,
        "patient_id": patient_user.get("_id"),
        "patient_name": format_person_name(patient_user),
        "doctor_email": doctor_email,
        "doctor_id": doctor.get("_id"),
        "doctor_name": format_person_name(doctor, doctor=True),
        "start_at": start,
        "end_at": end,
        "duration_minutes": int((end - start).total_seconds() // 60),
        "timezone": availability["timezone"],
        "reason": reason,
        "status": STATUS_PENDING,
        "expires_at": expiry_for(start, now),
        "reschedule": None,
        "created_at": now,
        "updated_at": now,
        "history": [_event("requested", patient_email, now, format_slot(start, availability["timezone"]))],
    }
    appointment["_id"] = appointments_collection.insert_one(appointment).inserted_id

    if _lost_race(appointments_collection, doctor_email, appointment["_id"], start, end,
                  (now, str(appointment["_id"])), now):
        appointments_collection.delete_one({"_id": appointment["_id"]})
        return None, ["That time slot was just taken. Please pick another one."]
    return appointment, []


# ---------------------------------------------------------------- doctor decisions


def _load(appointments_collection, appointment_id, now) -> dict | None:
    if appointments_collection is None:
        return None
    expire_stale(appointments_collection, now)
    return appointments_collection.find_one({"_id": appointment_id})


def accept_appointment(appointments_collection, appointment_id, doctor_email: str, now: datetime | None = None) -> list[str]:
    """PENDING -> CONFIRMED. Only the requested doctor, and only before the request expires."""
    now = _now(now)
    appointment = _load(appointments_collection, appointment_id, now)
    if appointment is None or appointment.get("doctor_email") != _normalize_email(doctor_email):
        return ["Only the requested doctor can accept this appointment."]
    if appointment["status"] == STATUS_EXPIRED:
        return ["This request has expired and can no longer be accepted."]
    if appointment["status"] != STATUS_PENDING:
        return ["Only pending requests can be accepted."]

    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": STATUS_PENDING},
        {"$set": {
            "status": STATUS_CONFIRMED,
            "confirmed_at": now,
            "expires_at": None,
            "updated_at": now,
            "history": _with_event(appointment, "confirmed", doctor_email, now),
        }},
    )
    return [] if result.matched_count else ["Only pending requests can be accepted."]


def reject_appointment(
    appointments_collection, appointment_id, doctor_email: str, reason: str = "", now: datetime | None = None
) -> list[str]:
    """PENDING -> REJECTED, releasing the slot. Only the requested doctor; the reason is optional."""
    now = _now(now)
    appointment = _load(appointments_collection, appointment_id, now)
    if appointment is None or appointment.get("doctor_email") != _normalize_email(doctor_email):
        return ["Only the requested doctor can reject this appointment."]
    if appointment["status"] != STATUS_PENDING:
        return ["Only pending requests can be rejected."]

    reason = (reason or "").strip()
    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": STATUS_PENDING},
        {"$set": {
            "status": STATUS_REJECTED,
            "rejection_reason": reason,
            "reschedule": None,
            "updated_at": now,
            "history": _with_event(appointment, "rejected", doctor_email, now, reason),
        }},
    )
    return [] if result.matched_count else ["Only pending requests can be rejected."]


def cancel_appointment(
    appointments_collection, appointment_id, actor_email: str, reason: str = "", now: datetime | None = None
) -> list[str]:
    """Either party cancels a future PENDING or CONFIRMED appointment, releasing its slot."""
    now = _now(now)
    appointment = _load(appointments_collection, appointment_id, now)
    role = role_of(appointment or {}, actor_email)
    if appointment is None or role is None:
        return ["Appointment not found."]
    if appointment["status"] not in ACTIVE_STATUSES:
        return ["Only pending or confirmed appointments can be cancelled."]
    if appointment["start_at"] <= now:
        return ["Appointments that have already started can't be cancelled."]

    reason = (reason or "").strip()
    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": appointment["status"]},
        {"$set": {
            "status": STATUS_CANCELLED,
            "cancelled_by": role,
            "cancellation_reason": reason,
            "reschedule": None,
            "updated_at": now,
            "history": _with_event(appointment, "cancelled", actor_email, now, reason),
        }},
    )
    return [] if result.matched_count else ["Only pending or confirmed appointments can be cancelled."]


def record_outcome(
    appointments_collection, appointment_id, doctor_email: str, outcome: str, now: datetime | None = None
) -> list[str]:
    """After a CONFIRMED appointment's start time, its doctor marks it COMPLETED or NO_SHOW."""
    now = _now(now)
    if outcome not in OUTCOME_STATUSES:
        return ["Unknown outcome."]
    appointment = _load(appointments_collection, appointment_id, now)
    if appointment is None or appointment.get("doctor_email") != _normalize_email(doctor_email):
        return ["Only the appointment's doctor can record the outcome."]
    if appointment["status"] != STATUS_CONFIRMED:
        return ["Only confirmed appointments can be marked completed or no-show."]
    if appointment["start_at"] > now:
        return ["You can record the outcome once the appointment has started."]

    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": STATUS_CONFIRMED},
        {"$set": {
            "status": outcome,
            "outcome_at": now,
            "reschedule": None,
            "updated_at": now,
            "history": _with_event(appointment, outcome, doctor_email, now),
        }},
    )
    return [] if result.matched_count else ["Only confirmed appointments can be marked completed or no-show."]


# ---------------------------------------------------------------- rescheduling


def propose_reschedule(
    appointments_collection,
    availability_collection,
    appointment_id,
    actor_email: str,
    new_start: datetime,
    now: datetime | None = None,
) -> list[str]:
    """Either party proposes a new slot. The original stays unchanged and the new slot is held until answered."""
    now = _now(now)
    appointment = _load(appointments_collection, appointment_id, now)
    role = role_of(appointment or {}, actor_email)
    if appointment is None or role is None:
        return ["Appointment not found."]
    if appointment["status"] not in ACTIVE_STATUSES or appointment["start_at"] <= now:
        return ["Only future pending or confirmed appointments can be rescheduled."]
    if active_proposal(appointment, now):
        return ["A reschedule proposal is already waiting for a response."]
    if new_start == appointment["start_at"]:
        return ["Pick a different time from the current one."]

    end, error = check_slot(appointments_collection, availability_collection, appointment["doctor_email"], new_start, now)
    if error:
        return [error]
    if _patient_conflict(appointments_collection, appointment["patient_email"], new_start, end, now,
                         exclude_id=appointment["_id"]):
        return ["The patient already has an active appointment that overlaps this time."]

    proposal = {
        "proposed_by": role,
        "proposed_by_email": _normalize_email(actor_email),
        "start_at": new_start,
        "end_at": end,
        "created_at": now,
        "expires_at": expiry_for(new_start, now),
    }
    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": appointment["status"], "reschedule": None},
        {"$set": {
            "reschedule": proposal,
            "updated_at": now,
            "history": _with_event(appointment, "reschedule_proposed", actor_email, now,
                                   format_slot(new_start, appointment["timezone"])),
        }},
    )
    if not result.matched_count:
        return ["This appointment changed. Please try again."]

    if _lost_race(appointments_collection, appointment["doctor_email"], appointment["_id"], new_start, end,
                  (now, str(appointment["_id"])), now):
        appointments_collection.update_one({"_id": appointment["_id"]}, {"$set": {"reschedule": None}})
        return ["That time slot was just taken. Please pick another one."]
    return []


def respond_to_reschedule(
    appointments_collection,
    availability_collection,
    appointment_id,
    actor_email: str,
    accept: bool,
    now: datetime | None = None,
) -> list[str]:
    """The other party accepts (move to the new slot, release the old one) or rejects the proposal.

    Accepting a proposal on a PENDING appointment also confirms it, since both
    parties have now agreed on the time.
    """
    now = _now(now)
    appointment = _load(appointments_collection, appointment_id, now)
    role = role_of(appointment or {}, actor_email)
    proposal = active_proposal(appointment or {}, now)
    if appointment is None or role is None:
        return ["Appointment not found."]
    if proposal is None:
        return ["There is no reschedule proposal waiting for a response."]
    if proposal["proposed_by"] == role:
        return ["The other party has to respond to your proposal."]

    if not accept:
        appointments_collection.update_one(
            {"_id": appointment["_id"]},
            {"$set": {
                "reschedule": None,
                "updated_at": now,
                "history": _with_event(appointment, "reschedule_rejected", actor_email, now),
            }},
        )
        return []

    if _patient_conflict(appointments_collection, appointment["patient_email"], proposal["start_at"],
                         proposal["end_at"], now, exclude_id=appointment["_id"]):
        return ["The patient now has another appointment at that time."]
    if any(
        _overlaps(proposal["start_at"], proposal["end_at"], start, end)
        for start, end in doctor_busy(appointments_collection, appointment["doctor_email"], now,
                                      exclude_id=appointment["_id"])
    ):
        return ["That time slot is no longer available."]

    old_slot = format_slot(appointment["start_at"], appointment["timezone"])
    new_slot = format_slot(proposal["start_at"], appointment["timezone"])
    history = _with_event(appointment, "rescheduled", actor_email, now, f"{old_slot} -> {new_slot}")
    fields = {
        "start_at": proposal["start_at"],
        "end_at": proposal["end_at"],
        "duration_minutes": int((proposal["end_at"] - proposal["start_at"]).total_seconds() // 60),
        "reschedule": None,
        "updated_at": now,
    }
    if appointment["status"] == STATUS_PENDING:
        fields.update({"status": STATUS_CONFIRMED, "confirmed_at": now, "expires_at": None})
        history.append(_event("confirmed", actor_email, now, "Confirmed by accepting the new time"))
    fields["history"] = history
    result = appointments_collection.update_one(
        {"_id": appointment["_id"], "status": appointment["status"]}, {"$set": fields}
    )
    return [] if result.matched_count else ["This appointment changed. Please try again."]


# ---------------------------------------------------------------- lists


def _sorted(appointments, newest_first=False):
    return sorted(appointments, key=lambda appointment: appointment["start_at"], reverse=newest_first)


def list_for_patient(appointments_collection, patient_email: str, now: datetime | None = None):
    """(upcoming, history) for the patient. Upcoming = future pending/confirmed, soonest first."""
    patient_email = _normalize_email(patient_email)
    if appointments_collection is None or not patient_email:
        return [], []
    now = _now(now)
    expire_stale(appointments_collection, now)
    appointments = list(appointments_collection.find({"patient_email": patient_email}))
    upcoming = [a for a in appointments if a["status"] in ACTIVE_STATUSES and a["start_at"] > now]
    history = [a for a in appointments if a not in upcoming]
    return _sorted(upcoming), _sorted(history, newest_first=True)


def list_for_doctor(appointments_collection, doctor_email: str, now: datetime | None = None):
    """(requests, upcoming, history) for the doctor.

    Requests = pending, soonest first. Upcoming = future confirmed. History =
    everything else, with confirmed appointments awaiting an outcome first.
    """
    doctor_email = _normalize_email(doctor_email)
    if appointments_collection is None or not doctor_email:
        return [], [], []
    now = _now(now)
    expire_stale(appointments_collection, now)
    appointments = list(appointments_collection.find({"doctor_email": doctor_email}))
    requests = [a for a in appointments if a["status"] == STATUS_PENDING]
    upcoming = [a for a in appointments if a["status"] == STATUS_CONFIRMED and a["start_at"] > now]
    awaiting = [a for a in appointments if a["status"] == STATUS_CONFIRMED and a["start_at"] <= now]
    rest = [a for a in appointments if a["status"] not in ACTIVE_STATUSES]
    return _sorted(requests), _sorted(upcoming), _sorted(awaiting, newest_first=True) + _sorted(rest, newest_first=True)
