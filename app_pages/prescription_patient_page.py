"""Patient "My prescriptions" page: read-only history of finalized and voided simulated prescriptions."""

from __future__ import annotations

import streamlit as st

from app_pages.patient_navigation import BOOK_APPOINTMENT, page
from app_pages.prescription_service import STATUS_FINALIZED, STATUS_VOIDED, list_prescriptions_for_patient
from app_pages.prescription_ui import (
    format_status,
    medication_names,
    prescription_dates,
    render_medications_table,
    render_note_and_void_reason,
    render_pdf_download,
    render_simulation_notice,
)
from app_pages.registration_page import get_prescriptions_collection
from ui.components import empty_state, entity_card, page_header, search_and_filter

FILTER_KEY = "my-rx"
STATUSES = [STATUS_FINALIZED, STATUS_VOIDED]


def _clear_filters() -> None:
    st.session_state[f"{FILTER_KEY}-search"] = ""
    st.session_state[f"{FILTER_KEY}-filter"] = list(STATUSES)


def _matches(prescription: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [str(prescription.get("prescription_id") or ""), str(prescription.get("doctor_name") or ""),
         medication_names(prescription)]
    ).lower()
    return query in haystack


def render() -> None:
    """Show the signed-in patient's own prescriptions. Drafts are never shown."""
    page_header("My prescriptions", "Simulated prescriptions your doctors have finalized")
    render_simulation_notice()

    user = st.session_state.get("authenticated_user") or {}
    prescriptions = list_prescriptions_for_patient(get_prescriptions_collection(), user.get("email"))
    if not prescriptions:
        empty_state(
            "No prescriptions yet",
            "When your doctor finalizes a simulated prescription for you, it appears here.",
            icon=":material/medication:",
            key="my-rx-none",
            action_label="Book appointment",
            page=page(BOOK_APPOINTMENT),
        )
        return

    query, statuses = search_and_filter(
        FILTER_KEY,
        placeholder="Search by prescription ID, doctor or medication",
        filters=STATUSES,
        format_filter=format_status,
    )
    shown = [rx for rx in prescriptions if rx.get("status") in statuses and _matches(rx, query)]
    if not shown:
        empty_state(
            "No prescriptions match",
            "Try a different search or status filter.",
            icon=":material/filter_alt_off:",
            key="my-rx-filtered",
            action_label="Clear filters",
            on_action=_clear_filters,
        )
        return

    for prescription in shown:
        key = str(prescription["_id"])
        container = entity_card(
            f"my-rx-{key}",
            str(prescription.get("prescription_id")),
            subtitle=f"Prescribed by {prescription.get('doctor_name') or 'your doctor'}",
            status=("prescription", prescription.get("status")),
            fields=prescription_dates(prescription),
        )
        with container:
            render_note_and_void_reason(prescription)
            render_medications_table(prescription.get("medications") or [])
            render_pdf_download(prescription, key=f"my_rx_pdf_{key}")
