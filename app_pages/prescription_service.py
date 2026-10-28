"""Simulated prescriptions: doctors draft, finalize and void them; patients view finalized/voided ones.

EDUCATIONAL DEMO ONLY. Prescriptions are simulated, never sent anywhere, and
every medication detail is typed in by the doctor - nothing is suggested or
inferred from the ML predictions.

Rules enforced here (not just in the UI):
- New prescriptions start as drafts. Only the author can see, edit or finalize a draft.
- Creating and finalizing require the doctor to be the patient's current Primary Health Practitioner.
- Finalized prescriptions can't be edited; the author can void one with a reason.
- Voided prescriptions stay in history. Patients only see finalized and voided records.
- Every create, edit and status change is appended to ``audit_history``.

Functions take the MongoDB collections as arguments so they can be unit tested
without a live database.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from app_pages.practitioner_service import format_person_name, get_primary_practitioner_email

STATUS_DRAFT = "draft"
STATUS_FINALIZED = "finalized"
STATUS_VOIDED = "voided"
PATIENT_VISIBLE_STATUSES = [STATUS_FINALIZED, STATUS_VOIDED]

MEDICATION_FIELDS = ("name", "dosage", "frequency", "duration", "instructions")
REQUIRED_MEDICATION_FIELDS = {
    "name": "Medication name",
    "dosage": "Dosage",
    "frequency": "Frequency",
    "duration": "Duration",
}

SIMULATION_NOTICE = (
    "SIMULATED PRESCRIPTION - FOR EDUCATIONAL DEMONSTRATION ONLY. "
    "Not a legally valid prescription. Not sent to any pharmacy. Do not use to obtain medication."
)


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def generate_prescription_id(now: datetime | None = None) -> str:
    """Human-readable system id, e.g. SIM-RX-20261027-4F9A2C."""
    now = now or datetime.utcnow()
    return f"SIM-RX-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"


def clean_medications(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Trim medication rows, drop blank ones, and report missing required fields."""
    medications = []
    errors = []
    for row in rows or []:
        medication = {field: str((row or {}).get(field) or "").strip() for field in MEDICATION_FIELDS}
        if not any(medication.values()):
            continue
        missing = [label for field, label in REQUIRED_MEDICATION_FIELDS.items() if not medication[field]]
        if missing:
            errors.append(f"Medication {len(medications) + 1}: {', '.join(missing)} required.")
        medications.append(medication)
    if not medications:
        errors.append("Add at least one medication.")
    return medications, errors


def _audit_entry(action: str, actor_email: str, details: str = "", now: datetime | None = None) -> dict:
    return {
        "action": action,
        "by": _normalize_email(actor_email),
        "at": now or datetime.utcnow(),
        "details": details,
    }


def _is_primary_practitioner(users_collection, requests_collection, doctor_email: str, patient_email: str) -> bool:
    return bool(doctor_email) and get_primary_practitioner_email(
        users_collection, requests_collection, patient_email
    ) == _normalize_email(doctor_email)


def create_draft(
    prescriptions_collection,
    users_collection,
    requests_collection,
    *,
    patient: dict,
    doctor: dict,
    medications: list[dict],
    doctor_note: str = "",
    analysis_id=None,
    prescription_id: str | None = None,
) -> tuple[dict | None, list[str]]:
    """Create a draft. ``patient`` comes from get_patient_overview, ``doctor`` is the signed-in user."""
    if prescriptions_collection is None:
        return None, ["The database is not available right now."]
    doctor_email = _normalize_email((doctor or {}).get("email"))
    patient_email = _normalize_email((patient or {}).get("email"))
    if not _is_primary_practitioner(users_collection, requests_collection, doctor_email, patient_email):
        return None, ["Only the patient's Primary Health Practitioner can create prescriptions."]

    medications, errors = clean_medications(medications)
    if errors:
        return None, errors

    now = datetime.utcnow()
    prescription = {
        "prescription_id": prescription_id or generate_prescription_id(now),
        "patient_id": patient.get("id"),
        "patient_email": patient_email,
        "patient_name": patient.get("name") or patient_email,
        "doctor_id": doctor.get("_id"),
        "doctor_email": doctor_email,
        "doctor_name": format_person_name(doctor, doctor=True),
        "analysis_id": analysis_id,
        "doctor_note": (doctor_note or "").strip(),
        "medications": medications,
        "status": STATUS_DRAFT,
        "is_simulated": True,
        "created_at": now,
        "updated_at": now,
        "audit_history": [_audit_entry("created", doctor_email, "Draft created", now)],
    }
    prescription["_id"] = prescriptions_collection.insert_one(prescription).inserted_id
    return prescription, []


def update_draft(
    prescriptions_collection,
    prescription_id,
    doctor_email: str,
    *,
    medications: list[dict],
    doctor_note: str = "",
    analysis_id=None,
) -> list[str]:
    """Edit a draft. Only its author can, and only while it is still a draft."""
    prescription = get_prescription_for_doctor(prescriptions_collection, prescription_id, doctor_email)
    if prescription is None or prescription.get("doctor_email") != _normalize_email(doctor_email):
        return ["Prescription not found."]
    if prescription.get("status") != STATUS_DRAFT:
        return ["Only draft prescriptions can be edited."]

    medications, errors = clean_medications(medications)
    if errors:
        return errors

    now = datetime.utcnow()
    result = prescriptions_collection.update_one(
        {"_id": prescription["_id"], "doctor_email": prescription["doctor_email"], "status": STATUS_DRAFT},
        {
            "$set": {
                "medications": medications,
                "doctor_note": (doctor_note or "").strip(),
                "analysis_id": analysis_id,
                "updated_at": now,
                "audit_history": prescription.get("audit_history", [])
                + [_audit_entry("edited", doctor_email, "Draft edited", now)],
            }
        },
    )
    return [] if result.matched_count else ["Only draft prescriptions can be edited."]


def finalize_prescription(
    prescriptions_collection,
    users_collection,
    requests_collection,
    prescription_id,
    doctor_email: str,
) -> list[str]:
    """Finalize a draft. Only the author, while still the patient's Primary Health Practitioner."""
    prescription = get_prescription_for_doctor(prescriptions_collection, prescription_id, doctor_email)
    if prescription is None or prescription.get("doctor_email") != _normalize_email(doctor_email):
        return ["Prescription not found."]
    if prescription.get("status") != STATUS_DRAFT:
        return ["Only draft prescriptions can be finalized."]
    if not _is_primary_practitioner(users_collection, requests_collection, doctor_email, prescription["patient_email"]):
        return ["Only the patient's current Primary Health Practitioner can finalize prescriptions."]
    _, errors = clean_medications(prescription.get("medications"))
    if errors:
        return errors

    now = datetime.utcnow()
    result = prescriptions_collection.update_one(
        {"_id": prescription["_id"], "doctor_email": prescription["doctor_email"], "status": STATUS_DRAFT},
        {
            "$set": {
                "status": STATUS_FINALIZED,
                "finalized_at": now,
                "updated_at": now,
                "audit_history": prescription.get("audit_history", [])
                + [_audit_entry("finalized", doctor_email, "Status changed from draft to finalized", now)],
            }
        },
    )
    return [] if result.matched_count else ["Only draft prescriptions can be finalized."]


def void_prescription(prescriptions_collection, prescription_id, doctor_email: str, reason: str) -> list[str]:
    """Void a finalized prescription. Only its author can, and a reason is required."""
    reason = (reason or "").strip()
    if not reason:
        return ["Please give a reason for voiding."]
    prescription = get_prescription_for_doctor(prescriptions_collection, prescription_id, doctor_email)
    if prescription is None or prescription.get("doctor_email") != _normalize_email(doctor_email):
        return ["Only the prescribing doctor can void this prescription."]
    if prescription.get("status") != STATUS_FINALIZED:
        return ["Only finalized prescriptions can be voided."]

    now = datetime.utcnow()
    result = prescriptions_collection.update_one(
        {"_id": prescription["_id"], "doctor_email": prescription["doctor_email"], "status": STATUS_FINALIZED},
        {
            "$set": {
                "status": STATUS_VOIDED,
                "void_reason": reason,
                "voided_at": now,
                "updated_at": now,
                "audit_history": prescription.get("audit_history", [])
                + [_audit_entry("voided", doctor_email, f"Status changed from finalized to voided: {reason}", now)],
            }
        },
    )
    return [] if result.matched_count else ["Only finalized prescriptions can be voided."]


def _visible_to_doctor(prescription: dict, doctor_email: str) -> bool:
    """Drafts are private to their author; finalized and voided records are part of the patient's history."""
    if prescription.get("status") == STATUS_DRAFT:
        return prescription.get("doctor_email") == _normalize_email(doctor_email)
    return prescription.get("status") in PATIENT_VISIBLE_STATUSES


def list_prescriptions_for_doctor(
    prescriptions_collection,
    doctor_email: str,
    patient_email: str,
    statuses: list[str] | None = None,
) -> list[dict]:
    """A patient's prescriptions as this doctor may see them, newest first, optionally filtered by status."""
    patient_email = _normalize_email(patient_email)
    if prescriptions_collection is None or not patient_email:
        return []
    found = prescriptions_collection.find({"patient_email": patient_email}).sort("created_at", -1)
    return [
        prescription
        for prescription in found
        if _visible_to_doctor(prescription, doctor_email)
        and (statuses is None or prescription.get("status") in statuses)
    ]


def get_prescription_for_doctor(prescriptions_collection, prescription_id, doctor_email: str) -> dict | None:
    if prescriptions_collection is None or prescription_id is None:
        return None
    prescription = prescriptions_collection.find_one({"_id": prescription_id})
    if prescription is None or not _visible_to_doctor(prescription, doctor_email):
        return None
    return prescription


def list_prescriptions_for_patient(prescriptions_collection, patient_email: str) -> list[dict]:
    """The signed-in patient's finalized and voided prescriptions, newest first. Never drafts."""
    patient_email = _normalize_email(patient_email)
    if prescriptions_collection is None or not patient_email:
        return []
    return list(
        prescriptions_collection.find(
            {"patient_email": patient_email, "status": {"$in": PATIENT_VISIBLE_STATUSES}}
        ).sort("created_at", -1)
    )
