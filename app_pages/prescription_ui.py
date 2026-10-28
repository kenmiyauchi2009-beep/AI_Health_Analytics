"""Streamlit pieces shared by the doctor and patient prescription views."""

from __future__ import annotations

import streamlit as st

from app_pages.prescription_pdf import build_prescription_pdf, prescription_pdf_filename
from app_pages.prescription_service import SIMULATION_NOTICE, STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED

STATUS_LABELS = {
    STATUS_DRAFT: "📝 Draft",
    STATUS_FINALIZED: "✅ Finalized",
    STATUS_VOIDED: "⛔ Voided",
}


def format_date(value, with_time: bool = False) -> str:
    if not hasattr(value, "strftime"):
        return "—"
    return value.strftime("%b %d, %Y %I:%M %p" if with_time else "%b %d, %Y")


def status_label(prescription: dict) -> str:
    status = prescription.get("status")
    return STATUS_LABELS.get(status, str(status or "").capitalize())


def render_simulation_notice() -> None:
    st.warning(f"**{SIMULATION_NOTICE}**", icon="⚠️")


def render_medications_table(medications: list[dict]) -> None:
    if not medications:
        st.caption("No medications.")
        return
    st.dataframe(
        [
            {
                "Medication": medication.get("name"),
                "Dosage": medication.get("dosage"),
                "Frequency": medication.get("frequency"),
                "Duration": medication.get("duration"),
                "Instructions": medication.get("instructions") or "—",
            }
            for medication in medications
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_pdf_download(prescription: dict, key: str) -> None:
    st.download_button(
        "Download simulated PDF",
        data=build_prescription_pdf(prescription),
        file_name=prescription_pdf_filename(prescription),
        mime="application/pdf",
        key=key,
    )


def render_prescription_summary(prescription: dict) -> None:
    """Read-only details: ids, dates, status, doctor's note, void reason and medications."""
    left, right = st.columns(2)
    with left:
        st.write(f"**Prescription ID:** {prescription.get('prescription_id')}")
        st.write(f"**Status:** {status_label(prescription)}")
        st.write(f"**Patient:** {prescription.get('patient_name')} (ID: {prescription.get('patient_id')})")
    with right:
        st.write(f"**Doctor:** {prescription.get('doctor_name')} (ID: {prescription.get('doctor_id')})")
        st.write(f"**Created:** {format_date(prescription.get('created_at'))}")
        if prescription.get("finalized_at"):
            st.write(f"**Finalized:** {format_date(prescription.get('finalized_at'))}")

    if prescription.get("status") == STATUS_VOIDED:
        st.error(
            f"Voided on {format_date(prescription.get('voided_at'))}. "
            f"Reason: {prescription.get('void_reason') or 'not given'}"
        )
    if prescription.get("doctor_note"):
        st.write(f"**Doctor's note:** {prescription['doctor_note']}")

    st.markdown("**Medications**")
    render_medications_table(prescription.get("medications") or [])
