"""Streamlit pieces shared by the doctor and patient prescription views."""

from __future__ import annotations

import streamlit as st

from app_pages.prescription_pdf import build_prescription_pdf, prescription_pdf_filename
from app_pages.prescription_service import STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED
from ui.components import data_table
from ui.components import status_label as _component_status_label

STATUS_LABELS = {status: _component_status_label("prescription", status)
                 for status in (STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED)}

# The on-screen version of prescription_service.SIMULATION_NOTICE (the PDF keeps the original wording).
SIMULATION_NOTICE_TEXT = (
    "Simulated prescription for educational demonstration only. It is not a legally valid prescription, "
    "is not sent to any pharmacy and must not be used to obtain medication."
)


def format_date(value, with_time: bool = False) -> str:
    """Dates are stored in UTC; times are shown with that timezone."""
    if not hasattr(value, "strftime"):
        return "—"
    return value.strftime("%b %d, %Y %I:%M %p UTC" if with_time else "%b %d, %Y")


def status_label(prescription: dict) -> str:
    status = prescription.get("status")
    return STATUS_LABELS.get(status, str(status or "").capitalize())


def format_status(status: str) -> str:
    """For status filter pills."""
    return STATUS_LABELS.get(status, str(status).capitalize())


def render_simulation_notice() -> None:
    """One calm notice per page saying these prescriptions are simulated."""
    st.info(SIMULATION_NOTICE_TEXT, icon=":material/science:")


def medication_names(prescription: dict) -> str:
    names = [str(medication.get("name") or "").strip() for medication in prescription.get("medications") or []]
    return ", ".join(name for name in names if name) or "No medications"


def render_medications_table(medications: list[dict]) -> None:
    if not medications:
        st.caption("No medications.")
        return
    data_table(
        [
            {
                "Medication": medication.get("name"),
                "Dosage": medication.get("dosage"),
                "Frequency": medication.get("frequency"),
                "Duration": medication.get("duration"),
                "Instructions": medication.get("instructions") or "—",
            }
            for medication in medications
        ]
    )


def render_pdf_download(prescription: dict, key: str, *, primary: bool = False) -> None:
    st.download_button(
        "Download simulated PDF",
        data=build_prescription_pdf(prescription),
        file_name=prescription_pdf_filename(prescription),
        mime="application/pdf",
        key=key,
        icon=":material/download:",
        type="primary" if primary else "secondary",
    )


def prescription_dates(prescription: dict) -> list[tuple[str, str]]:
    """Created, plus finalized and voided dates when they apply."""
    fields = [("Created", format_date(prescription.get("created_at")))]
    if prescription.get("finalized_at"):
        fields.append(("Finalized", format_date(prescription.get("finalized_at"))))
    if prescription.get("status") == STATUS_VOIDED:
        fields.append(("Voided", format_date(prescription.get("voided_at"))))
    return fields


def render_note_and_void_reason(prescription: dict) -> None:
    """The doctor's note and, for a voided prescription, why it was voided."""
    if prescription.get("status") == STATUS_VOIDED:
        st.markdown(f":gray[Reason for voiding]  \n{prescription.get('void_reason') or 'Not given'}")
    if prescription.get("doctor_note"):
        st.markdown(f":gray[Doctor's note]  \n{prescription['doctor_note']}")
