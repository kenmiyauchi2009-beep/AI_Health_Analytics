"""Data access for the patient -> Primary Health Practitioner (PHP) enrollment flow.

Functions take the MongoDB collections as arguments so they can be unit tested
without a live database. A patient has at most one PHP (stored on the patient's
user document as ``primary_doctor_email``) and at most one pending request.
"""

from __future__ import annotations

from datetime import datetime

from app_pages.registration_page import normalize_user_record

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUS_CANCELLED = "cancelled"
# An accepted relationship that ended because the patient moved to another doctor.
STATUS_REPLACED = "replaced"

REQUEST_TYPE_ENROLL = "enroll"
REQUEST_TYPE_CHANGE = "change"


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def format_person_name(user: dict | None, *, doctor: bool = False) -> str:
    """Return a display name for a user record, falling back to the email."""
    if not isinstance(user, dict):
        return "Doctor" if doctor else "Patient"
    name = f"{str(user.get('first_name') or '').strip()} {str(user.get('last_name') or '').strip()}".strip()
    if not name:
        return str(user.get("email") or ("Doctor" if doctor else "Patient"))
    return f"Dr. {name}" if doctor and not name.lower().startswith("dr") else name


def list_doctors(users_collection) -> list[dict]:
    """Return every registered doctor, sorted by name."""
    if users_collection is None:
        return []
    doctors = []
    for record in users_collection.find({}):
        normalized = normalize_user_record(dict(record))
        if normalized and normalized.get("role") == "Doctor" and normalized.get("email"):
            doctors.append(normalized)
    doctors.sort(key=lambda doctor: format_person_name(doctor, doctor=True).lower())
    return doctors


def get_primary_practitioner_email(users_collection, requests_collection, patient_email: str) -> str | None:
    """Return the email of the patient's current PHP, if any."""
    patient_email = _normalize_email(patient_email)
    if not patient_email or users_collection is None:
        return None

    patient = users_collection.find_one({"email": patient_email}) or {}
    primary_email = _normalize_email(patient.get("primary_doctor_email"))
    if primary_email:
        return primary_email

    # Legacy fallback: connections accepted before primary_doctor_email existed.
    if requests_collection is None:
        return None
    accepted = list(
        requests_collection.find({"patient_email": patient_email, "status": STATUS_ACCEPTED}).sort("updated_at", -1)
    )
    return _normalize_email(accepted[0].get("doctor_email")) if accepted else None


def get_primary_practitioner(users_collection, requests_collection, patient_email: str) -> dict | None:
    """Return the patient's current PHP user record, if any."""
    doctor_email = get_primary_practitioner_email(users_collection, requests_collection, patient_email)
    if not doctor_email:
        return None
    doctor = users_collection.find_one({"email": doctor_email})
    return normalize_user_record(dict(doctor)) if doctor else None


def get_pending_practitioner_request(requests_collection, patient_email: str) -> dict | None:
    """Return the patient's pending PHP request, if any."""
    patient_email = _normalize_email(patient_email)
    if requests_collection is None or not patient_email:
        return None
    return requests_collection.find_one({"patient_email": patient_email, "status": STATUS_PENDING})


def get_patient_request_history(requests_collection, patient_email: str, limit: int = 10) -> list[dict]:
    """Return the patient's most recent PHP requests, newest first."""
    patient_email = _normalize_email(patient_email)
    if requests_collection is None or not patient_email:
        return []
    return list(requests_collection.find({"patient_email": patient_email}).sort("created_at", -1))[:limit]


def request_primary_practitioner(
    users_collection,
    requests_collection,
    patient_user: dict | None,
    doctor_email: str,
    note: str = "",
) -> tuple[dict | None, str | None]:
    """Create a PHP enrollment (or change) request. Returns (request, error_message)."""
    if users_collection is None or requests_collection is None:
        return None, "The database is not available right now."
    if not isinstance(patient_user, dict):
        return None, "You must be signed in as a patient."

    patient_email = _normalize_email(patient_user.get("email"))
    doctor_email = _normalize_email(doctor_email)
    if not patient_email or not doctor_email:
        return None, "Please choose a valid doctor."

    doctor = normalize_user_record(dict(users_collection.find_one({"email": doctor_email}) or {}))
    if not doctor or doctor.get("role") != "Doctor":
        return None, "That doctor could not be found."

    if get_pending_practitioner_request(requests_collection, patient_email):
        return None, "You already have a pending request. Cancel it before requesting another doctor."

    current_email = get_primary_practitioner_email(users_collection, requests_collection, patient_email)
    if current_email == doctor_email:
        return None, "This doctor is already your Primary Health Practitioner."

    request = {
        "patient_email": patient_email,
        "patient_name": format_person_name(patient_user),
        "doctor_email": doctor_email,
        "doctor_name": format_person_name(doctor, doctor=True),
        "request_type": REQUEST_TYPE_CHANGE if current_email else REQUEST_TYPE_ENROLL,
        "previous_doctor_email": current_email,
        "note": (note or "").strip(),
        "status": STATUS_PENDING,
        "patient_notified": False,
        "created_at": datetime.utcnow(),
    }
    result = requests_collection.insert_one(request)
    request["_id"] = result.inserted_id
    return request, None


def cancel_practitioner_request(requests_collection, request_id, patient_email: str) -> bool:
    """Let a patient withdraw their own pending request."""
    if requests_collection is None:
        return False
    result = requests_collection.update_one(
        {"_id": request_id, "patient_email": _normalize_email(patient_email), "status": STATUS_PENDING},
        {"$set": {"status": STATUS_CANCELLED, "patient_notified": True, "updated_at": datetime.utcnow()}},
    )
    return result.matched_count > 0


def respond_to_practitioner_request(
    users_collection,
    requests_collection,
    request_id,
    doctor_email: str,
    accept: bool,
) -> bool:
    """Accept or decline a pending request addressed to this doctor.

    Accepting makes the doctor the patient's sole PHP and ends any previous
    accepted relationship, so it drops off the old doctor's patient list.
    """
    if users_collection is None or requests_collection is None:
        return False

    doctor_email = _normalize_email(doctor_email)
    now = datetime.utcnow()
    request = requests_collection.find_one(
        {"_id": request_id, "doctor_email": doctor_email, "status": STATUS_PENDING}
    )
    if request is None:
        return False

    new_status = STATUS_ACCEPTED if accept else STATUS_DECLINED
    result = requests_collection.update_one(
        {"_id": request_id, "status": STATUS_PENDING},
        {"$set": {"status": new_status, "patient_notified": False, "updated_at": now}},
    )
    if result.matched_count == 0:
        return False

    if accept:
        patient_email = _normalize_email(request.get("patient_email"))
        users_collection.update_one(
            {"email": patient_email},
            {"$set": {"primary_doctor_email": doctor_email, "primary_doctor_since": now}},
        )
        requests_collection.update_many(
            {"patient_email": patient_email, "status": STATUS_ACCEPTED, "_id": {"$ne": request_id}},
            {"$set": {"status": STATUS_REPLACED, "updated_at": now}},
        )
    return True


def get_unseen_decisions(requests_collection, patient_email: str) -> list[dict]:
    """Return accepted/declined requests the patient has not acknowledged yet."""
    patient_email = _normalize_email(patient_email)
    if requests_collection is None or not patient_email:
        return []
    return list(
        requests_collection.find(
            {
                "patient_email": patient_email,
                "status": {"$in": [STATUS_ACCEPTED, STATUS_DECLINED]},
                "patient_notified": False,
            }
        ).sort("updated_at", -1)
    )


def mark_decisions_seen(requests_collection, patient_email: str) -> None:
    """Acknowledge all outstanding accept/decline notifications for a patient."""
    if requests_collection is None:
        return
    requests_collection.update_many(
        {"patient_email": _normalize_email(patient_email), "patient_notified": False},
        {"$set": {"patient_notified": True}},
    )
