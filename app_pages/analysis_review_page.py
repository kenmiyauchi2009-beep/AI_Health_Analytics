"""Doctor page showing the full ML output for one of a patient's saved analyses."""

from __future__ import annotations

import streamlit as st

from app_pages.analysis_review_service import (
    analysis_to_prediction_result,
    assign_cluster,
    build_doctor_context,
    explain_cluster_match,
    format_analysis_date,
)
from app_pages.doctor_navigation import PATIENT_OVERVIEW, REVIEWING_ANALYSIS_KEY, go_to
from app_pages.doctor_notes_service import get_doctor_notes, save_doctor_note
from app_pages.patient_overview_page import load_viewed_patient
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.registration_page import get_analyses_collection, get_doctor_notes_collection
from assistant.ui_view import render_doctor_assistant_panel
from prediction.cluster_controller import ClusterController
from prediction.controller import DiseasePredictionController
from prediction.ui_view import load_cluster_assets, render_cluster_summary_tables


def _format_symptom(name: str) -> str:
    return str(name).replace("_", " ").strip().capitalize()


def _load_cluster_controller() -> ClusterController:
    model, symptoms, metadata = load_cluster_assets()
    return ClusterController(model=model, symptoms=symptoms, metadata=metadata)


def _render_symptoms(symptoms: list[str]) -> None:
    st.subheader("Patient Reported Symptoms")
    if not symptoms:
        st.info("No symptoms were recorded for this analysis.")
        return
    st.write(", ".join(_format_symptom(symptom) for symptom in symptoms))


def _render_disease_predictions(analysis: dict) -> None:
    result = analysis_to_prediction_result(analysis)
    st.subheader("Disease Predictions")
    with st.container(border=True):
        prediction_col, confidence_col = st.columns(2)
        prediction_col.metric("Model prediction", result.top_disease)
        confidence_col.metric("Confidence", f"{result.top_probability:.1%}")
        if result.is_low_confidence:
            st.warning(
                "Low confidence: no disease reached the "
                f"{DiseasePredictionController.CONFIDENCE_THRESHOLD:.0%} threshold."
            )

        st.markdown("**Other predictions**")
        others = result.ranked[1:]
        if others:
            st.dataframe(
                [{"Disease": item.disease, "Confidence": f"{item.probability:.1%}"} for item in others],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No other predictions were recorded.")


def _render_why_this_cluster(explanation: dict, assignment) -> None:
    shared = ", ".join(_format_symptom(name) for name in explanation["shared_symptoms"])
    missing = ", ".join(_format_symptom(name) for name in explanation["cluster_symptoms_not_reported"])
    atypical = ", ".join(_format_symptom(name) for name in explanation["reported_symptoms_not_typical"])

    st.markdown(
        f"K-Means places the patient in the cluster whose centre is nearest to their symptom profile. "
        f"The patient is closest to **Cluster {assignment.cluster_id}**."
    )
    st.write(f"**Reported symptoms that are common in this cluster:** {shared or 'None'}")
    st.write(f"**Common cluster symptoms the patient did not report:** {missing or 'None'}")
    st.write(f"**Reported symptoms that are not typical of this cluster:** {atypical or 'None'}")

    runner_up = explanation["runner_up"]
    if runner_up:
        gap = assignment.confidence - runner_up["similarity"]
        st.write(
            f"**Next closest:** Cluster {runner_up['cluster_id']} ({runner_up['similarity']:.1%} similarity), "
            f"{gap:.1%} behind the assigned cluster."
        )
        if gap < 0.05:
            st.caption("The two closest clusters are very close, so this subgroup match is uncertain.")


def _render_patient_subgroup(controller: ClusterController, symptoms: list[str], assignment, analysis_id: str) -> None:
    st.subheader("Patient Subgroup")
    if assignment is None:
        st.info("The cluster model does not recognise any of the reported symptoms.")
        return

    with st.container(border=True):
        cluster_col, similarity_col, size_col = st.columns(3)
        cluster_col.metric("Cluster", assignment.cluster_id)
        similarity_col.metric("Similarity", f"{assignment.confidence:.1%}")
        size_col.metric("Past patients in cluster", assignment.summary.patient_count)
        render_cluster_summary_tables(assignment.summary)

        toggle_key = f"why_cluster_{analysis_id}"
        if st.button("Why this Cluster", key=f"{toggle_key}_button"):
            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
        if st.session_state.get(toggle_key):
            _render_why_this_cluster(explain_cluster_match(controller, symptoms, assignment), assignment)


def _render_doctor_notes(patient: dict, analysis: dict) -> None:
    analysis_id = str(analysis["_id"])
    open_key = f"doctor_note_open_{analysis_id}"
    # Bumped after each save so the text box comes back empty.
    version_key = f"doctor_note_version_{analysis_id}"
    notes_collection = get_doctor_notes_collection()

    flash = st.session_state.pop("doctor_note_flash", None)
    if flash:
        st.success(flash)

    if not st.session_state.get(open_key):
        if st.button("Add Doctor's note", key=f"add_doctor_note_{analysis_id}", type="primary"):
            st.session_state[open_key] = True
            st.rerun()
    else:
        st.subheader("Doctor Notes")
        with st.form(key=f"doctor_note_form_{analysis_id}"):
            text = st.text_area(
                "Doctor notes",
                key=f"doctor_note_text_{analysis_id}_{st.session_state.get(version_key, 0)}",
                height=150,
                label_visibility="collapsed",
                placeholder="Write your note about this analysis",
            )
            submitted = st.form_submit_button("Save Note", type="primary")
        if submitted:
            user = st.session_state.get("authenticated_user") or {}
            _, error = save_doctor_note(notes_collection, patient, user.get("email"), text, analysis["_id"])
            if error:
                st.error(error)
            else:
                st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
                st.session_state["doctor_note_flash"] = "Note saved."
                st.rerun()

    notes = get_doctor_notes(notes_collection, patient.get("id"), analysis["_id"])
    if notes:
        st.markdown("**Saved notes**")
        for note in notes:
            with st.container(border=True):
                st.caption(format_analysis_date(note.created_at))
                st.write(note.text)


def render_page() -> None:
    """Review Analysis page: the full ML output for the analysis picked on the Patient Overview."""
    if st.button("← Back to patient overview", key="analysis_review_back"):
        st.session_state.pop(REVIEWING_ANALYSIS_KEY, None)
        go_to(PATIENT_OVERVIEW)

    patient = load_viewed_patient()
    if patient is None:
        return

    analyses = get_patient_analyses(get_analyses_collection(), patient["email"])
    reviewing_id = st.session_state.get(REVIEWING_ANALYSIS_KEY)
    analysis = next((item for item in analyses if str(item["_id"]) == reviewing_id), None)
    if analysis is None:
        st.info("No analysis is selected. Go back to the patient overview and click **Review Analysis**.")
        return

    _render(patient, analysis, analyses)


def _render(patient: dict, analysis: dict, all_analyses: list[dict]) -> None:
    analysis_id = str(analysis["_id"])
    symptoms = list(analysis.get("symptoms") or [])

    st.title("Review Analysis")
    st.caption(f"{patient['name']} · {format_analysis_date(analysis.get('created_at'))}")

    _render_symptoms(symptoms)
    _render_disease_predictions(analysis)

    controller = None
    assignment = None
    try:
        controller = _load_cluster_controller()
        assignment = assign_cluster(controller, symptoms)
    except Exception as error:
        st.subheader("Patient Subgroup")
        st.error(f"The patient subgroup could not be computed: {error}")
    if controller is not None:
        _render_patient_subgroup(controller, symptoms, assignment, analysis_id)

    st.divider()
    render_doctor_assistant_panel(
        build_doctor_context(analysis, all_analyses, assignment, patient.get("known_conditions")),
        conversation_key=f"doctor_ai_{analysis_id}",
    )

    st.divider()
    _render_doctor_notes(patient, analysis)
