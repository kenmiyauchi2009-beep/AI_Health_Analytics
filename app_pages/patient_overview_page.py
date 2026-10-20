"""Doctor page showing one patient's profile and their disease-prediction history."""

from __future__ import annotations

import streamlit as st

from app_pages.doctor_navigation import (
    DASHBOARD,
    PATIENT_OVERVIEW,
    REVIEW_ANALYSIS,
    REVIEWING_ANALYSIS_KEY,
    VIEWING_PATIENT_KEY,
    go_to,
)
from app_pages.patient_overview_service import get_patient_analyses, get_patient_overview, review_analysis
from app_pages.registration_page import get_analyses_collection, get_requests_collection, get_users_collection

def open_patient_overview(patient_email: str) -> None:
    """Switch the doctor workspace to this patient's overview."""
    st.session_state[VIEWING_PATIENT_KEY] = str(patient_email or "").strip().lower()
    st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
    go_to(PATIENT_OVERVIEW)


def _close_patient_overview() -> None:
    st.session_state.pop(VIEWING_PATIENT_KEY, None)
    st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
    go_to(DASHBOARD)


def _format_time(value) -> str:
    return value.strftime("%b %d, %Y %I:%M %p") if hasattr(value, "strftime") else "Unknown date"


def _format_symptom(name: str) -> str:
    return str(name).replace("_", " ").strip().capitalize()


def _render_profile(patient: dict) -> None:
    st.subheader("Patient Profile")
    with st.container(border=True):
        st.write(f"**Name:** {patient['name']}")
        st.write(f"**Age:** {patient['age'] if patient['age'] is not None else 'Not provided'}")
        conditions = ", ".join(patient["known_conditions"]) or "None recorded"
        st.write(f"**Known conditions:** {conditions}")


def _render_analysis(analysis: dict, patient_email: str) -> None:
    analysis_id = str(analysis["_id"])
    with st.container(border=True):
        header_col, status_col = st.columns([3, 1])
        with header_col:
            st.write(f"**Date:** {_format_time(analysis.get('created_at'))}")
        with status_col:
            if analysis.get("reviewed"):
                st.caption(f"✅ Reviewed {_format_time(analysis.get('reviewed_at'))}")
            else:
                st.caption("🕒 Not reviewed")

        symptoms = ", ".join(_format_symptom(symptom) for symptom in analysis.get("symptoms") or [])
        st.write(f"**Symptoms:** {symptoms or 'None recorded'}")
        st.write(f"**Prediction:** {analysis.get('top_disease') or 'Unknown'}")
        st.write(f"**Confidence:** {float(analysis.get('top_probability') or 0):.1%}")
        if analysis.get("reviewed") and analysis.get("review_notes"):
            st.write(f"**Review notes:** {analysis['review_notes']}")

        if st.button("Review Analysis", key=f"review_analysis_{analysis_id}"):
            user = st.session_state.get("authenticated_user") or {}
            review_analysis(get_analyses_collection(), analysis["_id"], patient_email, user.get("email"))
            st.session_state[REVIEWING_ANALYSIS_KEY] = analysis_id
            go_to(REVIEW_ANALYSIS)


def load_viewed_patient() -> dict | None:
    """Return the patient picked on the dashboard, or show why it can't be shown."""
    patient_email = st.session_state.get(VIEWING_PATIENT_KEY)
    if not patient_email:
        st.info("No patient is selected. Go back to the dashboard and click **View Patient**.")
        return None

    user = st.session_state.get("authenticated_user") or {}
    patient = get_patient_overview(
        get_users_collection(),
        get_requests_collection(),
        user.get("email"),
        patient_email,
    )
    if patient is None:
        st.error("This patient could not be found, or you are not their Primary Health Practitioner.")
    return patient


def render_page() -> None:
    """Patient Overview page for the patient picked on the doctor dashboard."""
    if st.button("← Back to dashboard", key="patient_overview_back"):
        _close_patient_overview()

    patient = load_viewed_patient()
    if patient is None:
        return

    st.title("Patient Overview")
    _render_profile(patient)

    st.subheader("Analysis History")
    analyses = get_patient_analyses(get_analyses_collection(), patient["email"])
    if not analyses:
        st.info("This patient has not run any disease predictions yet.")
        return

    for analysis in analyses:
        _render_analysis(analysis, patient["email"])
