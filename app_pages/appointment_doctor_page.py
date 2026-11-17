"""Doctor appointment pages: incoming requests, and upcoming appointments with history."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import (
    ROLE_DOCTOR,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_NO_SHOW,
    accept_appointment,
    list_for_doctor,
    record_outcome,
    reject_appointment,
)
from app_pages.appointment_ui import (
    FLASH_KEY,
    appointment_card,
    format_when,
    render_change_controls,
)
from app_pages.doctor_navigation import APPOINTMENT_REQUESTS, AVAILABILITY, page
from app_pages.registration_page import get_appointments_collection
from ui.components import confirmation_dialog, empty_state, flash, open_dialog, page_header, show_errors, show_flash


def _doctor_email() -> str:
    return str((st.session_state.get("authenticated_user") or {}).get("email") or "").strip().lower()


# ---------------------------------------------------------------- appointment requests


def _render_request_actions(appointment: dict, now: datetime) -> None:
    key = f"doc_req_{appointment['_id']}"
    reject_key = f"{key}_reject"

    def accept_and_reject() -> None:
        if st.button("Accept", key=f"{key}_accept", type="primary", icon=":material/check:"):
            errors = accept_appointment(get_appointments_collection(), appointment["_id"], _doctor_email(), now)
            if not show_errors(errors):
                flash(f"Appointment with {appointment['patient_name']} confirmed.", key=FLASH_KEY)
                st.rerun()
        st.button("Reject", key=f"{key}_reject_open", icon=":material/block:",
                  on_click=open_dialog, args=(reject_key,))

    render_change_controls(appointment, _doctor_email(), now, key, reschedule_label="Propose another time",
                           cancel=False, leading_actions=accept_and_reject)

    def confirm(reason: str) -> list[str]:
        errors = reject_appointment(get_appointments_collection(), appointment["_id"], _doctor_email(), reason, now)
        if not errors:
            flash(f"Request from {appointment['patient_name']} rejected. The time slot is available again.",
                  key=FLASH_KEY)
        return errors

    confirmation_dialog(
        reject_key,
        title="Reject request?",
        message=f"{appointment['patient_name']}'s request for "
                f"**{format_when(appointment['start_at'], appointment['timezone'])}** will be rejected and the "
                "time slot released.",
        confirm_label="Reject request",
        on_confirm=confirm,
        reason_label="Reason (optional, shown to the patient)",
        danger=True,
    )


def render_requests_page() -> None:
    """Doctor Appointment requests page."""
    page_header("Appointment requests", "Accept or reject requests from your patients before they expire.")
    show_flash(FLASH_KEY)
    now = datetime.utcnow()
    requests, _, _ = list_for_doctor(get_appointments_collection(), _doctor_email(), now)
    if not requests:
        empty_state(
            "No requests waiting",
            "New requests from your patients appear here. Patients can only book times you've made available.",
            icon=":material/inbox:",
            key="doc-requests",
            action_label="Review my availability",
            page=page(AVAILABILITY),
        )
    for appointment in requests:
        with appointment_card(appointment, ROLE_DOCTOR, now, f"doc_req_card_{appointment['_id']}"):
            _render_request_actions(appointment, now)


# ---------------------------------------------------------------- my appointments


def _render_outcome(appointment: dict, now: datetime) -> None:
    key = f"doc_outcome_{appointment['_id']}"
    st.caption(":material/pending_actions: This appointment has started. Record how it went.")
    with st.container(horizontal=True, gap="small"):
        for outcome, label, icon, kind in [
            (STATUS_COMPLETED, "Mark completed", ":material/check_circle:", "primary"),
            (STATUS_NO_SHOW, "Mark no-show", ":material/person_off:", "secondary"),
        ]:
            if st.button(label, key=f"{key}_{outcome}", icon=icon, type=kind):
                errors = record_outcome(get_appointments_collection(), appointment["_id"], _doctor_email(),
                                        outcome, now)
                if not show_errors(errors):
                    flash(f"Appointment with {appointment['patient_name']} marked {label.split()[-1]}.",
                          key=FLASH_KEY)
                    st.rerun()


def render_page() -> None:
    """Doctor My appointments page: upcoming and history."""
    actions = page_header("My appointments", "Confirmed visits, and a record of past appointments.")
    show_flash(FLASH_KEY)

    now = datetime.utcnow()
    requests, upcoming, history = list_for_doctor(get_appointments_collection(), _doctor_email(), now)
    if requests:
        actions.page_link(page(APPOINTMENT_REQUESTS), label=f"Review requests ({len(requests)})",
                          icon=":material/inbox:")

    upcoming_tab, history_tab = st.tabs([f"Upcoming ({len(upcoming)})", f"History ({len(history)})"])
    with upcoming_tab:
        if not upcoming:
            empty_state(
                "No upcoming appointments",
                "Requests you accept appear here.",
                icon=":material/event_available:",
                key="doc-upcoming",
                action_label="Review appointment requests",
                page=page(APPOINTMENT_REQUESTS),
            )
        for appointment in upcoming:
            key = f"doc_up_{appointment['_id']}"
            with appointment_card(appointment, ROLE_DOCTOR, now, key):
                render_change_controls(appointment, _doctor_email(), now, key)

    with history_tab:
        if not history:
            empty_state(
                "No past appointments yet",
                "Completed, cancelled and expired appointments are kept here.",
                icon=":material/history:",
                key="doc-history",
                action_label="Review my availability",
                page=page(AVAILABILITY),
            )
        for appointment in history:
            with appointment_card(appointment, ROLE_DOCTOR, now, f"doc_hist_{appointment['_id']}"):
                if appointment["status"] == STATUS_CONFIRMED and appointment["start_at"] <= now:
                    _render_outcome(appointment, now)
