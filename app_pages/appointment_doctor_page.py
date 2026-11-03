"""Doctor "Appointments" page: incoming requests, upcoming appointments and history."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import (
    ROLE_DOCTOR,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_NO_SHOW,
    accept_appointment,
    active_proposal,
    list_for_doctor,
    record_outcome,
    reject_appointment,
)
from app_pages.appointment_ui import (
    flash,
    render_appointment_details,
    render_cancel_control,
    render_reschedule_controls,
    show_errors,
    show_flash,
)
from app_pages.doctor_navigation import AVAILABILITY, DASHBOARD, go_to
from app_pages.registration_page import get_appointments_collection


def _doctor_email() -> str:
    return str((st.session_state.get("authenticated_user") or {}).get("email") or "").strip().lower()


def _render_request(appointment: dict, now: datetime) -> None:
    key = f"doc_req_{appointment['_id']}"
    accept_col, _ = st.columns([1, 3])
    if accept_col.button("Accept", key=f"{key}_accept", type="primary"):
        errors = accept_appointment(get_appointments_collection(), appointment["_id"], _doctor_email(), now)
        if not show_errors(errors):
            flash(f"Appointment with {appointment['patient_name']} confirmed.")
            st.rerun()
    with st.expander("Reject"):
        reason = st.text_input("Reason for rejection (optional, shown to the patient)", key=f"{key}_reject_reason")
        if st.button("Confirm rejection", key=f"{key}_reject_confirm"):
            errors = reject_appointment(get_appointments_collection(), appointment["_id"], _doctor_email(), reason, now)
            if not show_errors(errors):
                flash(f"Request from {appointment['patient_name']} rejected. The time slot is available again.")
                st.rerun()
    render_reschedule_controls(appointment, _doctor_email(), now, key)


def _render_outcome(appointment: dict, now: datetime) -> None:
    key = f"doc_outcome_{appointment['_id']}"
    st.caption("This appointment has started. Record how it went.")
    completed_col, no_show_col, _ = st.columns([1, 1, 2])
    for column, outcome, label in [(completed_col, STATUS_COMPLETED, "Mark completed"),
                                   (no_show_col, STATUS_NO_SHOW, "Mark no-show")]:
        if column.button(label, key=f"{key}_{outcome}"):
            errors = record_outcome(get_appointments_collection(), appointment["_id"], _doctor_email(), outcome, now)
            if not show_errors(errors):
                flash(f"Appointment with {appointment['patient_name']} marked {label.split()[-1]}.")
                st.rerun()


def render_page() -> None:
    """Doctor Appointments page."""
    nav_back, nav_availability, _ = st.columns([1, 1, 3])
    if nav_back.button("← Back to dashboard", key="appointments_back"):
        go_to(DASHBOARD)
    if nav_availability.button("Manage availability", key="appointments_availability"):
        go_to(AVAILABILITY)

    st.title("Appointments")
    show_flash()

    now = datetime.utcnow()
    requests, upcoming, history = list_for_doctor(get_appointments_collection(), _doctor_email(), now)
    proposals = sum(
        1 for appointment in upcoming
        if (active_proposal(appointment, now) or {}).get("proposed_by") not in (None, ROLE_DOCTOR)
    )

    requests_tab, upcoming_tab, history_tab = st.tabs([
        f"Appointment Requests ({len(requests)})",
        f"Upcoming Appointments ({len(upcoming)})" + (f" · {proposals} reschedule request(s)" if proposals else ""),
        "Appointment History",
    ])
    with requests_tab:
        if not requests:
            st.info("No pending appointment requests.")
        for appointment in requests:
            with st.container(border=True):
                render_appointment_details(appointment, ROLE_DOCTOR, now)
                _render_request(appointment, now)

    with upcoming_tab:
        if not upcoming:
            st.info("No upcoming confirmed appointments.")
        for appointment in upcoming:
            key = f"doc_up_{appointment['_id']}"
            with st.container(border=True):
                render_appointment_details(appointment, ROLE_DOCTOR, now)
                render_reschedule_controls(appointment, _doctor_email(), now, key)
                render_cancel_control(appointment, _doctor_email(), now, key)

    with history_tab:
        if not history:
            st.info("No past appointments yet.")
        for appointment in history:
            with st.container(border=True):
                render_appointment_details(appointment, ROLE_DOCTOR, now)
                if appointment["status"] == STATUS_CONFIRMED and appointment["start_at"] <= now:
                    _render_outcome(appointment, now)
