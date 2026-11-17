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
    MY_PATIENTS,
    NEW_PRESCRIPTION,
    PATIENT_OVERVIEW,
    PRESCRIPTION_DETAIL,
    PRESCRIPTION_EDITOR,
    PRESCRIPTIONS,
    VIEWING_PATIENT_KEY,
    VIEWING_PRESCRIPTION_KEY,
    go_to,
    page,
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
    format_status,
    medication_names,
    prescription_dates,
    render_medications_table,
    render_note_and_void_reason,
    render_pdf_download,
    render_simulation_notice,
)
from app_pages.registration_page import (
    get_analyses_collection,
    get_prescriptions_collection,
    get_requests_collection,
    get_users_collection,
)
from ui.components import (
    card,
    chart_container,
    confirmation_dialog,
    data_table,
    empty_state,
    entity_card,
    field_grid,
    flash,
    form_section,
    open_dialog,
    page_header,
    search_and_filter,
    show_errors,
    show_flash,
)

EDITOR_STATE_KEY = "rx_editor"
# Messages queued with flash(..., key=FLASH_KEY) are shown on the next prescription page.
FLASH_KEY = "rx"
# A page to open at the start of the next run, set where switching pages directly isn't possible
# (button callbacks, confirmation dialogs).
PENDING_PAGE_KEY = "rx_pending_page"
ALL_STATUSES = [STATUS_DRAFT, STATUS_FINALIZED, STATUS_VOIDED]
LIST_FILTER_KEY = "rx-list"
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
            f"{analysis.get('top_disease') or 'Analysis'} ({format_date(analysis.get('created_at'))})",
        )
        for analysis in get_patient_analyses(get_analyses_collection(), patient["email"])
    }


def _breadcrumb(patient: dict, *current: str) -> list[tuple[str, object | None]]:
    """My patients / {patient} / Prescriptions [/ current]. The last item is the current page."""
    trail = [("My patients", page(MY_PATIENTS)), (patient["name"], page(PATIENT_OVERVIEW))]
    if current:
        return [*trail, ("Prescriptions", page(PRESCRIPTIONS)), *[(label, None) for label in current]]
    return [*trail, ("Prescriptions", None)]


def _follow_pending_navigation() -> None:
    target = st.session_state.pop(PENDING_PAGE_KEY, None)
    if target:
        go_to(target)


def open_prescription_list() -> None:
    go_to(PRESCRIPTIONS)


def open_prescription_detail(prescription: dict) -> None:
    """Open a prescription's detail page (also from the cross-patient Prescriptions page)."""
    st.session_state[VIEWING_PATIENT_KEY] = prescription.get("patient_email")
    st.session_state[VIEWING_PRESCRIPTION_KEY] = str(prescription["_id"])
    go_to(PRESCRIPTION_DETAIL)


def _select_for_editor(prescription: dict | None = None) -> None:
    st.session_state[EDITING_PRESCRIPTION_KEY] = str(prescription["_id"]) if prescription else NEW_PRESCRIPTION
    st.session_state.pop(EDITOR_STATE_KEY, None)


def _open_editor(prescription: dict | None = None) -> None:
    _select_for_editor(prescription)
    go_to(PRESCRIPTION_EDITOR)


def _request_new_prescription() -> None:
    """Button callback: open the editor for a new prescription on the next run."""
    _select_for_editor()
    st.session_state[PENDING_PAGE_KEY] = PRESCRIPTION_EDITOR


def _clear_list_filters() -> None:
    st.session_state[f"{LIST_FILTER_KEY}-search"] = ""
    st.session_state[f"{LIST_FILTER_KEY}-filter"] = list(ALL_STATUSES)


# ---------------------------------------------------------------- list page


def render_prescriptions_page() -> None:
    """All of a patient's prescriptions visible to this doctor, with search and status filters."""
    _follow_pending_navigation()
    patient = load_viewed_patient()
    if patient is None:
        return

    actions = page_header(
        "Prescriptions", f"Simulated prescriptions for {patient['name']}", breadcrumb=_breadcrumb(patient)
    )
    if actions.button("Create prescription", type="primary", icon=":material/add:", key="rx_create"):
        _open_editor()
    show_flash(FLASH_KEY)
    render_simulation_notice()

    prescriptions = list_prescriptions_for_doctor(get_prescriptions_collection(), _doctor_email(), patient["email"])
    if not prescriptions:
        empty_state(
            "No prescriptions yet",
            f"Create a simulated prescription for {patient['name']}. It stays a draft only you can see until you "
            "finalize it.",
            icon=":material/medication:",
            key="rx-list-none",
            action_label="Create prescription",
            on_action=_request_new_prescription,
        )
        return

    query, statuses = search_and_filter(
        LIST_FILTER_KEY,
        placeholder="Search by prescription ID or medication",
        filters=ALL_STATUSES,
        format_filter=format_status,
    )
    shown = [
        prescription
        for prescription in prescriptions
        if prescription.get("status") in statuses
        and (not query or query in f"{prescription.get('prescription_id')} {medication_names(prescription)}".lower())
    ]
    if not shown:
        empty_state(
            "No prescriptions match",
            "Try a different search or status filter.",
            icon=":material/filter_alt_off:",
            key="rx-list-filtered",
            action_label="Clear filters",
            on_action=_clear_list_filters,
        )
        return

    analyses = _analysis_labels(patient)
    for prescription in shown:
        key = str(prescription["_id"])
        analysis = analyses.get(str(prescription.get("analysis_id")))
        container = entity_card(
            f"rx-{key}",
            str(prescription.get("prescription_id")),
            subtitle=medication_names(prescription),
            status=("prescription", prescription.get("status")),
            fields=[
                ("Created", format_date(prescription.get("created_at"))),
                ("Medications", len(prescription.get("medications") or [])),
                ("Associated analysis", analysis[1] if analysis else None),
            ],
        )
        with container, st.container(horizontal=True, gap="small"):
            if st.button("View", key=f"rx_view_{key}", icon=":material/visibility:"):
                open_prescription_detail(prescription)
            if _is_own_draft(prescription) and st.button("Edit draft", key=f"rx_edit_{key}", icon=":material/edit:"):
                _open_editor(prescription)


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
    medications = []
    for index, row in enumerate(list(editor["rows"]), start=1):
        if index > 1:
            st.divider()
        header, remove = st.columns([4, 1], vertical_alignment="center")
        header.markdown(f"**Medication {index}**")
        with remove.container(horizontal=True, horizontal_alignment="right"):
            st.button(
                "Remove", key=_widget_key(editor, f"{row}_remove"), icon=":material/delete:", type="tertiary",
                disabled=len(editor["rows"]) == 1, help=f"Remove medication {index}",
                on_click=editor["rows"].remove, args=(row,),
            )
        columns = st.columns(4)
        for column, field in zip(columns, ("name", "dosage", "frequency", "duration")):
            column.text_input(FIELD_LABELS[field], key=_widget_key(editor, f"{row}_{field}"))
        st.text_input(FIELD_LABELS["instructions"], key=_widget_key(editor, f"{row}_instructions"))
        medications.append(
            {field: st.session_state.get(_widget_key(editor, f"{row}_{field}"), "") for field in MEDICATION_FIELDS}
        )

    # Callbacks rather than st.rerun() mid-page, so every row's widgets are drawn on each run and keep their values.
    st.button("Add medication", key=_widget_key(editor, "add_row"), icon=":material/add:",
              on_click=_add_row, args=(editor,))
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


FINALIZE_MESSAGE = (
    "Once finalized, this simulated prescription **can't be edited** and becomes visible to the patient. "
    "You can still void it later with a reason."
)


def _finalize_dialog(dialog_key: str, save_first=None, key: str | None = None) -> None:
    """Confirm finalizing. From the editor, ``save_first()`` saves the draft and returns (key, errors) first."""

    def confirm(_reason: str) -> list[str]:
        target, errors = (save_first() if save_first is not None else (key, []))
        if not errors:
            errors = _finalize(target)
        if errors:
            return errors
        st.session_state.pop(EDITOR_STATE_KEY, None)
        st.session_state[VIEWING_PRESCRIPTION_KEY] = target
        st.session_state[PENDING_PAGE_KEY] = PRESCRIPTION_DETAIL
        flash("Prescription finalized.", key=FLASH_KEY)
        return []

    confirmation_dialog(
        dialog_key,
        title="Finalize prescription",
        message=FINALIZE_MESSAGE,
        confirm_label="Finalize prescription",
        on_confirm=confirm,
    )


def _editor_unavailable(patient: dict, title: str, message: str) -> None:
    page_header(title, breadcrumb=_breadcrumb(patient, title))
    empty_state(title, message, icon=":material/edit_off:", key="rx-editor-unavailable",
                action_label="Go to prescriptions", page=page(PRESCRIPTIONS))


def render_prescription_editor_page() -> None:
    """Create a new draft or edit one of the doctor's own drafts."""
    _follow_pending_navigation()
    patient = load_viewed_patient()
    if patient is None:
        return

    key = st.session_state.get(EDITING_PRESCRIPTION_KEY)
    existing = None
    if not key:
        _editor_unavailable(patient, "No prescription selected",
                            "Choose Create prescription or Edit draft on the prescription list.")
        return
    if key != NEW_PRESCRIPTION:
        existing = _find_prescription(patient, key)
        if existing is None or not _is_own_draft(existing):
            _editor_unavailable(patient, "This prescription can't be edited",
                                "Only your own draft prescriptions can be edited. Finalized prescriptions are "
                                "read-only.")
            return

    editor = st.session_state.get(EDITOR_STATE_KEY)
    if editor is None or editor.get("for") != key:
        editor = _init_editor(key, existing)

    title = "Edit draft prescription" if existing else "Create prescription"
    page_header(
        title,
        f"Simulated prescription for {patient['name']}",
        breadcrumb=_breadcrumb(patient, editor["prescription_id"] if existing else "New prescription"),
    )
    render_simulation_notice()

    doctor = _doctor()
    with form_section("Prescription details", "Filled in automatically.", key="rx-details"):
        field_grid(
            [
                ("Prescription ID", editor["prescription_id"]),
                ("Date", format_date(existing["created_at"] if existing else datetime.utcnow())),
                ("Status", STATUS_LABELS[STATUS_DRAFT]),
                ("Patient", f"{patient['name']} (ID {patient.get('id')})"),
                ("Doctor", f"{format_person_name(doctor, doctor=True)} (ID {doctor.get('_id')})"),
            ]
        )

    analyses = _analysis_labels(patient)
    with form_section(
        "Linked analysis and note",
        "A linked analysis is for reference only. It never fills in or suggests medications.",
        key="rx-links",
    ):
        analysis_key = st.selectbox(
            "Associated analysis (optional)",
            options=[None, *analyses.keys()],
            format_func=lambda option: "None" if option is None else analyses[option][1],
            key=_widget_key(editor, "analysis"),
        )
        analysis_id = analyses[analysis_key][0] if analysis_key in analyses else None
        note = st.text_area("Doctor's note (optional)", key=_widget_key(editor, "note"))

    with form_section("Medications", "Enter every detail manually. Nothing is pre-filled or suggested.",
                      key="rx-medications"):
        medications = _render_medication_rows(editor)

    def save_first():
        return _save(existing, patient, editor, medications, note, analysis_id)

    errors: list[str] = []
    with card("rx-editor-actions", raised=True):
        with st.container(horizontal=True, gap="small"):
            save_clicked = st.button("Save draft", type="primary", icon=":material/save:",
                                     key=_widget_key(editor, "save"))
            finalize_clicked = st.button("Finalize", icon=":material/verified:", key=_widget_key(editor, "finalize"))
            cancel_clicked = st.button("Cancel", key=_widget_key(editor, "cancel"))
        if save_clicked:
            _, errors = save_first()
            if not errors:
                st.session_state.pop(EDITOR_STATE_KEY, None)
                flash(f"Draft {editor['prescription_id']} saved.", key=FLASH_KEY)
                go_to(PRESCRIPTIONS)
        if finalize_clicked:
            _, errors = clean_medications(medications)
            if not errors:
                open_dialog(f"rx-finalize-{editor['nonce']}")
        if cancel_clicked:
            st.session_state.pop(EDITOR_STATE_KEY, None)
            go_to(PRESCRIPTIONS)
        show_errors(errors)

    _finalize_dialog(f"rx-finalize-{editor['nonce']}", save_first=save_first)


# ---------------------------------------------------------------- detail page


def _void_dialog(prescription: dict) -> None:
    def confirm(reason: str) -> list[str]:
        errors = void_prescription(get_prescriptions_collection(), prescription["_id"], _doctor_email(), reason)
        if not errors:
            flash("Prescription voided.", key=FLASH_KEY)
        return errors

    confirmation_dialog(
        f"rx-void-{prescription['_id']}",
        title="Void prescription",
        message=(
            f"Void **{prescription.get('prescription_id')}**? Voided prescriptions stay in the patient's history "
            "for audit purposes and can't be restored."
        ),
        confirm_label="Void prescription",
        on_confirm=confirm,
        reason_label="Reason for voiding",
        reason_required=True,
        danger=True,
    )


def _render_audit_history(prescription: dict) -> None:
    with st.expander("Audit history", icon=":material/history:"):
        data_table(
            [
                {
                    "When": format_date(entry.get("at"), with_time=True),
                    "Action": str(entry.get("action") or "").capitalize(),
                    "By": entry.get("by"),
                    "Details": entry.get("details"),
                }
                for entry in prescription.get("audit_history") or []
            ]
        )


def render_prescription_detail_page() -> None:
    """Read-only view of one prescription, with the actions its status allows."""
    _follow_pending_navigation()
    patient = load_viewed_patient()
    if patient is None:
        return
    prescription = _find_prescription(patient, st.session_state.get(VIEWING_PRESCRIPTION_KEY))
    if prescription is None:
        page_header("Prescription", breadcrumb=_breadcrumb(patient, "Prescription"))
        empty_state("No prescription selected", "Open a prescription from the list to see its details.",
                    icon=":material/description:", key="rx-detail-none",
                    action_label="Go to prescriptions", page=page(PRESCRIPTIONS))
        return

    key = str(prescription["_id"])
    status = prescription.get("status")
    is_author = prescription.get("doctor_email") == _doctor_email()
    actions = page_header(
        str(prescription.get("prescription_id")),
        f"Simulated prescription for {patient['name']}",
        breadcrumb=_breadcrumb(patient, str(prescription.get("prescription_id"))),
    )
    with actions:
        render_pdf_download(prescription, key=f"rx_pdf_{key}")
        if _is_own_draft(prescription):
            if st.button("Edit draft", key=f"rx_detail_edit_{key}", icon=":material/edit:"):
                _open_editor(prescription)
            if st.button("Finalize", type="primary", key=f"rx_detail_finalize_{key}", icon=":material/verified:"):
                open_dialog(f"rx-finalize-{key}")
        elif status == STATUS_FINALIZED and is_author:
            if st.button("Void prescription", key=f"rx_detail_void_{key}", icon=":material/block:"):
                open_dialog(f"rx-void-{key}")
    show_flash(FLASH_KEY)
    render_simulation_notice()

    analysis = _analysis_labels(patient).get(str(prescription.get("analysis_id")))
    summary = entity_card(
        f"rx-summary-{key}",
        "Summary",
        status=("prescription", status),
        fields=[
            ("Patient", f"{prescription.get('patient_name')} (ID {prescription.get('patient_id')})"),
            ("Doctor", f"{prescription.get('doctor_name')} (ID {prescription.get('doctor_id')})"),
            *prescription_dates(prescription),
            ("Associated analysis", analysis[1] if analysis else "None"),
        ],
    )
    with summary:
        render_note_and_void_reason(prescription)
        if status == STATUS_FINALIZED and not is_author:
            st.caption("Only the prescribing doctor can void this prescription.")

    with chart_container("Medications", key=f"rx-medications-{key}"):
        render_medications_table(prescription.get("medications") or [])

    _render_audit_history(prescription)

    if _is_own_draft(prescription):
        _finalize_dialog(f"rx-finalize-{key}", key=key)
    elif status == STATUS_FINALIZED and is_author:
        _void_dialog(prescription)

