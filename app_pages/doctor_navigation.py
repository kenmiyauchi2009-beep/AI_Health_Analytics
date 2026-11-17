"""Doctor workspace pages (each with its own URL) and the sidebar groups that list them.

Detail pages (patient overview, analysis review, prescription editor/detail) aren't in the sidebar;
they're opened from lists. The selected patient, analysis and prescription travel between pages in
session state, which st.switch_page keeps.
"""

from __future__ import annotations

import streamlit as st

DASHBOARD = "doctor-dashboard"
MY_PATIENTS = "my-patients"
PATIENT_REQUESTS = "patient-requests"
PATIENT_OVERVIEW = "patient-overview"
REVIEW_ANALYSIS = "review-analysis"
APPOINTMENT_REQUESTS = "appointment-requests"
APPOINTMENTS = "appointments"
AVAILABILITY = "availability"
DOCTOR_NOTES = "doctor-notes"
PRESCRIPTION_MANAGEMENT = "prescription-management"
PRESCRIPTIONS = "patient-prescriptions"
PRESCRIPTION_EDITOR = "prescription-editor"
PRESCRIPTION_DETAIL = "prescription-detail"
AI_ASSISTANT = "doctor-ai-assistant"
PROFILE = "doctor-profile"

VIEWING_PATIENT_KEY = "viewing_patient_email"
REVIEWING_ANALYSIS_KEY = "reviewing_analysis_id"
# str(_id) of the prescription being viewed or edited; the editor uses NEW_PRESCRIPTION for a new one.
VIEWING_PRESCRIPTION_KEY = "viewing_prescription_id"
EDITING_PRESCRIPTION_KEY = "editing_prescription_id"
NEW_PRESCRIPTION = "new"

SIDEBAR_GROUPS = [
    ("Overview", [DASHBOARD]),
    ("Patient management", [MY_PATIENTS, PATIENT_REQUESTS]),
    ("Appointments", [APPOINTMENT_REQUESTS, APPOINTMENTS, AVAILABILITY]),
    ("Clinical workspace", [DOCTOR_NOTES, PRESCRIPTION_MANAGEMENT, AI_ASSISTANT]),
    ("Account", [PROFILE]),
]


def doctor_pages() -> dict[str, st.Page]:
    # Imported here because these page modules import go_to() from this one.
    from app_pages.account_profile_page import render as render_profile_page
    from app_pages.ai_assistant_page import render_doctor as render_ai_assistant_page
    from app_pages.analysis_review_page import render_page as render_analysis_review_page
    from app_pages.appointment_doctor_page import render_page as render_appointments_page
    from app_pages.appointment_doctor_page import render_requests_page as render_appointment_requests_page
    from app_pages.availability_page import render_page as render_availability_page
    from app_pages.dashboard_page import (
        render_doctor_dashboard,
        render_my_patients_page,
        render_patient_requests_page,
    )
    from app_pages.doctor_notes_page import render as render_doctor_notes_page
    from app_pages.patient_overview_page import render_page as render_patient_overview_page
    from app_pages.prescription_doctor_pages import (
        render_prescription_detail_page,
        render_prescription_editor_page,
        render_prescriptions_page,
    )
    from app_pages.prescription_management_page import render as render_prescription_management_page

    def page(render, title, url_path, icon, **kwargs):
        return st.Page(render, title=title, url_path=url_path, icon=icon, **kwargs)

    return {
        DASHBOARD: page(render_doctor_dashboard, "Dashboard", DASHBOARD, ":material/space_dashboard:", default=True),
        MY_PATIENTS: page(render_my_patients_page, "My patients", MY_PATIENTS, ":material/group:"),
        PATIENT_REQUESTS: page(render_patient_requests_page, "Patient requests", PATIENT_REQUESTS,
                               ":material/person_add:"),
        PATIENT_OVERVIEW: page(render_patient_overview_page, "Patient overview", PATIENT_OVERVIEW,
                               ":material/person:"),
        REVIEW_ANALYSIS: page(render_analysis_review_page, "Review analysis", REVIEW_ANALYSIS,
                              ":material/clinical_notes:"),
        APPOINTMENT_REQUESTS: page(render_appointment_requests_page, "Appointment requests", APPOINTMENT_REQUESTS,
                                   ":material/inbox:"),
        APPOINTMENTS: page(render_appointments_page, "My appointments", APPOINTMENTS, ":material/calendar_month:"),
        AVAILABILITY: page(render_availability_page, "My availability", AVAILABILITY, ":material/schedule:"),
        DOCTOR_NOTES: page(render_doctor_notes_page, "Doctor's notes", DOCTOR_NOTES, ":material/sticky_note_2:"),
        PRESCRIPTION_MANAGEMENT: page(render_prescription_management_page, "Prescriptions", PRESCRIPTION_MANAGEMENT,
                                      ":material/medication:"),
        PRESCRIPTIONS: page(render_prescriptions_page, "Patient prescriptions", PRESCRIPTIONS,
                            ":material/medication:"),
        PRESCRIPTION_EDITOR: page(render_prescription_editor_page, "Prescription editor", PRESCRIPTION_EDITOR,
                                  ":material/edit_note:"),
        PRESCRIPTION_DETAIL: page(render_prescription_detail_page, "Prescription", PRESCRIPTION_DETAIL,
                                  ":material/description:"),
        AI_ASSISTANT: page(render_ai_assistant_page, "AI assistant", AI_ASSISTANT, ":material/auto_awesome:"),
        PROFILE: page(render_profile_page, "Profile", PROFILE, ":material/account_circle:"),
    }


def page(key: str) -> st.Page:
    """The st.Page for a doctor page, for st.page_link and breadcrumbs."""
    return doctor_pages()[key]


def go_to(key: str) -> None:
    """Open another doctor page."""
    st.switch_page(doctor_pages()[key])
