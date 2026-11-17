"""AI assistant pages. The assistant explains saved ML results; it always works on one chosen analysis."""

from __future__ import annotations

import streamlit as st

from app_pages.analysis_review_service import analysis_to_prediction_result, assign_cluster, build_doctor_context
from app_pages.patient_overview_service import get_patient_analyses, get_patient_overview
from app_pages.registration_page import (
    get_accepted_doctor_requests,
    get_analyses_collection,
    get_requests_collection,
    get_users_collection,
)
from assistant.patient_analysis_context import PatientAnalysisContext
from assistant.ui_view import render_doctor_assistant_panel, render_patient_assistant_panel
from prediction.cluster_controller import ClusterController
from prediction.ui_view import format_symptom, load_cluster_assets
from ui.components import card, empty_state, field_grid, page_header, section_header

CURRENT_SESSION = "current"


def _cluster_controller() -> ClusterController | None:
    try:
        model, symptoms, metadata = load_cluster_assets()
        return ClusterController(model=model, symptoms=symptoms, metadata=metadata)
    except Exception:
        return None


def _assignment_for(symptoms: list[str]):
    controller = _cluster_controller()
    return assign_cluster(controller, symptoms) if controller is not None else None


def _analysis_label(analysis: dict) -> str:
    created = analysis.get("created_at")
    when = f"{created:%b %d, %Y}" if hasattr(created, "strftime") else "Unknown date"
    return f"{analysis.get('top_disease') or 'Unknown'}, {when}"


def _render_summary(context: PatientAnalysisContext) -> None:
    """What the conversation is about, with the same provenance labels as the results page."""
    with card("assistant-summary"):
        prediction = context.prediction
        fields = [("Symptoms", ", ".join(format_symptom(name) for name in context.selected_symptoms) or None)]
        if prediction is not None:
            fields += [("Model prediction", prediction.top_disease),
                       ("Model confidence", f"{prediction.top_probability:.0%}")]
        if context.cluster_assignment is not None:
            fields.append(("Patient subgroup", f"Cluster {context.cluster_assignment.cluster_id}"))
        field_grid(fields, columns=len(fields))


# ---------------------------------------------------------------- patient


def render_patient() -> None:
    from app_pages.analysis_history_page import ASSISTANT_ANALYSIS_KEY
    from app_pages.patient_navigation import NEW_ANALYSIS, page

    user = st.session_state.get("authenticated_user") or {}
    page_header("AI assistant", "Ask questions about your analysis results in plain language")

    analyses = get_patient_analyses(get_analyses_collection(), user.get("email"))
    session_result = st.session_state.get("latest_prediction")
    options = ([CURRENT_SESSION] if session_result is not None else []) + [str(item["_id"]) for item in analyses]
    if not options:
        empty_state("Nothing to discuss yet", "Run a health analysis first, then ask the assistant about it.",
                    icon=":material/auto_awesome:", key="assistant", action_label="Start a new analysis",
                    page=page(NEW_ANALYSIS))
        return

    by_id = {str(item["_id"]): item for item in analyses}
    preselected = st.session_state.pop(ASSISTANT_ANALYSIS_KEY, None)
    if preselected in options:
        st.session_state["assistant_choice"] = preselected
    choice = st.selectbox(
        "Analysis",
        options=options,
        format_func=lambda key: "Your latest analysis (this session)" if key == CURRENT_SESSION
        else _analysis_label(by_id[key]),
        key="assistant_choice",
    )

    if choice == CURRENT_SESSION:
        context = PatientAnalysisContext(
            selected_symptoms=list(st.session_state.get("selected_symptoms") or []),
            prediction=session_result,
            cluster_assignment=st.session_state.get("latest_cluster_assignment"),
        )
        conversation_key = "ai_conversation"
    else:
        analysis = by_id[choice]
        symptoms = list(analysis.get("symptoms") or [])
        context = PatientAnalysisContext(
            selected_symptoms=symptoms,
            prediction=analysis_to_prediction_result(analysis),
            cluster_assignment=_assignment_for(symptoms),
        )
        conversation_key = f"patient_ai_{choice}"

    _render_summary(context)
    with card("assistant-chat", lane="ai"):
        section_header("Conversation", badge="ai")
        render_patient_assistant_panel(context, conversation_key)


# ---------------------------------------------------------------- doctor


def render_doctor() -> None:
    from app_pages.doctor_navigation import (
        MY_PATIENTS,
        REVIEW_ANALYSIS,
        REVIEWING_ANALYSIS_KEY,
        VIEWING_PATIENT_KEY,
        go_to,
        page,
    )

    user = st.session_state.get("authenticated_user") or {}
    doctor_email = user.get("email")
    page_header("AI assistant", "Discuss a patient's saved analysis: summaries, uncertainty, comparisons")

    connections = get_accepted_doctor_requests(doctor_email)
    patients = {str(item.get("patient_email") or "").lower(): item.get("patient_name") or item.get("patient_email")
                for item in connections if item.get("patient_email")}
    if not patients:
        empty_state("No patients yet", "The assistant works on your patients' analyses.", icon=":material/group:",
                    key="doctor-assistant", action_label="Go to my patients", page=page(MY_PATIENTS))
        return

    patient_col, analysis_col = st.columns(2)
    patient_email = patient_col.selectbox("Patient", options=list(patients), format_func=patients.get,
                                          key="doctor_assistant_patient")
    patient = get_patient_overview(get_users_collection(), get_requests_collection(), doctor_email, patient_email)
    analyses = get_patient_analyses(get_analyses_collection(), patient_email)
    if patient is None or not analyses:
        with analysis_col:
            st.selectbox("Analysis", options=[], placeholder="No analyses yet", key="doctor_assistant_analysis_none")
        empty_state("This patient has no analyses yet", "Analyses appear here after the patient runs one.",
                    icon=":material/stethoscope:", key="doctor-assistant-analyses")
        return

    by_id = {str(item["_id"]): item for item in analyses}
    analysis_id = analysis_col.selectbox("Analysis", options=list(by_id), format_func=lambda key: _analysis_label(by_id[key]),
                                         key=f"doctor_assistant_analysis_{patient_email}")
    analysis = by_id[analysis_id]
    context = build_doctor_context(analysis, analyses, _assignment_for(list(analysis.get("symptoms") or [])),
                                   patient.get("known_conditions"))

    _render_summary(context)

    if st.button("Open full review", icon=":material/clinical_notes:", key="doctor_assistant_review"):
        st.session_state[VIEWING_PATIENT_KEY] = patient_email
        st.session_state[REVIEWING_ANALYSIS_KEY] = analysis_id
        go_to(REVIEW_ANALYSIS)
    with card("doctor-assistant-chat", lane="ai"):
        section_header("Conversation", "Ask about this analysis, the model's uncertainty, the patient subgroup, or how "
                       "it compares with the patient's earlier analyses", badge="ai")
        # Same conversation key as the Review analysis page, so the discussion carries over.
        render_doctor_assistant_panel(context, conversation_key=f"doctor_ai_{analysis_id}")
