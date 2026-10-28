"""Separate pages (own URLs) for the doctor workspace: dashboard -> patient overview -> review analysis.

The selected patient and analysis travel between pages in session state, which
st.switch_page keeps.
"""

from __future__ import annotations

import streamlit as st

DASHBOARD = "doctor-dashboard"
PATIENT_OVERVIEW = "patient-overview"
REVIEW_ANALYSIS = "review-analysis"
PRESCRIPTIONS = "patient-prescriptions"
PRESCRIPTION_EDITOR = "prescription-editor"
PRESCRIPTION_DETAIL = "prescription-detail"

VIEWING_PATIENT_KEY = "viewing_patient_email"
REVIEWING_ANALYSIS_KEY = "reviewing_analysis_id"
# str(_id) of the prescription being viewed or edited; the editor uses NEW_PRESCRIPTION for a new one.
VIEWING_PRESCRIPTION_KEY = "viewing_prescription_id"
EDITING_PRESCRIPTION_KEY = "editing_prescription_id"
NEW_PRESCRIPTION = "new"


def doctor_pages() -> dict[str, st.Page]:
    # Imported here because these page modules import go_to() from this one.
    from app_pages.analysis_review_page import render_page as render_analysis_review_page
    from app_pages.dashboard_page import render_doctor_dashboard
    from app_pages.patient_overview_page import render_page as render_patient_overview_page
    from app_pages.prescription_doctor_pages import (
        render_prescription_detail_page,
        render_prescription_editor_page,
        render_prescriptions_page,
    )

    return {
        DASHBOARD: st.Page(render_doctor_dashboard, title="Doctor Dashboard", url_path=DASHBOARD, default=True),
        PATIENT_OVERVIEW: st.Page(render_patient_overview_page, title="Patient Overview", url_path=PATIENT_OVERVIEW),
        REVIEW_ANALYSIS: st.Page(render_analysis_review_page, title="Review Analysis", url_path=REVIEW_ANALYSIS),
        PRESCRIPTIONS: st.Page(render_prescriptions_page, title="Prescriptions", url_path=PRESCRIPTIONS),
        PRESCRIPTION_EDITOR: st.Page(
            render_prescription_editor_page, title="Prescription Editor", url_path=PRESCRIPTION_EDITOR
        ),
        PRESCRIPTION_DETAIL: st.Page(
            render_prescription_detail_page, title="Prescription", url_path=PRESCRIPTION_DETAIL
        ),
    }


def go_to(page: str) -> None:
    """Open another doctor page."""
    st.switch_page(doctor_pages()[page])
