"""Patient analysis history: every saved prediction, with a way to ask the AI assistant about any of them."""

from __future__ import annotations

import streamlit as st

from app_pages.patient_navigation import AI_ASSISTANT, NEW_ANALYSIS, go_to, page
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.registration_page import get_analyses_collection
from prediction.ui_view import MODEL_DISCLAIMER, format_symptom
from ui.components import data_table, empty_state, entity_card, page_header, search_and_filter

# Read by the AI assistant page to preselect an analysis.
ASSISTANT_ANALYSIS_KEY = "assistant_analysis_id"


def _ask_assistant(analysis_id) -> None:
    st.session_state[ASSISTANT_ANALYSIS_KEY] = str(analysis_id)
    go_to(AI_ASSISTANT)


def _matches(analysis: dict, query: str) -> bool:
    haystack = " ".join([str(analysis.get("top_disease") or "")]
                        + [format_symptom(name) for name in analysis.get("symptoms") or []]).lower()
    return query in haystack


def render() -> None:
    user = st.session_state.get("authenticated_user") or {}
    actions = page_header("Analysis history", "Every symptom analysis you've run, newest first")
    actions.page_link(page(NEW_ANALYSIS), label="New health analysis", icon=":material/add:")

    analyses = get_patient_analyses(get_analyses_collection(), user.get("email"))
    if not analyses:
        empty_state("No analyses yet", "Your results are saved here each time you analyze your symptoms.",
                    icon=":material/history:", key="history", action_label="Start a new analysis",
                    page=page(NEW_ANALYSIS))
        return

    query, reviewed_filter = search_and_filter(
        "history",
        placeholder="Search by condition or symptom",
        filters=["reviewed", "unreviewed"],
        format_filter=lambda value: {"reviewed": "Reviewed by doctor", "unreviewed": "Not reviewed"}[value],
    )
    shown = [
        analysis for analysis in analyses
        if (not query or _matches(analysis, query))
        and ("reviewed" if analysis.get("reviewed") else "unreviewed") in reviewed_filter
    ]
    if not shown:
        empty_state("No analyses match", "Try a different search or filter.", icon=":material/search_off:",
                    key="history-filtered")
        return

    st.caption(MODEL_DISCLAIMER)
    for analysis in shown:
        created = analysis.get("created_at")
        with entity_card(
            f"analysis-{analysis['_id']}",
            analysis.get("top_disease") or "Unknown",
            subtitle=f"{created:%A, %b %d, %Y at %I:%M %p} UTC" if hasattr(created, "strftime") else None,
            status=("review", "reviewed" if analysis.get("reviewed") else "unreviewed"),
            fields=[
                ("Model confidence", f"{float(analysis.get('top_probability') or 0):.0%}"
                 + (" (low)" if analysis.get("is_low_confidence") else "")),
                ("Symptoms", ", ".join(format_symptom(name) for name in analysis.get("symptoms") or []) or None),
            ],
            columns=2,
        ):
            with st.expander("Top model predictions"):
                data_table(
                    [{"Condition": item.get("disease"), "Model confidence": float(item.get("probability") or 0)}
                     for item in analysis.get("ranked") or []],
                    column_config={"Model confidence": st.column_config.ProgressColumn(
                        format="percent", min_value=0, max_value=1)},
                )
            if st.button("Ask the AI assistant", key=f"ask-{analysis['_id']}", icon=":material/auto_awesome:"):
                _ask_assistant(analysis["_id"])
