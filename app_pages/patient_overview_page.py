"""Doctor page showing one patient's profile and their disease-prediction history."""

from __future__ import annotations

import streamlit as st

from app_pages.patient_overview_service import get_patient_analyses, get_patient_overview, review_analysis
from app_pages.registration_page import get_analyses_collection, get_requests_collection, get_users_collection

VIEWING_PATIENT_KEY = "viewing_patient_email"
REVIEWING_ANALYSIS_KEY = "reviewing_analysis_id"


def open_patient_overview(patient_email: str) -> None:
    """Switch the doctor workspace to this patient's overview."""
    st.session_state[VIEWING_PATIENT_KEY] = str(patient_email or "").strip().lower()
    st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
    st.rerun()


def _close_patient_overview() -> None:
    st.session_state.pop(VIEWING_PATIENT_KEY, None)
    st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
    st.rerun()


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


def _render_review_panel(analysis: dict, patient_email: str) -> None:
    st.markdown("**Top predictions**")
    st.dataframe(
        [
            {"Rank": rank, "Disease": item.get("disease"), "Probability": f"{float(item.get('probability') or 0):.1%}"}
            for rank, item in enumerate(analysis.get("ranked") or [], start=1)
        ],
        use_container_width=True,
        hide_index=True,
    )
    if analysis.get("is_low_confidence"):
        st.warning("Low confidence: no disease reached the 50% confidence threshold.")

    notes = st.text_area(
        "Review notes",
        value=analysis.get("review_notes") or "",
        key=f"review_notes_{analysis['_id']}",
    )
    save_col, close_col = st.columns([1, 1])
    with save_col:
        if st.button("Save review", key=f"save_review_{analysis['_id']}", type="primary"):
            user = st.session_state.get("authenticated_user") or {}
            review_analysis(get_analyses_collection(), analysis["_id"], patient_email, user.get("email"), notes)
            st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
            st.session_state["patient_overview_flash"] = "Review saved."
            st.rerun()
    with close_col:
        if st.button("Close", key=f"close_review_{analysis['_id']}"):
            st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
            st.rerun()


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

        if st.session_state.get(REVIEWING_ANALYSIS_KEY) == analysis_id:
            _render_review_panel(analysis, patient_email)
        elif st.button("Review Analysis", key=f"review_analysis_{analysis_id}"):
            st.session_state[REVIEWING_ANALYSIS_KEY] = analysis_id
            st.rerun()


def render(patient_email: str) -> None:
    """Render the Patient Overview for the signed-in doctor."""
    if st.button("← Back to dashboard", key="patient_overview_back"):
        _close_patient_overview()

    st.title("Patient Overview")

    user = st.session_state.get("authenticated_user") or {}
    patient = get_patient_overview(
        get_users_collection(),
        get_requests_collection(),
        user.get("email"),
        patient_email,
    )
    if patient is None:
        st.error("This patient could not be found, or you are not their Primary Health Practitioner.")
        return

    flash = st.session_state.pop("patient_overview_flash", None)
    if flash:
        st.success(flash)

    _render_profile(patient)

    st.subheader("Analysis History")
    analyses = get_patient_analyses(get_analyses_collection(), patient["email"])
    if not analyses:
        st.info("This patient has not run any disease predictions yet.")
        return

    for analysis in analyses:
        _render_analysis(analysis, patient["email"])
