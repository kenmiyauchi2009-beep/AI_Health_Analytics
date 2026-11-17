"""Patient appointment pages: book with the connected doctor, then manage upcoming and past appointments."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import ROLE_PATIENT, list_for_patient, request_appointment
from app_pages.appointment_ui import (
    FLASH_KEY,
    appointment_card,
    booking_options,
    format_remaining,
    format_when,
    render_change_controls,
    render_slot_picker,
)
from app_pages.patient_navigation import BOOK_APPOINTMENT, MY_APPOINTMENTS, MY_DOCTORS, page
from app_pages.practitioner_service import format_person_name, get_primary_practitioner
from app_pages.registration_page import (
    get_appointments_collection,
    get_availability_collection,
    get_requests_collection,
    get_users_collection,
)
from ui.components import card, empty_state, entity_card, form_section, page_header, show_errors, show_flash

# The appointment just requested, shown as a confirmation on the next run.
CONFIRMATION_KEY = "book_confirmation"


def _patient() -> dict:
    return st.session_state.get("authenticated_user") or {}


# ---------------------------------------------------------------- book appointment


def _render_confirmation(appointment: dict, now: datetime) -> None:
    with card("book-confirmation", raised=True):
        st.markdown("### :material/check_circle: Request sent")
        st.markdown(
            f"Your request for **{format_when(appointment['start_at'], appointment['timezone'])}** with "
            f"{appointment['doctor_name']} is **awaiting their approval**."
        )
        st.caption(
            f"The time is held for you while you wait. If {appointment['doctor_name']} doesn't respond within "
            f"{format_remaining(appointment['expires_at'], now)}, the request expires and the slot is released."
        )
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            st.page_link(page(MY_APPOINTMENTS), label="View my appointments", icon=":material/calendar_month:")
            st.button("Book another appointment", key="book_another", icon=":material/add:")


def _render_doctor_card(doctor: dict, availability: dict | None) -> None:
    fields = [("Clinic", doctor.get("clinic_or_hospital"))]
    if availability is not None:
        fields += [("Appointment length", f"{availability['slot_minutes']} minutes"),
                   ("Timezone", availability["timezone"])]
    entity_card(
        "book-doctor",
        format_person_name(doctor, doctor=True),
        subtitle=doctor.get("speciality") or "Primary health practitioner",
        fields=fields,
    )


def _submit(doctor: dict, start: datetime | None, reason: str, now: datetime) -> None:
    if start is None:
        show_errors(["Choose a time to request an appointment."])
        return
    appointment, errors = request_appointment(
        get_appointments_collection(),
        get_availability_collection(),
        get_users_collection(),
        get_requests_collection(),
        patient_user=_patient(),
        doctor_email=doctor["email"],
        start=start,
        reason=reason,
        now=now,
    )
    if not show_errors(errors):
        st.session_state.pop("book_reason", None)
        st.session_state[CONFIRMATION_KEY] = appointment
        st.rerun()


def render_book_page() -> None:
    page_header("Book appointment", "Request a visit with your connected doctor. They approve each request.")
    show_flash(FLASH_KEY)
    now = datetime.utcnow()

    confirmation = st.session_state.pop(CONFIRMATION_KEY, None)
    if confirmation:
        _render_confirmation(confirmation, now)
        return

    doctor = get_primary_practitioner(get_users_collection(), get_requests_collection(), _patient().get("email"))
    if doctor is None:
        empty_state(
            "Connect with a doctor first",
            "You can book appointments with your primary health practitioner once they accept your request.",
            icon=":material/medical_services:",
            key="book-no-doctor",
            action_label="Find a doctor",
            page=page(MY_DOCTORS),
        )
        return

    # Patients can only book with the doctor they have an active relationship with.
    availability, busy, dates = booking_options(doctor["email"], now)
    _render_doctor_card(doctor, availability)
    name = format_person_name(doctor, doctor=True)
    if availability is None:
        empty_state(
            "No bookable hours yet",
            f"{name} hasn't published their availability, so there are no times to book. Please check back later.",
            icon=":material/event_busy:",
            key="book-no-availability",
            action_label="View my appointments",
            page=page(MY_APPOINTMENTS),
        )
        return
    if not dates:
        empty_state(
            "No free times in the next 30 days",
            f"All of {name}'s bookable times are taken or blocked. New times appear here as they open up.",
            icon=":material/event_busy:",
            key="book-no-slots",
            action_label="View my appointments",
            page=page(MY_APPOINTMENTS),
        )
        return

    with form_section("Choose a date and time", f"Times are shown in {name}'s timezone, {availability['timezone']}.",
                      key="book-slot"):
        start = render_slot_picker(availability, busy, dates, "book", now)

    with form_section("Reason for visit", f"Shared with {name} to help them prepare.", key="book-reason"):
        reason = st.text_area("Reason for visit", max_chars=500, key="book_reason", label_visibility="collapsed",
                              placeholder="For example: follow-up on last week's fever")

    if st.button("Request appointment", type="primary", key="book_submit", icon=":material/send:"):
        _submit(doctor, start, reason, now)


# ---------------------------------------------------------------- my appointments


def render_my_appointments_page() -> None:
    actions = page_header("My appointments", "Your upcoming visits and past appointments.")
    actions.page_link(page(BOOK_APPOINTMENT), label="Book appointment", icon=":material/calendar_add_on:")
    show_flash(FLASH_KEY)

    now = datetime.utcnow()
    email = _patient().get("email")
    upcoming, history = list_for_patient(get_appointments_collection(), email, now)

    upcoming_tab, history_tab = st.tabs([f"Upcoming ({len(upcoming)})", f"History ({len(history)})"])
    with upcoming_tab:
        if not upcoming:
            empty_state(
                "No upcoming appointments",
                "Requests you send and visits your doctor confirms appear here.",
                icon=":material/event_available:",
                key="pat-upcoming",
                action_label="Book appointment",
                page=page(BOOK_APPOINTMENT),
            )
        for appointment in upcoming:
            key = f"pat_appt_{appointment['_id']}"
            with appointment_card(appointment, ROLE_PATIENT, now, key):
                render_change_controls(appointment, email, now, key)

    with history_tab:
        if not history:
            empty_state(
                "No past appointments yet",
                "Completed, cancelled and expired appointments are kept here.",
                icon=":material/history:",
                key="pat-history",
                action_label="Book appointment",
                page=page(BOOK_APPOINTMENT),
            )
        for appointment in history:
            appointment_card(appointment, ROLE_PATIENT, now, f"pat_hist_{appointment['_id']}")
