"""Doctor "Prescriptions" page (Clinical workspace): every simulated prescription this doctor wrote, across patients.

Prescriptions are created from a patient (My patients > patient > Prescriptions); this page is for finding them
again. Drafts come first because they still need the doctor to finish and finalize them.
"""

from __future__ import annotations

import streamlit as st

from app_pages.doctor_navigation import MY_PATIENTS, page
from app_pages.prescription_doctor_pages import open_prescription_detail
from app_pages.prescription_service import (
    STATUS_DRAFT,
    STATUS_FINALIZED,
    STATUS_VOIDED,
    list_prescriptions_by_doctor,
)
from app_pages.prescription_ui import (
    format_date,
    format_status,
    medication_names,
    prescription_dates,
    render_simulation_notice,
)
from app_pages.registration_page import get_prescriptions_collection
from ui.components import empty_state, entity_card, page_header, search_and_filter, section_header

FILTER_KEY = "rx-all"
ALL_STATUSES = [STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED]


def _doctor_email() -> str:
    user = st.session_state.get("authenticated_user") or {}
    return str(user.get("email") or "").strip().lower()


def _clear_filters() -> None:
    st.session_state[f"{FILTER_KEY}-search"] = ""
    st.session_state[f"{FILTER_KEY}-filter"] = list(ALL_STATUSES)


def _matches(prescription: dict, query: str) -> bool:
    if not query:
        return True
    return query in f"{prescription.get('patient_name') or ''} {prescription.get('prescription_id') or ''}".lower()


def _render_card(prescription: dict) -> None:
    key = str(prescription["_id"])
    is_draft = prescription.get("status") == STATUS_DRAFT
    container = entity_card(
        f"rx-all-{key}",
        str(prescription.get("patient_name") or prescription.get("patient_email")),
        subtitle=str(prescription.get("prescription_id")),
        status=("prescription", prescription.get("status")),
        fields=[
            *prescription_dates(prescription),
            ("Medications", medication_names(prescription)),
        ],
    )
    with container:
        if is_draft:
            st.caption(f"Last saved {format_date(prescription.get('updated_at'))}")
        if st.button("Open draft" if is_draft else "Open prescription", key=f"rx_all_open_{key}",
                     icon=":material/open_in_new:"):
            open_prescription_detail(prescription)


def render() -> None:
    page_header("Prescriptions", "Every simulated prescription you have written, across all your patients")
    render_simulation_notice()

    prescriptions = list_prescriptions_by_doctor(get_prescriptions_collection(), _doctor_email())
    if not prescriptions:
        empty_state(
            "No prescriptions yet",
            "Prescriptions are created from a patient. Open a patient from My patients, then create a prescription.",
            icon=":material/medication:",
            key="rx-all-none",
            action_label="Go to my patients",
            page=page(MY_PATIENTS),
        )
        return

    query, statuses = search_and_filter(
        FILTER_KEY,
        placeholder="Search by patient name or prescription ID",
        filters=ALL_STATUSES,
        format_filter=format_status,
    )
    shown = [rx for rx in prescriptions if rx.get("status") in statuses and _matches(rx, query)]
    if not shown:
        empty_state(
            "No prescriptions match",
            "Try a different search or status filter.",
            icon=":material/filter_alt_off:",
            key="rx-all-filtered",
            action_label="Clear filters",
            on_action=_clear_filters,
        )
        return

    drafts = [rx for rx in shown if rx.get("status") == STATUS_DRAFT]
    others = [rx for rx in shown if rx.get("status") != STATUS_DRAFT]
    if drafts:
        section_header(
            "Drafts to finish",
            "Only you can see drafts. Finalize one to share it with the patient.",
        )
        for prescription in drafts:
            _render_card(prescription)
    if others:
        section_header("Finalized and voided", "Part of each patient's prescription history")
        for prescription in others:
            _render_card(prescription)
