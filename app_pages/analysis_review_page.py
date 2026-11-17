"""Doctor page showing the full ML output for one of a patient's saved analyses."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from app_pages.analysis_review_service import (
    analysis_to_prediction_result,
    assign_cluster,
    build_doctor_context,
    explain_cluster_match,
    format_analysis_date,
)
from app_pages.doctor_navigation import MY_PATIENTS, PATIENT_OVERVIEW, REVIEWING_ANALYSIS_KEY, page
from app_pages.doctor_notes_service import get_doctor_notes, save_doctor_note
from app_pages.patient_overview_page import load_viewed_patient
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.registration_page import get_analyses_collection, get_doctor_notes_collection
from assistant.ui_view import render_doctor_assistant_panel
from prediction.cluster_controller import ClusterController
from prediction.controller import DiseasePredictionController
from prediction.ui_view import load_cluster_assets, render_cluster_summary_tables
from ui.components import (
    card,
    empty_state,
    error_message,
    field_grid,
    flash,
    page_header,
    section_header,
    show_errors,
    show_flash,
)

# Colours match ui/theme.py tokens (model output is blue).
_MODEL_BLUE = "#2563EB"
_MODEL_BLUE_LIGHT = "#93C5FD"
_TEXT = "#0F172A"
_TEXT_MUTED = "#64748B"
_BORDER = "#E2E8F0"

_NOTE_FLASH_KEY = "doctor_note"


def _format_symptom(name: str) -> str:
    return str(name).replace("_", " ").strip().capitalize()


def _format_date(value) -> str:
    return value.strftime("%b %d, %Y") if hasattr(value, "strftime") else "Unknown date"


def _format_time(value) -> str:
    # Analyses and notes are stored in naive UTC.
    return f"{format_analysis_date(value)} UTC" if hasattr(value, "strftime") else "Unknown date"


def _load_cluster_controller() -> ClusterController:
    model, symptoms, metadata = load_cluster_assets()
    return ClusterController(model=model, symptoms=symptoms, metadata=metadata)


# ---------------------------------------------------------------- reported symptoms


def _render_symptoms(symptoms: list[str]) -> None:
    section_header("Reported symptoms", "What the patient selected when they ran this prediction")
    with card("review-symptoms"):
        if not symptoms:
            st.markdown(":gray[No symptoms were recorded for this analysis.]")
            return
        st.markdown(" ".join(f":gray-badge[{_format_symptom(symptom)}]" for symptom in symptoms))


# ---------------------------------------------------------------- disease prediction


def _predictions_chart(result) -> alt.Chart:
    data = pd.DataFrame(
        {
            "Condition": [item.disease for item in result.ranked],
            "Model confidence": [item.probability for item in result.ranked],
            "Rank": ["Top prediction" if index == 0 else "Alternative" for index in range(len(result.ranked))],
        }
    )
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=4, height=18).encode(
        x=alt.X(
            "Model confidence:Q",
            axis=alt.Axis(format="%", grid=True, gridColor=_BORDER, tickCount=5, labelColor=_TEXT_MUTED, title=None),
            scale=alt.Scale(domain=[0, 1]),
        ),
        y=alt.Y("Condition:N", sort=None,
                axis=alt.Axis(title=None, labelColor=_TEXT, labelLimit=220, ticks=False, domain=False)),
        color=alt.Color("Rank:N", legend=None,
                        scale=alt.Scale(domain=["Top prediction", "Alternative"],
                                        range=[_MODEL_BLUE, _MODEL_BLUE_LIGHT])),
        tooltip=[alt.Tooltip("Condition:N"), alt.Tooltip("Model confidence:Q", format=".1%")],
    )
    labels = bars.mark_text(align="left", dx=6).encode(
        text=alt.Text("Model confidence:Q", format=".1%"), color=alt.value(_TEXT_MUTED)
    )
    return (bars + labels).properties(height=46 * len(data) + 10).configure_view(stroke=None).configure(background="transparent")


def _render_disease_prediction(analysis: dict) -> None:
    result = analysis_to_prediction_result(analysis)
    with card("review-prediction", lane="model"):
        section_header(
            "Disease prediction",
            "What the logistic-regression classifier predicted from the reported symptoms",
            badge="model",
        )
        prediction_col, confidence_col = st.columns([3, 2])
        with prediction_col:
            st.markdown(":gray[Predicted condition]")
            st.markdown(f"## {result.top_disease}")
        with confidence_col:
            st.metric(
                "Model confidence",
                f"{result.top_probability:.1%}",
                help="The classifier's relative score for this condition among those it knows, not a certainty.",
            )
            st.progress(min(max(result.top_probability, 0.0), 1.0))
        if result.is_low_confidence:
            st.warning(
                "Low model confidence: no condition reached the "
                f"{DiseasePredictionController.CONFIDENCE_THRESHOLD:.0%} threshold. The reported symptoms fit "
                "several conditions similarly.",
                icon=":material/warning:",
            )

        if result.ranked:
            st.markdown(f"**Top {len(result.ranked)} model predictions**")
            st.altair_chart(_predictions_chart(result), width="stretch")
            if len(result.ranked) == 1:
                st.caption("No alternative predictions were recorded.")
        else:
            st.caption("No other predictions were recorded.")
        st.caption(
            "Model output from symptom patterns in training data. It is not a diagnosis and does not account for "
            "examination, history or tests."
        )


# ---------------------------------------------------------------- patient subgroup


def _render_why_this_cluster(explanation: dict, assignment) -> None:
    def listed(names: list[str]) -> str:
        return ", ".join(_format_symptom(name) for name in names) or "None"

    with card("review-why-cluster"):
        st.markdown("**Why this cluster**")
        st.markdown(
            "K-Means places the patient in the cluster whose centre is nearest to their symptom profile. "
            f"The patient is closest to **Cluster {assignment.cluster_id}**."
        )
        field_grid(
            [
                ("Reported symptoms common in this cluster", listed(explanation["shared_symptoms"])),
                ("Common cluster symptoms the patient did not report",
                 listed(explanation["cluster_symptoms_not_reported"])),
                ("Reported symptoms not typical of this cluster", listed(explanation["reported_symptoms_not_typical"])),
            ]
        )
        runner_up = explanation["runner_up"]
        if runner_up:
            gap = assignment.confidence - runner_up["similarity"]
            st.markdown(
                f":gray[Next closest]  \nCluster {runner_up['cluster_id']} with {runner_up['similarity']:.1%} "
                f"similarity, {gap:.1%} behind the assigned cluster."
            )
            if gap < 0.05:
                st.caption(
                    ":material/info: The two closest clusters are very close, so this subgroup match is uncertain."
                )


def _toggle(key: str) -> None:
    st.session_state[key] = not st.session_state.get(key, False)


def _render_patient_subgroup(controller, symptoms: list[str], assignment, analysis_id: str, error=None) -> None:
    with card("review-subgroup", lane="subgroup"):
        section_header(
            "Patient subgroup",
            "Past patients whose symptom patterns are most like this patient's",
            badge="subgroup",
        )
        if error is not None:
            error_message(
                f"The patient subgroup could not be computed: {error}",
                "Check that the cluster model files are available. The rest of this analysis is unaffected.",
            )
            return
        if assignment is None:
            st.info("The cluster model does not recognise any of the reported symptoms.", icon=":material/info:")
            return

        field_grid(
            [
                ("Subgroup", f"Cluster {assignment.cluster_id}"),
                ("Similarity", f"{assignment.confidence:.1%}"),
                ("Past patients in this subgroup", f"{assignment.summary.patient_count:,}"),
            ]
        )
        render_cluster_summary_tables(assignment.summary)
        st.caption(
            "Subgroups group past patients by symptom similarity (K-Means). This is not a diagnosis."
        )

        toggle_key = f"why_cluster_{analysis_id}"
        showing = st.session_state.get(toggle_key, False)
        st.button(
            "Hide explanation" if showing else "Explain why this cluster",
            key=f"{toggle_key}_button",
            icon=":material/expand_less:" if showing else ":material/help:",
            on_click=_toggle,
            args=(toggle_key,),
        )
        if showing:
            _render_why_this_cluster(explain_cluster_match(controller, symptoms, assignment), assignment)


# ---------------------------------------------------------------- AI assistant


def _render_assistant(patient: dict, analysis: dict, all_analyses: list[dict], assignment) -> None:
    analysis_id = str(analysis["_id"])
    with card("review-assistant", lane="ai"):
        section_header(
            "AI assistant",
            "Ask about this analysis. Answers explain the model and subgroup results above and are not a diagnosis.",
            badge="ai",
        )
        render_doctor_assistant_panel(
            build_doctor_context(analysis, all_analyses, assignment, patient.get("known_conditions")),
            conversation_key=f"doctor_ai_{analysis_id}",
        )


# ---------------------------------------------------------------- doctor's notes


def _open_note_form(open_key: str) -> None:
    st.session_state[open_key] = True


def _close_note_form(open_key: str) -> None:
    st.session_state[open_key] = False


def _render_doctor_notes(patient: dict, analysis: dict) -> None:
    analysis_id = str(analysis["_id"])
    open_key = f"doctor_note_open_{analysis_id}"
    # Bumped after each save so the text box comes back empty.
    version_key = f"doctor_note_version_{analysis_id}"
    notes_collection = get_doctor_notes_collection()
    notes = get_doctor_notes(notes_collection, patient.get("id"), analysis["_id"])
    form_open = bool(st.session_state.get(open_key))

    actions = section_header("Doctor's notes", "Your notes on this analysis, newest first")
    if not form_open and notes:
        actions.button(
            "Add note",
            key=f"add_doctor_note_{analysis_id}",
            type="primary",
            icon=":material/add:",
            on_click=_open_note_form,
            args=(open_key,),
        )
    show_flash(_NOTE_FLASH_KEY)

    if form_open:
        with card("review-note-form"):
            with st.form(key=f"doctor_note_form_{analysis_id}", border=False):
                text = st.text_area(
                    "New note",
                    key=f"doctor_note_text_{analysis_id}_{st.session_state.get(version_key, 0)}",
                    height=150,
                    placeholder="For example: follow up in two weeks if the fever persists",
                )
                with st.container(horizontal=True, gap="small"):
                    submitted = st.form_submit_button("Save note", type="primary", icon=":material/save:")
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                _close_note_form(open_key)
                st.rerun()
            if submitted:
                user = st.session_state.get("authenticated_user") or {}
                _, error = save_doctor_note(notes_collection, patient, user.get("email"), text, analysis["_id"])
                if error:
                    show_errors([error])
                else:
                    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
                    flash("Note saved.", key=_NOTE_FLASH_KEY)
                    st.rerun()

    if not notes:
        if not form_open:
            empty_state(
                "No notes on this analysis yet",
                "Add a note to record your assessment or follow-up plan.",
                icon=":material/sticky_note_2:",
                key=f"notes-{analysis_id}",
                action_label="Add note",
                on_action=lambda: _open_note_form(open_key),
            )
        return

    for note in notes:
        with card(f"review-note-{note.id}"):
            st.caption(_format_time(note.created_at))
            st.write(note.text)


# ---------------------------------------------------------------- page


def render_page() -> None:
    """Review analysis page: the full ML output for the analysis picked on the patient overview."""
    patient = load_viewed_patient()
    if patient is None:
        return

    analyses = get_patient_analyses(get_analyses_collection(), patient["email"])
    reviewing_id = st.session_state.get(REVIEWING_ANALYSIS_KEY)
    analysis = next((item for item in analyses if str(item["_id"]) == reviewing_id), None)
    if analysis is None:
        page_header(
            "Review analysis",
            breadcrumb=[("My patients", page(MY_PATIENTS)), (patient["name"], page(PATIENT_OVERVIEW)),
                        ("Analysis", None)],
        )
        empty_state(
            "No analysis selected",
            f"Choose an analysis from {patient['name']}'s analysis history to review it.",
            icon=":material/clinical_notes:",
            key="no-analysis",
            action_label="Open patient overview",
            page=page(PATIENT_OVERVIEW),
        )
        return

    _render(patient, analysis, analyses)


def _render(patient: dict, analysis: dict, all_analyses: list[dict]) -> None:
    analysis_id = str(analysis["_id"])
    symptoms = list(analysis.get("symptoms") or [])

    page_header(
        "Review analysis",
        f"{patient['name']}'s disease prediction from {_format_time(analysis.get('created_at'))}",
        breadcrumb=[
            ("My patients", page(MY_PATIENTS)),
            (patient["name"], page(PATIENT_OVERVIEW)),
            (f"Analysis {_format_date(analysis.get('created_at'))}", None),
        ],
    )

    _render_symptoms(symptoms)
    _render_disease_prediction(analysis)

    controller = None
    assignment = None
    cluster_error = None
    try:
        controller = _load_cluster_controller()
        assignment = assign_cluster(controller, symptoms)
    except Exception as error:  # Model files missing or unreadable; show it in the subgroup section.
        cluster_error = error
    _render_patient_subgroup(controller, symptoms, assignment, analysis_id, cluster_error)

    _render_assistant(patient, analysis, all_analyses, assignment)
    _render_doctor_notes(patient, analysis)
