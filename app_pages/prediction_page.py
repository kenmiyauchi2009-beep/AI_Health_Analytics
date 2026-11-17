"""New health analysis: pick symptoms, then see the model prediction, the patient subgroup and an AI explanation.

One "Analyze symptoms" click runs both ML models on the same symptom list and saves the prediction to the
patient's history. Results stay on screen (in session state) until the next analysis.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.patient_navigation import ANALYSIS_HISTORY, page
from app_pages.patient_overview_service import save_analysis
from app_pages.registration_page import get_analyses_collection
from assistant.ui_view import render_assistant_panel
from prediction.cluster_controller import ClusterController
from prediction.controller import DiseasePredictionController
from prediction.ui_view import (
    format_symptom,
    load_cluster_assets,
    load_prediction_assets,
    render_analyze_button,
    render_asset_uploaders,
    render_cluster_browse,
    render_cluster_compare,
    render_model_output,
    render_subgroup_result,
    render_symptom_picker,
    run_cluster_assignment,
    run_prediction,
)
from ui.components import card, error_message, page_header, section_header

ANALYZED_AT_KEY = "analyzed_at"


def _save_to_history(selected_symptoms: list[str], result) -> bool:
    """Keep the prediction in the patient's analysis history so their doctor can review it."""
    user = st.session_state.get("authenticated_user") or {}
    try:
        return save_analysis(get_analyses_collection(), user.get("email"), selected_symptoms, result) is not None
    except Exception as error:  # pragma: no cover - saving history must not block the result
        st.warning(f"Your result couldn't be saved to your history: {error}", icon=":material/warning:")
        return False


def _load_cluster_controller() -> ClusterController | None:
    try:
        model, symptoms, metadata = load_cluster_assets()
        return ClusterController(model=model, symptoms=symptoms, metadata=metadata)
    except Exception as error:
        error_message(f"The patient subgroup model couldn't be loaded: {error}.",
                      "Disease prediction still works; subgroups will be skipped.")
        return None


def _analyze(model, symptoms, cluster_controller, selected: list[str]) -> None:
    """Run both models on the same symptoms and keep the results for this session."""
    with st.spinner("Analyzing your symptoms…"):
        result = run_prediction(DiseasePredictionController(model=model, symptoms=symptoms), selected)
        assignment = None
        if cluster_controller is not None:
            known = [name for name in selected if name in cluster_controller.symptoms.names]
            if known:
                assignment = run_cluster_assignment(cluster_controller, known)
    st.session_state.latest_prediction = result
    st.session_state.latest_cluster_assignment = assignment
    st.session_state.selected_symptoms = list(selected)
    st.session_state[ANALYZED_AT_KEY] = datetime.now()
    # A new analysis starts a new conversation with the assistant.
    st.session_state.pop("ai_conversation", None)
    if _save_to_history(selected, result):
        st.toast("Saved to your analysis history", icon=":material/check_circle:")


def _render_results(cluster_controller) -> None:
    result = st.session_state.get("latest_prediction")
    if result is None:
        return
    analyzed = st.session_state.get("selected_symptoms") or []
    current = st.session_state.get("symptom_picker") or []

    st.divider()
    actions = section_header(
        "Step 2: your results",
        f"Based on {len(analyzed)} symptom{'s' if len(analyzed) != 1 else ''}: "
        + ", ".join(format_symptom(name) for name in analyzed),
    )
    actions.page_link(page(ANALYSIS_HISTORY), label="Analysis history", icon=":material/history:")
    if sorted(current) != sorted(analyzed):
        st.info("You've changed your symptoms since this analysis. Select **Analyze symptoms** to update the results.",
                icon=":material/info:")

    render_model_output(result)

    assignment = st.session_state.get("latest_cluster_assignment")
    if assignment is not None:
        render_subgroup_result(assignment)
    if cluster_controller is not None:
        with st.expander("Explore all patient subgroups", icon=":material/hub:"):
            render_cluster_browse(cluster_controller)
            st.divider()
            render_cluster_compare(cluster_controller)

    with card("ai-explanation", lane="ai"):
        section_header("Ask about your results", "Plain-language explanations of the results above", badge="ai")
        render_assistant_panel()


def render() -> None:
    """New health analysis page."""
    page_header(
        "New health analysis",
        "Select your symptoms and get a model prediction, the patient subgroup you resemble, and an explanation. "
        "This is not a medical diagnosis.",
    )

    model_file, symptoms_file, metadata_file = None, None, None
    with card("symptoms"):
        section_header("Step 1: your symptoms", "Search the symptom list and add everything you're experiencing")
        try:
            # Uploaders are read before the picker so custom symptom lists apply immediately.
            model_file = st.session_state.get("model_uploader")
            symptoms_file = st.session_state.get("symptoms_uploader")
            metadata_file = st.session_state.get("metadata_uploader")
            model, symptoms, metadata = load_prediction_assets(
                model_file=model_file, symptoms_file=symptoms_file, metadata_file=metadata_file
            )
        except Exception as error:
            error_message(f"The prediction model couldn't be loaded: {error}.",
                          "Remove any custom model files below or check the models/ folder.")
            render_asset_uploaders()
            return

        selected = render_symptom_picker(symptoms.names)
        analyze = render_analyze_button(disabled=not selected)

    cluster_controller = _load_cluster_controller()
    if analyze:
        try:
            _analyze(model, symptoms, cluster_controller, selected)
        except ValueError as error:
            error_message(str(error))

    _render_results(cluster_controller)

    st.divider()
    render_asset_uploaders()
    if metadata is not None:
        st.caption(
            f"Model: {metadata.get('model_type', 'unknown')}, {metadata.get('num_features', len(symptoms.names))} "
            f"symptoms, {len(metadata.get('disease_labels', [])) or 'n/a'} conditions."
        )
