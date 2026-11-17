"""Patient pages (each with its own URL) and the sidebar groups that list them."""

from __future__ import annotations

import streamlit as st

HOME = "home"
NEW_ANALYSIS = "new-analysis"
ANALYSIS_HISTORY = "analysis-history"
MY_PRESCRIPTIONS = "my-prescriptions"
HEALTH_PROFILE = "health-profile"
BOOK_APPOINTMENT = "book-appointment"
MY_APPOINTMENTS = "my-appointments"
MY_DOCTORS = "my-doctors"
AI_ASSISTANT = "ai-assistant"
DATA_EXPLORER = "data-explorer"
PROFILE = "profile"

SIDEBAR_GROUPS = [
    ("Overview", [HOME]),
    ("My health", [NEW_ANALYSIS, ANALYSIS_HISTORY, MY_PRESCRIPTIONS, HEALTH_PROFILE]),
    ("Appointments", [BOOK_APPOINTMENT, MY_APPOINTMENTS, MY_DOCTORS]),
    ("Tools", [AI_ASSISTANT, DATA_EXPLORER]),
    ("Account", [PROFILE]),
]


def patient_pages() -> dict[str, st.Page]:
    # Imported here so page modules can import page()/go_to() from this one.
    from app_pages.account_profile_page import render as render_profile_page
    from app_pages.ai_assistant_page import render_patient as render_ai_assistant_page
    from app_pages.analysis_history_page import render as render_analysis_history_page
    from app_pages.appointment_patient_page import render_book_page, render_my_appointments_page
    from app_pages.dashboard_page import render_patient_dashboard as render_data_explorer_page
    from app_pages.health_profile_page import render as render_health_profile_page
    from app_pages.patient_home_page import render as render_home_page
    from app_pages.practitioner_page import render as render_my_doctors_page
    from app_pages.prediction_page import render as render_new_analysis_page
    from app_pages.prescription_patient_page import render as render_my_prescriptions_page

    def page(render, title, url_path, icon, **kwargs):
        return st.Page(render, title=title, url_path=url_path, icon=icon, **kwargs)

    return {
        HOME: page(render_home_page, "Home", HOME, ":material/home:", default=True),
        NEW_ANALYSIS: page(render_new_analysis_page, "New health analysis", NEW_ANALYSIS, ":material/stethoscope:"),
        ANALYSIS_HISTORY: page(render_analysis_history_page, "Analysis history", ANALYSIS_HISTORY,
                               ":material/history:"),
        MY_PRESCRIPTIONS: page(render_my_prescriptions_page, "My prescriptions", MY_PRESCRIPTIONS,
                               ":material/medication:"),
        HEALTH_PROFILE: page(render_health_profile_page, "Health profile", HEALTH_PROFILE,
                             ":material/monitor_heart:"),
        BOOK_APPOINTMENT: page(render_book_page, "Book appointment", BOOK_APPOINTMENT, ":material/calendar_add_on:"),
        MY_APPOINTMENTS: page(render_my_appointments_page, "My appointments", MY_APPOINTMENTS,
                              ":material/calendar_month:"),
        MY_DOCTORS: page(render_my_doctors_page, "My doctors", MY_DOCTORS, ":material/medical_services:"),
        AI_ASSISTANT: page(render_ai_assistant_page, "AI assistant", AI_ASSISTANT, ":material/auto_awesome:"),
        DATA_EXPLORER: page(render_data_explorer_page, "Data explorer", DATA_EXPLORER, ":material/table_chart:"),
        PROFILE: page(render_profile_page, "Profile", PROFILE, ":material/account_circle:"),
    }


def page(key: str) -> st.Page:
    """The st.Page for a patient page, for st.page_link and breadcrumbs."""
    return patient_pages()[key]


def go_to(key: str) -> None:
    st.switch_page(patient_pages()[key])
