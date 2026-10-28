"""Doctor pages for simulated prescriptions: a patient's prescription list, the editor, and the detail view.

All medication details are typed in by the doctor. Nothing is pre-filled or
suggested, including from the patient's ML analyses (an analysis can only be
linked for reference).
"""

from __future__ import annotations

import secrets
from datetime import datetime

import streamlit as st

from app_pages.doctor_navigation import (
    EDITING_PRESCRIPTION_KEY,
    NEW_PRESCRIPTION,
    PATIENT_OVERVIEW,
    PRESCRIPTION_DETAIL,
    PRESCRIPTION_EDITOR,
    PRESCRIPTIONS,
    VIEWING_PRESCRIPTION_KEY,
    go_to,
)
from app_pages.patient_overview_page import load_viewed_patient
from app_pages.patient_overview_service import get_patient_analyses
from app_pages.practitioner_service import format_person_name
from app_pages.prescription_service import (
    MEDICATION_FIELDS,
    STATUS_DRAFT,
    STATUS_FINALIZED,
    STATUS_VOIDED,
    clean_medications,
    create_draft,
    finalize_prescription,
    generate_prescription_id,
    list_prescriptions_for_doctor,
    update_draft,
    void_prescription,
)
from app_pages.prescription_ui import (
    STATUS_LABELS,
    format_date,
    render_pdf_download,
    render_prescription_summary,
    render_simulation_notice,
    status_label,
)
from app_pages.registration_page import (
    get_analyses_collection,
    get_prescriptions_collection,
    get_requests_collection,
    get_users_collection,
)

EDITOR_STATE_KEY = "rx_editor"
FLASH_KEY = "rx_flash"
# Which confirmation dialog is open. Kept in session state so the dialog stays open across reruns.
FINALIZE_DIALOG_KEY = "rx_finalize_dialog"
VOID_DIALOG_KEY = "rx_void_dialog"
FIELD_LABELS = {
    "name": "Medication name",
    "dosage": "Dosage",
    "frequency": "Frequency",
    "duration": "Duration",
    "instructions": "Additional instructions (optional)",
}


def _doctor() -> dict:
    return st.session_state.get("authenticated_user") or {}


def _doctor_email() -> str:
    return str(_doctor().get("email") or "").strip().lower()


def _show_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)


def _is_own_draft(prescription: dict) -> bool:
    return prescription.get("status") == STATUS_DRAFT and prescription.get("doctor_email") == _doctor_email()


def _find_prescription(patient: dict, key: str | None) -> dict | None:
    """Look the prescription up among this patient's records the doctor may see."""
    if not key:
        return None
    for prescription in list_prescriptions_for_doctor(get_prescriptions_collection(), _doctor_email(), patient["email"]):
        if str(prescription["_id"]) == key:
            return prescription
    return None


def _analysis_labels(patient: dict) -> dict[str, tuple[object, str]]:
    """str(analysis _id) -> (analysis _id, label) for the patient's saved analyses."""
    return {
        str(analysis["_id"]): (
            analysis["_id"],
            f"{format_date(analysis.get('created_at'))} · {analysis.get('top_disease') or 'Unknown'}",
        )
        for analysis in get_patient_analyses(get_analyses_collection(), patient["email"])
    }


def open_prescription_list() -> None:
    go_to(PRESCRIPTIONS)


def _open_detail(prescription: dict) -> None:
    st.session_state[VIEWING_PRESCRIPTION_KEY] = str(prescription["_id"])
    go_to(PRESCRIPTION_DETAIL)


def _open_editor(prescription: dict | None = None) -> None:
    st.session_state[EDITING_PRESCRIPTION_KEY] = str(prescription["_id"]) if prescription else NEW_PRESCRIPTION
    st.session_state.pop(EDITOR_STATE_KEY, None)
    go_to(PRESCRIPTION_EDITOR)


# ---------------------------------------------------------------- list page


def render_prescriptions_page() -> None:
    """All of a patient's prescriptions visible to this doctor, with status filters."""
    if st.button("← Back to patient overview", key="rx_list_back"):
        go_to(PATIENT_OVERVIEW)

    patient = load_viewed_patient()
    if patient is None:
        return

    st.title(f"Prescriptions · {patient['name']}")
    render_simulation_notice()
    _show_flash()

    if st.button("Create Prescription", type="primary", key="rx_create"):
        _open_editor()

    statuses = st.segmented_control(
        "Filter by status",
        options=[STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED],
        selection_mode="multi",
        default=[STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED],
        format_func=lambda status: STATUS_LABELS[status],
        key="rx_status_filter",
    )
    prescriptions = list_prescriptions_for_doctor(
        get_prescriptions_collection(), _doctor_email(), patient["email"], statuses=list(statuses or [])
    )
    if not prescriptions:
        st.info("No prescriptions match the selected filters.")
        return

    analyses = _analysis_labels(patient)
    widths = [3, 2, 1.3, 1.5, 3, 1.6]
    for column, title in zip(
        st.columns(widths), ["Prescription ID", "Created", "Medications", "Status", "Associated analysis", "Action"]
    ):
        column.markdown(f"**{title}**")

    for prescription in prescriptions:
        key = str(prescription["_id"])
        analysis = analyses.get(str(prescription.get("analysis_id")))
        cols = st.columns(widths, vertical_alignment="center")
        cols[0].write(prescription.get("prescription_id"))
        cols[1].write(format_date(prescription.get("created_at")))
        cols[2].write(str(len(prescription.get("medications") or [])))
        cols[3].write(status_label(prescription))
        cols[4].write(analysis[1] if analysis else "—")
        with cols[5]:
            if _is_own_draft(prescription):
                view_col, edit_col = st.columns(2)
                if view_col.button("View", key=f"rx_view_{key}"):
                    _open_detail(prescription)
                if edit_col.button("Edit", key=f"rx_edit_{key}"):
                    _open_editor(prescription)
            elif st.button("View", key=f"rx_view_{key}"):
                _open_detail(prescription)


# ---------------------------------------------------------------- editor page


def _widget_key(editor: dict, name: str) -> str:
    # The nonce gives every editor session fresh widgets, so old values never leak in.
    return f"rx_{editor['nonce']}_{name}"


def _init_editor(key: str, existing: dict | None) -> dict:
    editor = {
        "for": key,
        "nonce": secrets.token_hex(4),
        "prescription_id": existing["prescription_id"] if existing else generate_prescription_id(),
        "rows": [],
        "next_row": 0,
    }
    for medication in (existing or {}).get("medications") or [{}]:
        _add_row(editor, medication)
    st.session_state[_widget_key(editor, "note")] = (existing or {}).get("doctor_note") or ""
    analysis_id = (existing or {}).get("analysis_id")
    st.session_state[_widget_key(editor, "analysis")] = str(analysis_id) if analysis_id is not None else None
    st.session_state[EDITOR_STATE_KEY] = editor
    return editor


def _add_row(editor: dict, values: dict | None = None) -> None:
    row = editor["next_row"]
    editor["next_row"] += 1
    editor["rows"].append(row)
    for field in MEDICATION_FIELDS:
        st.session_state[_widget_key(editor, f"{row}_{field}")] = str((values or {}).get(field) or "")


def _render_medication_rows(editor: dict) -> list[dict]:
    st.subheader("Medications")
    st.caption("Enter every detail manually. Nothing is pre-filled or suggested.")
    medications = []
    for index, row in enumerate(list(editor["rows"]), start=1):
        with st.container(border=True):
            header, remove = st.columns([5, 1], vertical_alignment="center")
            header.markdown(f"**Medication {index}**")
            if remove.button("Remove", key=_widget_key(editor, f"{row}_remove"), disabled=len(editor["rows"]) == 1):
                editor["rows"].remove(row)
                st.rerun()
            columns = st.columns(4)
            for column, field in zip(columns, ("name", "dosage", "frequency", "duration")):
                column.text_input(FIELD_LABELS[field], key=_widget_key(editor, f"{row}_{field}"))
            st.text_input(FIELD_LABELS["instructions"], key=_widget_key(editor, f"{row}_instructions"))
        medications.append({field: st.session_state.get(_widget_key(editor, f"{row}_{field}"), "") for field in MEDICATION_FIELDS})

    if st.button("+ Add medication", key=_widget_key(editor, "add_row")):
        _add_row(editor)
        st.rerun()
    return medications


def _save(existing: dict | None, patient: dict, editor: dict, medications: list[dict], note: str, analysis_id):
    """Create or update the draft. Returns (str(_id) or None, errors)."""
    if existing is None:
        created, errors = create_draft(
            get_prescriptions_collection(),
            get_users_collection(),
            get_requests_collection(),
            patient=patient,
            doctor=_doctor(),
            medications=medications,
            doctor_note=note,
            analysis_id=analysis_id,
            prescription_id=editor["prescription_id"],
        )
        if created is None:
            return None, errors
        # From now on this editor updates the saved draft instead of creating another one.
        key = str(created["_id"])
        st.session_state[EDITING_PRESCRIPTION_KEY] = key
        editor["for"] = key
        return key, []
    errors = update_draft(
        get_prescriptions_collection(),
        existing["_id"],
        _doctor_email(),
        medications=medications,
        doctor_note=note,
        analysis_id=analysis_id,
    )
    return (None if errors else str(existing["_id"])), errors


def _finalize(key: str) -> list[str]:
    patient = load_viewed_patient()
    prescription = _find_prescription(patient, key) if patient else None
    if prescription is None:
        return ["Prescription not found."]
    return finalize_prescription(
        get_prescriptions_collection(),
        get_users_collection(),
        get_requests_collection(),
        prescription["_id"],
        _doctor_email(),
    )


def _close_dialogs() -> None:
    st.session_state.pop(FINALIZE_DIALOG_KEY, None)
    st.session_state.pop(VOID_DIALOG_KEY, None)
    st.session_state.pop("rx_void_reason", None)


@st.dialog("Finalize prescription", on_dismiss=_close_dialogs)
def _confirm_finalize(save_first=None, key: str | None = None) -> None:
    st.write(
        "Once finalized, this simulated prescription **can't be edited** and becomes visible to the patient. "
        "You can still void it later with a reason."
    )
    confirm, cancel = st.columns(2)
    if confirm.button("Finalize", type="primary", key="rx_finalize_confirm"):
        errors = []
        if save_first is not None:
            key, errors = save_first()
        if not errors:
            errors = _finalize(key)
        if errors:
            for error in errors:
                st.error(error)
            return
        _close_dialogs()
        st.session_state.pop(EDITOR_STATE_KEY, None)
        st.session_state[VIEWING_PRESCRIPTION_KEY] = key
        st.session_state[FLASH_KEY] = "Prescription finalized."
        go_to(PRESCRIPTION_DETAIL)
    if cancel.button("Cancel", key="rx_finalize_cancel"):
        _close_dialogs()
        st.rerun()


def render_prescription_editor_page() -> None:
    """Create a new draft or edit one of the doctor's own drafts."""
    if st.button("← Back to prescriptions", key="rx_editor_back"):
        st.session_state.pop(EDITOR_STATE_KEY, None)
        go_to(PRESCRIPTIONS)

    patient = load_viewed_patient()
    if patient is None:
        return

    key = st.session_state.get(EDITING_PRESCRIPTION_KEY)
    existing = None
    if not key:
        st.info("No prescription is selected. Go back and click **Create Prescription** or **Edit**.")
        return
    if key != NEW_PRESCRIPTION:
        existing = _find_prescription(patient, key)
        if existing is None or not _is_own_draft(existing):
            st.error("Only your own draft prescriptions can be edited. Finalized prescriptions are read-only.")
            return

    editor = st.session_state.get(EDITOR_STATE_KEY)
    if editor is None or editor.get("for") != key:
        editor = _init_editor(key, existing)

    st.title("Edit Draft Prescription" if existing else "Create Prescription")
    render_simulation_notice()

    with st.container(border=True):
        doctor = _doctor()
        left, right = st.columns(2)
        left.write(f"**Prescription ID:** {editor['prescription_id']}")
        left.write(f"**Date:** {format_date(existing['created_at'] if existing else datetime.utcnow())}")
        left.write(f"**Status:** {STATUS_LABELS[STATUS_DRAFT]}")
        right.write(f"**Patient:** {patient['name']} (ID: {patient.get('id')})")
        right.write(f"**Doctor:** {format_person_name(doctor, doctor=True)} (ID: {doctor.get('_id')})")

    analyses = _analysis_labels(patient)
    analysis_key = st.selectbox(
        "Associated analysis (optional, for reference only)",
        options=[None, *analyses.keys()],
        format_func=lambda option: "None" if option is None else analyses[option][1],
        key=_widget_key(editor, "analysis"),
    )
    analysis_id = analyses[analysis_key][0] if analysis_key in analyses else None
    note = st.text_area("Doctor's note (optional)", key=_widget_key(editor, "note"))

    medications = _render_medication_rows(editor)

    st.divider()
    save_col, finalize_col, cancel_col = st.columns(3)
    if save_col.button("Save as draft", type="primary", key=_widget_key(editor, "save")):
        saved_key, errors = _save(existing, patient, editor, medications, note, analysis_id)
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state.pop(EDITOR_STATE_KEY, None)
            st.session_state[FLASH_KEY] = f"Draft {editor['prescription_id']} saved."
            go_to(PRESCRIPTIONS)
    if finalize_col.button("Finalize", key=_widget_key(editor, "finalize")):
        _, errors = clean_medications(medications)
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state[FINALIZE_DIALOG_KEY] = editor["nonce"]
    if cancel_col.button("Cancel", key=_widget_key(editor, "cancel")):
        st.session_state.pop(EDITOR_STATE_KEY, None)
        go_to(PRESCRIPTIONS)

    if st.session_state.get(FINALIZE_DIALOG_KEY) == editor["nonce"]:
        _confirm_finalize(save_first=lambda: _save(existing, patient, editor, medications, note, analysis_id))


# ---------------------------------------------------------------- detail page


@st.dialog("Void prescription", on_dismiss=_close_dialogs)
def _confirm_void(prescription: dict) -> None:
    st.write(
        f"Void **{prescription.get('prescription_id')}**? Voided prescriptions stay in the patient's history "
        "for audit purposes and can't be restored."
    )
    reason = st.text_area("Reason for voiding (required)", key="rx_void_reason")
    confirm, cancel = st.columns(2)
    if confirm.button("Void prescription", type="primary", key="rx_void_confirm"):
        errors = void_prescription(get_prescriptions_collection(), prescription["_id"], _doctor_email(), reason)
        if errors:
            for error in errors:
                st.error(error)
            return
        _close_dialogs()
        st.session_state[FLASH_KEY] = "Prescription voided."
        st.rerun()
    if cancel.button("Cancel", key="rx_void_cancel"):
        _close_dialogs()
        st.rerun()


def _render_audit_history(prescription: dict) -> None:
    with st.expander("Audit history"):
        st.dataframe(
            [
                {
                    "When": format_date(entry.get("at"), with_time=True),
                    "Action": str(entry.get("action") or "").capitalize(),
                    "By": entry.get("by"),
                    "Details": entry.get("details"),
                }
                for entry in prescription.get("audit_history") or []
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_prescription_detail_page() -> None:
    """Read-only view of one prescription, with the actions its status allows."""
    if st.button("← Back to prescriptions", key="rx_detail_back"):
        go_to(PRESCRIPTIONS)

    patient = load_viewed_patient()
    if patient is None:
        return
    prescription = _find_prescription(patient, st.session_state.get(VIEWING_PRESCRIPTION_KEY))
    if prescription is None:
        st.info("No prescription is selected. Go back to the prescription list and click **View**.")
        return

    st.title(f"Prescription {prescription.get('prescription_id')}")
    render_simulation_notice()
    _show_flash()

    with st.container(border=True):
        render_prescription_summary(prescription)
        analysis = _analysis_labels(patient).get(str(prescription.get("analysis_id")))
        st.caption(f"Associated analysis: {analysis[1] if analysis else 'None'}")

    key = str(prescription["_id"])
    is_author = prescription.get("doctor_email") == _doctor_email()
    actions = st.columns(3)
    with actions[0]:
        render_pdf_download(prescription, key=f"rx_pdf_{key}")
    if _is_own_draft(prescription):
        if actions[1].button("Edit draft", key=f"rx_detail_edit_{key}"):
            _open_editor(prescription)
        if actions[2].button("Finalize", type="primary", key=f"rx_detail_finalize_{key}"):
            st.session_state[FINALIZE_DIALOG_KEY] = key
        if st.session_state.get(FINALIZE_DIALOG_KEY) == key:
            _confirm_finalize(key=key)
    elif prescription.get("status") == STATUS_FINALIZED and is_author:
        if actions[1].button("Void prescription", key=f"rx_detail_void_{key}"):
            st.session_state[VOID_DIALOG_KEY] = key
        if st.session_state.get(VOID_DIALOG_KEY) == key:
            _confirm_void(prescription)
    elif prescription.get("status") == STATUS_FINALIZED:
        actions[1].caption("Only the prescribing doctor can void this prescription.")

    _render_audit_history(prescription)
