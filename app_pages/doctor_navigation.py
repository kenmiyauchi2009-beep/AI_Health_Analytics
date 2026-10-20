"""Separate pages (own URLs) for the doctor workspace: dashboard -> patient overview -> review analysis.

The selected patient and analysis travel between pages in session state, which
st.switch_page keeps.
"""

from __future__ import annotations

import streamlit as st

DASHBOARD = "doctor-dashboard"
PATIENT_OVERVIEW = "patient-overview"
REVIEW_ANALYSIS = "review-analysis"

VIEWING_PATIENT_KEY = "viewing_patient_email"
REVIEWING_ANALYSIS_KEY = "reviewing_analysis_id"


def doctor_pages() -> dict[str, st.Page]:
    # Imported here because these page modules import go_to() from this one.
    from app_pages.analysis_review_page import render_page as render_analysis_review_page
    from app_pages.dashboard_page import render_doctor_dashboard
    from app_pages.patient_overview_page import render_page as render_patient_overview_page

    return {
        DASHBOARD: st.Page(render_doctor_dashboard, title="Doctor Dashboard", url_path=DASHBOARD, default=True),
        PATIENT_OVERVIEW: st.Page(render_patient_overview_page, title="Patient Overview", url_path=PATIENT_OVERVIEW),
        REVIEW_ANALYSIS: st.Page(render_analysis_review_page, title="Review Analysis", url_path=REVIEW_ANALYSIS),
    }


def go_to(page: str) -> None:
    """Open another doctor page."""
    st.switch_page(doctor_pages()[page])
