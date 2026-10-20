"""Data access for the doctor's Patient Overview page.

Each disease prediction a patient runs is saved as an "analysis" document so
their Primary Health Practitioner can review it later. Functions take the
MongoDB collections as arguments so they can be unit tested without a live
database.
"""

from __future__ import annotations

from datetime import date, datetime

from app_pages.practitioner_service import format_person_name, get_primary_practitioner_email
from app_pages.registration_page import normalize_user_record


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def calculate_age(date_of_birth, today: date | None = None) -> int | None:
    """Return the age in whole years from a ``YYYY-MM-DD`` string or date, if valid."""
    if isinstance(date_of_birth, datetime):
        birth = date_of_birth.date()
    elif isinstance(date_of_birth, date):
        birth = date_of_birth
    else:
        try:
            birth = date.fromisoformat(str(date_of_birth or "").strip()[:10])
        except ValueError:
            return None

    today = today or date.today()
    if birth > today:
        return None
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def parse_known_conditions(value) -> list[str]:
    """Normalize known conditions stored as a list or a comma-separated string."""
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value or "").split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def save_analysis(analyses_collection, patient_email: str, selected_symptoms: list[str], result) -> dict | None:
    """Store one disease prediction run by a patient. ``result`` is a PredictionResult."""
    patient_email = _normalize_email(patient_email)
    if analyses_collection is None or not patient_email or result is None:
        return None

    analysis = {
        "patient_email": patient_email,
        "symptoms": list(selected_symptoms),
        "top_disease": result.top_disease,
        "top_probability": float(result.top_probability),
        "ranked": [{"disease": item.disease, "probability": float(item.probability)} for item in result.ranked],
        "is_low_confidence": bool(result.is_low_confidence),
        "reviewed": False,
        "created_at": datetime.utcnow(),
    }
    inserted = analyses_collection.insert_one(analysis)
    analysis["_id"] = inserted.inserted_id
    return analysis


def get_patient_analyses(analyses_collection, patient_email: str, limit: int = 50) -> list[dict]:
    """Return the patient's saved analyses, newest first."""
    patient_email = _normalize_email(patient_email)
    if analyses_collection is None or not patient_email:
        return []
    return list(analyses_collection.find({"patient_email": patient_email}).sort("created_at", -1))[:limit]


def get_patient_overview(users_collection, requests_collection, doctor_email: str, patient_email: str) -> dict | None:
    """Return profile details for a patient, only if this doctor is their Primary Health Practitioner."""
    doctor_email = _normalize_email(doctor_email)
    patient_email = _normalize_email(patient_email)
    if users_collection is None or not doctor_email or not patient_email:
        return None
    if get_primary_practitioner_email(users_collection, requests_collection, patient_email) != doctor_email:
        return None

    patient = normalize_user_record(dict(users_collection.find_one({"email": patient_email}) or {}))
    if not patient:
        return None

    return {
        "email": patient_email,
        "name": format_person_name(patient),
        "age": calculate_age(patient.get("date_of_birth")),
        "known_conditions": parse_known_conditions(patient.get("known_conditions")),
    }


def review_analysis(analyses_collection, analysis_id, patient_email: str, doctor_email: str, notes: str = "") -> bool:
    """Mark one of the patient's analyses as reviewed by the doctor, with optional notes."""
    if analyses_collection is None:
        return False
    result = analyses_collection.update_one(
        {"_id": analysis_id, "patient_email": _normalize_email(patient_email)},
        {
            "$set": {
                "reviewed": True,
                "reviewed_by": _normalize_email(doctor_email),
                "review_notes": (notes or "").strip(),
                "reviewed_at": datetime.utcnow(),
            }
        },
    )
    return result.matched_count > 0
