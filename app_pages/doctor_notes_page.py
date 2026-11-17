"""Doctor's notes: every note the signed-in doctor has written, across all their patients."""

from __future__ import annotations

import streamlit as st

from app_pages.doctor_navigation import (
    MY_PATIENTS,
    REVIEW_ANALYSIS,
    REVIEWING_ANALYSIS_KEY,
    VIEWING_PATIENT_KEY,
    go_to,
    page,
)
from app_pages.doctor_notes_service import DoctorNote, list_notes_by_doctor
from app_pages.patient_overview_page import open_patient_overview
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.practitioner_service import format_person_name
from app_pages.registration_page import (
    get_analyses_collection,
    get_doctor_notes_collection,
    get_users_collection,
)
from ui.components import card, empty_state, error_message, page_header

_ALL_PATIENTS = "__all__"
_SEARCH_KEY = "doctor_notes_search"
_PATIENT_KEY = "doctor_notes_patient"


def _format_time(value) -> str:
    # Notes and analyses are stored in naive UTC.
    return f"{value.strftime('%b %d, %Y %I:%M %p')} UTC" if hasattr(value, "strftime") else "Unknown date"


def _patient_names(users_collection, emails: set[str]) -> dict[str, str]:
    """Display name for each patient email; falls back to the email when the user can't be found."""
    names = {}
    for email in emails:
        record = users_collection.find_one({"email": email}) if users_collection is not None else None
        names[email] = format_person_name(record) if record else email
    return names


def _analysis_dates(analyses_collection, notes: list[DoctorNote]) -> dict[str, object]:
    """created_at of every analysis a note is linked to, keyed by str(analysis _id)."""
    dates = {}
    for email in {note.patient_email for note in notes if note.analysis_id is not None}:
        for analysis in get_patient_analyses(analyses_collection, email, limit=10_000):
            dates[str(analysis["_id"])] = analysis.get("created_at")
    return dates


def _open_analysis(note: DoctorNote) -> None:
    st.session_state[VIEWING_PATIENT_KEY] = note.patient_email
    st.session_state[REVIEWING_ANALYSIS_KEY] = str(note.analysis_id)
    go_to(REVIEW_ANALYSIS)


def _clear_filters() -> None:
    st.session_state[_SEARCH_KEY] = ""
    st.session_state[_PATIENT_KEY] = _ALL_PATIENTS


def _render_note(note: DoctorNote, patient_name: str, analysis_dates: dict[str, object]) -> None:
    with card(f"doctor-note-{note.id}"):
        title_col, action_col = st.columns([3, 1], vertical_alignment="center")
        with title_col:
            st.markdown(f"**{patient_name}**")
            st.caption(f"Written {_format_time(note.created_at)}")
        with action_col.container(horizontal=True, horizontal_alignment="right"):
            if note.analysis_id is not None:
                clicked = st.button("Open analysis", key=f"note_open_analysis_{note.id}",
                                    icon=":material/clinical_notes:")
            else:
                clicked = st.button("Open patient", key=f"note_open_patient_{note.id}", icon=":material/person:")
        st.write(note.text)
        if note.analysis_id is not None:
            analysis_date = analysis_dates.get(str(note.analysis_id))
            linked = f"Analysis {_format_time(analysis_date)}" if analysis_date else "Analysis no longer available"
            st.markdown(f":gray[Linked analysis]  \n{linked}")

    if clicked:
        if note.analysis_id is not None:
            _open_analysis(note)
        else:
            open_patient_overview(note.patient_email)


def render() -> None:
    """Doctor's notes page (sidebar: Clinical workspace)."""
    page_header("Doctor's notes", "Every note you have written about your patients, newest first")

    notes_collection = get_doctor_notes_collection()
    if notes_collection is None:
        error_message("Your notes can't be loaded because the database is not available right now.",
                      "Try again in a few minutes.")
        return

    user = st.session_state.get("authenticated_user") or {}
    notes = list_notes_by_doctor(notes_collection, user.get("email"))
    if not notes:
        empty_state(
            "No notes yet",
            "Notes you write while reviewing a patient's analysis appear here.",
            icon=":material/sticky_note_2:",
            key="doctor-notes",
            action_label="Go to my patients",
            page=page(MY_PATIENTS),
        )
        return

    names = _patient_names(get_users_collection(), {note.patient_email for note in notes})
    analysis_dates = _analysis_dates(get_analyses_collection(), notes)

    patient_options = [_ALL_PATIENTS] + sorted(names, key=lambda email: names[email].lower())
    if st.session_state.get(_PATIENT_KEY) not in patient_options:
        st.session_state[_PATIENT_KEY] = _ALL_PATIENTS
    search_col, patient_col = st.columns([2, 1], vertical_alignment="bottom")
    query = search_col.text_input(
        "Search notes",
        placeholder="Patient name or words in the note",
        key=_SEARCH_KEY,
        icon=":material/search:",
    ).strip().lower()
    patient_filter = patient_col.selectbox(
        "Patient",
        patient_options,
        key=_PATIENT_KEY,
        format_func=lambda email: "All patients" if email == _ALL_PATIENTS else names[email],
    )

    shown = [
        note
        for note in notes
        if (patient_filter == _ALL_PATIENTS or note.patient_email == patient_filter)
        and (not query or query in note.text.lower() or query in names[note.patient_email].lower()
             or query in note.patient_email)
    ]
    st.caption(f"Showing {len(shown)} of {len(notes)} notes")

    if not shown:
        empty_state(
            "No notes match your filters",
            "Try another name or word, or clear the filters to see every note.",
            icon=":material/search_off:",
            key="doctor-notes-filtered",
            action_label="Clear filters",
            on_action=_clear_filters,
        )
        return

    for note in shown:
        _render_note(note, names[note.patient_email], analysis_dates)
