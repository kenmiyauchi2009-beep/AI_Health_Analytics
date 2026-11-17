"""Doctor page showing one patient's profile and their disease-prediction history."""

from __future__ import annotations

import streamlit as st

from app_pages.doctor_navigation import (
    MY_PATIENTS,
    PATIENT_OVERVIEW,
    PRESCRIPTIONS,
    REVIEW_ANALYSIS,
    REVIEWING_ANALYSIS_KEY,
    VIEWING_PATIENT_KEY,
    go_to,
    page,
)
from app_pages.patient_overview_service import get_patient_analyses, get_patient_overview, review_analysis
from app_pages.prescription_service import (
    STATUS_DRAFT,
    STATUS_FINALIZED,
    STATUS_VOIDED,
    list_prescriptions_for_doctor,
)
from app_pages.registration_page import (
    get_analyses_collection,
    get_prescriptions_collection,
    get_requests_collection,
    get_users_collection,
)
from ui.components import card, empty_state, entity_card, field_grid, metric_row, page_header, section_header


def open_patient_overview(patient_email: str) -> None:
    """Switch the doctor workspace to this patient's overview."""
    st.session_state[VIEWING_PATIENT_KEY] = str(patient_email or "").strip().lower()
    st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
    go_to(PATIENT_OVERVIEW)


def _format_time(value) -> str:
    # Analyses are stored in naive UTC.
    return f"{value.strftime('%b %d, %Y %I:%M %p')} UTC" if hasattr(value, "strftime") else "Unknown date"


def _format_symptom(name: str) -> str:
    return str(name).replace("_", " ").strip().capitalize()


def _render_profile(patient: dict) -> None:
    with card("patient-profile"):
        field_grid(
            [
                ("Age", patient["age"] if patient["age"] is not None else "Not provided"),
                ("Known conditions", ", ".join(patient["known_conditions"]) or "None recorded"),
                ("Email", patient["email"]),
            ]
        )


def _render_analysis(analysis: dict, patient_email: str) -> None:
    analysis_id = str(analysis["_id"])
    reviewed = bool(analysis.get("reviewed"))
    symptoms = ", ".join(_format_symptom(symptom) for symptom in analysis.get("symptoms") or [])
    subtitle = f"Reviewed {_format_time(analysis.get('reviewed_at'))}" if reviewed else "Waiting for your review"

    container = entity_card(
        f"analysis-{analysis_id}",
        f"Analysis {_format_time(analysis.get('created_at'))}",
        subtitle=subtitle,
        status=("review", "reviewed" if reviewed else "unreviewed"),
        fields=[
            ("Predicted condition", analysis.get("top_disease") or "Unknown"),
            ("Model confidence", f"{float(analysis.get('top_probability') or 0):.1%}"),
            ("Reported symptoms", symptoms or "None recorded"),
        ],
    )
    with container:
        if analysis.get("is_low_confidence"):
            st.caption(":material/warning: Low model confidence: no condition reached the confidence threshold.")
        if reviewed and analysis.get("review_notes"):
            st.markdown(f":gray[Review notes]  \n{analysis['review_notes']}")
        with st.container(horizontal=True, horizontal_alignment="right"):
            clicked = st.button(
                "Review analysis",
                key=f"review_analysis_{analysis_id}",
                type="secondary" if reviewed else "primary",
                icon=":material/clinical_notes:",
            )
        if clicked:
            user = st.session_state.get("authenticated_user") or {}
            review_analysis(get_analyses_collection(), analysis["_id"], patient_email, user.get("email"))
            st.session_state[REVIEWING_ANALYSIS_KEY] = analysis_id
            go_to(REVIEW_ANALYSIS)


def _render_analysis_history(patient: dict, analyses: list[dict]) -> None:
    section_header("Analysis history", "Disease predictions the patient has run, newest first")
    if not analyses:
        empty_state(
            "No analyses yet",
            f"When {patient['name']} runs a disease prediction, it appears here for you to review.",
            icon=":material/clinical_notes:",
            key="patient-analyses",
        )
        return
    for analysis in analyses:
        _render_analysis(analysis, patient["email"])


def _render_prescriptions_section(prescriptions: list[dict]) -> None:
    actions = section_header(
        "Prescriptions",
        "Simulated prescriptions for educational demonstration only. Nothing is sent to a pharmacy.",
    )
    if actions.button("View prescriptions", key="patient_overview_prescriptions", icon=":material/medication:"):
        go_to(PRESCRIPTIONS)
    with card("patient-prescriptions"):
        field_grid(
            [
                (label, sum(1 for prescription in prescriptions if prescription.get("status") == status))
                for status, label in [
                    (STATUS_DRAFT, "Your drafts"),
                    (STATUS_FINALIZED, "Finalized"),
                    (STATUS_VOIDED, "Voided"),
                ]
            ]
        )


def load_viewed_patient() -> dict | None:
    """Return the patient picked on My patients, or show why it can't be shown."""
    patient_email = st.session_state.get(VIEWING_PATIENT_KEY)
    if not patient_email:
        empty_state(
            "No patient selected",
            "Open a patient from My patients to see their details.",
            icon=":material/person_search:",
            key="no-patient",
            action_label="Go to my patients",
            page=page(MY_PATIENTS),
        )
        return None

    user = st.session_state.get("authenticated_user") or {}
    patient = get_patient_overview(
        get_users_collection(),
        get_requests_collection(),
        user.get("email"),
        patient_email,
    )
    if patient is None:
        empty_state(
            "This patient can't be shown",
            "The patient could not be found, or you are no longer their primary health practitioner.",
            icon=":material/person_off:",
            key="patient-unavailable",
            action_label="Go to my patients",
            page=page(MY_PATIENTS),
        )
    return patient


def render_page() -> None:
    """Patient overview page for the patient picked on My patients."""
    patient = load_viewed_patient()
    if patient is None:
        return

    user = st.session_state.get("authenticated_user") or {}
    analyses = get_patient_analyses(get_analyses_collection(), patient["email"])
    prescriptions = list_prescriptions_for_doctor(get_prescriptions_collection(), user.get("email"), patient["email"])

    page_header(
        patient["name"],
        "Profile, analysis history and prescriptions for a patient in your care",
        breadcrumb=[("My patients", page(MY_PATIENTS)), (patient["name"], None)],
    )
    _render_profile(patient)
    metric_row(
        [
            ("Analyses", len(analyses), "Disease predictions this patient has run"),
            ("Not reviewed", sum(1 for analysis in analyses if not analysis.get("reviewed")),
             "Analyses you haven't opened yet"),
            ("Prescriptions", len(prescriptions), "Simulated prescriptions you can see for this patient"),
        ],
        key="patient-overview",
    )
    _render_analysis_history(patient, analyses)
    _render_prescriptions_section(prescriptions)
