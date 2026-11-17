"""Patient home: what's coming up, the latest analysis, and quick ways into the main tasks."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import format_slot, list_for_patient
from app_pages.patient_navigation import (
    ANALYSIS_HISTORY,
    BOOK_APPOINTMENT,
    MY_APPOINTMENTS,
    MY_DOCTORS,
    MY_PRESCRIPTIONS,
    NEW_ANALYSIS,
    page,
)
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.practitioner_page import render_practitioner_notifications
from app_pages.practitioner_service import format_person_name, get_primary_practitioner
from app_pages.prescription_service import STATUS_FINALIZED, list_prescriptions_for_patient
from app_pages.registration_page import (
    get_analyses_collection,
    get_appointments_collection,
    get_prescriptions_collection,
    get_requests_collection,
    get_users_collection,
)
from prediction.ui_view import format_symptom
from ui.components import card, empty_state, entity_card, metric_row, page_header, section_header


def _greeting(now: datetime) -> str:
    return "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"


def _render_next_appointment(upcoming: list[dict]) -> None:
    section_header("Next appointment")
    if not upcoming:
        empty_state("No upcoming appointments", "Book a visit with your doctor when you need one.",
                    icon=":material/calendar_month:", key="home-appointments", action_label="Book appointment",
                    page=page(BOOK_APPOINTMENT))
        return
    appointment = upcoming[0]
    with entity_card(
        "home-next-appointment",
        format_slot(appointment["start_at"], appointment["timezone"]),
        subtitle=appointment.get("doctor_name"),
        status=("appointment", appointment["status"]),
        fields=[("Duration", f"{appointment['duration_minutes']} minutes"), ("Reason", appointment.get("reason"))],
        columns=2,
    ):
        st.page_link(page(MY_APPOINTMENTS), label="Manage appointments", icon=":material/arrow_forward:")


def _render_latest_analysis(analyses: list[dict]) -> None:
    section_header("Latest health analysis")
    if not analyses:
        empty_state("No analyses yet", "Describe your symptoms to get a model prediction and an explanation.",
                    icon=":material/stethoscope:", key="home-analysis", action_label="Start a new analysis",
                    page=page(NEW_ANALYSIS))
        return
    latest = analyses[0]
    created = latest.get("created_at")
    with entity_card(
        "home-latest-analysis",
        latest.get("top_disease") or "Unknown",
        subtitle=f"Model prediction from {created:%b %d, %Y}" if hasattr(created, "strftime") else "Model prediction",
        status=("review", "reviewed" if latest.get("reviewed") else "unreviewed"),
        fields=[
            ("Model confidence", f"{float(latest.get('top_probability') or 0):.0%}"),
            ("Symptoms", ", ".join(format_symptom(name) for name in latest.get("symptoms") or []) or None),
        ],
        columns=2,
    ):
        st.page_link(page(ANALYSIS_HISTORY), label="See all analyses", icon=":material/arrow_forward:")


def render() -> None:
    user = st.session_state.get("authenticated_user") or {}
    email = user.get("email")
    now = datetime.now()

    actions = page_header(f"{_greeting(now)}, {user.get('first_name') or format_person_name(user)}",
                          "Your health activity at a glance")
    actions.page_link(page(NEW_ANALYSIS), label="New health analysis", icon=":material/add:")
    render_practitioner_notifications()

    upcoming, _ = list_for_patient(get_appointments_collection(), email)
    analyses = get_patient_analyses(get_analyses_collection(), email)
    prescriptions = list_prescriptions_for_patient(get_prescriptions_collection(), email)
    doctor = get_primary_practitioner(get_users_collection(), get_requests_collection(), email)

    metric_row(
        [
            ("Upcoming appointments", len(upcoming)),
            ("Health analyses", len(analyses)),
            ("Active prescriptions", sum(1 for item in prescriptions if item.get("status") == STATUS_FINALIZED),
             "Finalized simulated prescriptions from your doctor"),
        ],
        key="home",
    )

    left, right = st.columns(2, gap="large")
    with left:
        _render_next_appointment(upcoming)
    with right:
        _render_latest_analysis(analyses)

    section_header("Your doctor")
    if doctor is None:
        empty_state("You're not connected to a doctor yet",
                    "Connect with a primary health practitioner to book appointments and receive prescriptions.",
                    icon=":material/medical_services:", key="home-doctor", action_label="Find a doctor",
                    page=page(MY_DOCTORS))
    else:
        with card("home-doctor"):
            with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
                st.markdown(f"**{format_person_name(doctor, doctor=True)}**  \n"
                            f":gray[{doctor.get('speciality') or 'Primary health practitioner'}]", width="stretch")
                st.page_link(page(BOOK_APPOINTMENT), label="Book appointment", icon=":material/calendar_add_on:",
                             width="content")
                if prescriptions:
                    st.page_link(page(MY_PRESCRIPTIONS), label="View prescriptions", icon=":material/medication:",
                                 width="content")
