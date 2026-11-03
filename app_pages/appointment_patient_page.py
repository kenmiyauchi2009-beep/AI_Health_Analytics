"""Patient "Appointments" page: book with the connected doctor, then manage upcoming and past appointments."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import ROLE_PATIENT, format_slot, list_for_patient, request_appointment
from app_pages.appointment_ui import (
    flash,
    render_appointment_details,
    render_cancel_control,
    render_reschedule_controls,
    render_slot_picker,
    show_errors,
    show_flash,
)
from app_pages.practitioner_service import format_person_name, get_primary_practitioner
from app_pages.registration_page import (
    get_appointments_collection,
    get_availability_collection,
    get_requests_collection,
    get_users_collection,
)


def _patient() -> dict:
    return st.session_state.get("authenticated_user") or {}


def _render_booking(now: datetime) -> None:
    doctor = get_primary_practitioner(get_users_collection(), get_requests_collection(), _patient().get("email"))
    if doctor is None:
        st.info("Connect with a doctor in the **Primary Health Practitioner** tab before booking an appointment.")
        return

    # Patients can only book with the doctor they have an active relationship with.
    doctors = {doctor["email"]: doctor}
    doctor_email = st.selectbox(
        "Your connected doctor",
        options=list(doctors),
        format_func=lambda email: format_person_name(doctors[email], doctor=True),
        key="book_doctor",
    )
    start = render_slot_picker(doctor_email, "book", now)
    if start is None:
        return

    reason = st.text_area("Reason for the appointment", max_chars=500, key="book_reason")
    if st.button("Request appointment", type="primary", key="book_submit"):
        appointment, errors = request_appointment(
            get_appointments_collection(),
            get_availability_collection(),
            get_users_collection(),
            get_requests_collection(),
            patient_user=_patient(),
            doctor_email=doctor_email,
            start=start,
            reason=reason,
            now=now,
        )
        if not show_errors(errors):
            st.session_state.pop("book_reason", None)
            flash(
                f"Your request for {format_slot(appointment['start_at'], appointment['timezone'])} was sent to "
                f"{appointment['doctor_name']} and is awaiting their approval."
            )
            st.rerun()


def render() -> None:
    st.title("Appointments")
    show_flash()

    now = datetime.utcnow()
    email = _patient().get("email")
    upcoming, history = list_for_patient(get_appointments_collection(), email, now)

    book_tab, upcoming_tab, history_tab = st.tabs(
        ["Book an appointment", f"Upcoming Appointments ({len(upcoming)})", "Appointment History"]
    )
    with book_tab:
        _render_booking(now)

    with upcoming_tab:
        if not upcoming:
            st.info("You have no upcoming appointments.")
        for appointment in upcoming:
            key = f"pat_appt_{appointment['_id']}"
            with st.container(border=True):
                render_appointment_details(appointment, ROLE_PATIENT, now)
                render_reschedule_controls(appointment, email, now, key)
                render_cancel_control(appointment, email, now, key)

    with history_tab:
        if not history:
            st.info("No past appointments yet.")
        for appointment in history:
            with st.container(border=True):
                render_appointment_details(appointment, ROLE_PATIENT, now)
