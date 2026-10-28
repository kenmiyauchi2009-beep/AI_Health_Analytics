"""Doctor notes, stored in their own collection and linked to the patient's user id.

Functions take the MongoDB collection as an argument so they can be unit tested
without a live database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DoctorNote:
    """A doctor's note about one patient, optionally tied to the analysis it was written on."""

    patient_id: Any
    patient_email: str
    doctor_email: str
    text: str
    analysis_id: Any = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: Any = None

    def to_document(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "patient_email": self.patient_email,
            "doctor_email": self.doctor_email,
            "analysis_id": self.analysis_id,
            "text": self.text,
            "created_at": self.created_at,
        }

    @classmethod
    def from_document(cls, document: dict) -> DoctorNote:
        return cls(
            id=document.get("_id"),
            patient_id=document.get("patient_id"),
            patient_email=document.get("patient_email") or "",
            doctor_email=document.get("doctor_email") or "",
            analysis_id=document.get("analysis_id"),
            text=document.get("text") or "",
            created_at=document.get("created_at"),
        )


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def save_doctor_note(
    notes_collection,
    patient: dict,
    doctor_email: str,
    text: str,
    analysis_id=None,
) -> tuple[DoctorNote | None, str | None]:
    """Save a note for a patient. ``patient`` is the dict from get_patient_overview. Returns (note, error)."""
    if notes_collection is None:
        return None, "The database is not available right now."
    text = (text or "").strip()
    if not text:
        return None, "Please write a note before saving."
    if not isinstance(patient, dict) or patient.get("id") is None:
        return None, "This patient could not be found."

    note = DoctorNote(
        patient_id=patient["id"],
        patient_email=_normalize_email(patient.get("email")),
        doctor_email=_normalize_email(doctor_email),
        text=text,
        analysis_id=analysis_id,
    )
    note.id = notes_collection.insert_one(note.to_document()).inserted_id
    return note, None


def get_doctor_notes(notes_collection, patient_id, analysis_id=None) -> list[DoctorNote]:
    """Return a patient's notes newest first, optionally only those written on one analysis."""
    if notes_collection is None or patient_id is None:
        return []
    query = {"patient_id": patient_id}
    if analysis_id is not None:
        query["analysis_id"] = analysis_id
    return [DoctorNote.from_document(document) for document in notes_collection.find(query).sort("created_at", -1)]
