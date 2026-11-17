"""Patient "My doctors" page: current Primary Health Practitioner, doctors to request, and request history."""

from __future__ import annotations

import streamlit as st

from app_pages.practitioner_service import (
    REQUEST_TYPE_CHANGE,
    STATUS_ACCEPTED,
    cancel_practitioner_request,
    format_person_name,
    get_patient_request_history,
    get_pending_practitioner_request,
    get_primary_practitioner,
    get_unseen_decisions,
    list_doctors,
    mark_decisions_seen,
    request_primary_practitioner,
)
from app_pages.registration_page import get_requests_collection, get_users_collection
from ui.components import (
    card,
    data_table,
    empty_state,
    entity_card,
    error_message,
    field_grid,
    page_header,
    section_header,
    status_badge,
    status_label,
)

GRID_COLUMNS = 3
FLASH_KEY = "php_flash"
FLASH_ICONS = {"success": ":material/check_circle:", "error": ":material/error:", "info": ":material/info:"}


def _collections():
    users_collection = get_users_collection()
    if users_collection is None:
        return None, None
    return users_collection, get_requests_collection()


def _patient_email() -> str:
    user = st.session_state.get("authenticated_user") or {}
    return str(user.get("email") or "").strip().lower()


def _format_time(value) -> str:
    return value.strftime("%b %d, %Y %I:%M %p UTC") if hasattr(value, "strftime") else "Recently"


def _md(text) -> str:
    """Escape user-entered text so it renders literally inside st.markdown."""
    value = str(text or "")
    for char in "\\`*_[]<>#|~$":
        value = value.replace(char, f"\\{char}")
    return value


def _doctor_fields(doctor: dict) -> list[tuple[str, object]]:
    years = doctor.get("yoe")
    return [
        ("Degree", _md(doctor.get("degree")) or "Not provided"),
        ("Experience", f"{years} years" if years not in (None, "") else "Not provided"),
        ("Clinic or hospital", _md(doctor.get("clinic_or_hospital")) or "Not provided"),
    ]


def render_practitioner_notifications() -> None:
    """Tell the patient when a doctor has accepted or declined their request."""
    _, requests_collection = _collections()
    decisions = get_unseen_decisions(requests_collection, _patient_email())
    if not decisions:
        return

    for decision in decisions:
        doctor_name = decision.get("doctor_name") or decision.get("doctor_email") or "The doctor"
        if decision.get("status") == STATUS_ACCEPTED:
            st.success(
                f"{_md(doctor_name)} accepted your request and is now your Primary Health Practitioner.",
                icon=":material/check_circle:",
            )
        else:
            st.error(
                f"{_md(doctor_name)} declined your request to become your Primary Health Practitioner. "
                "You can ask another doctor below.",
                icon=":material/block:",
            )

    if st.button("Dismiss", key="dismiss_php_notifications", icon=":material/close:"):
        mark_decisions_seen(requests_collection, _patient_email())
        st.rerun()


def _show_flash() -> None:
    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message, icon=FLASH_ICONS.get(kind))


def _render_current_practitioner(current: dict | None) -> None:
    section_header("Your Primary Health Practitioner")
    if not current:
        empty_state(
            "You don't have a Primary Health Practitioner yet",
            "Choose a doctor below and send a request. Once they accept, you can book appointments with them.",
            icon=":material/medical_services:",
            key="no-practitioner",
        )
        return

    with card("current-practitioner", raised=True):
        name_col, badge_col = st.columns([4, 1], vertical_alignment="center")
        with name_col:
            st.markdown(f"### {_md(format_person_name(current, doctor=True))}")
            st.markdown(f":gray[{_md(current.get('speciality')) or 'Speciality not provided'}]")
        with badge_col.container(horizontal=True, horizontal_alignment="right"):
            status_badge("connection", STATUS_ACCEPTED)
        field_grid(_doctor_fields(current))
        st.caption(
            "You can have one Primary Health Practitioner. If you request another doctor and they accept, "
            "they replace your current one."
        )


def _render_pending(pending: dict, requests_collection, patient_email: str) -> None:
    container = entity_card(
        "pending-request",
        _md(pending.get("doctor_name") or pending.get("doctor_email")),
        subtitle="Waiting for the doctor to reply. You can request another doctor once they reply or you cancel.",
        status=("connection", "pending"),
        fields=[("Sent", _format_time(pending.get("created_at")))],
    )
    with container:
        if st.button("Cancel request", key="php_cancel_pending", icon=":material/close:"):
            if cancel_practitioner_request(requests_collection, pending["_id"], patient_email):
                st.session_state[FLASH_KEY] = ("success", "Your request was cancelled.")
            else:
                st.session_state[FLASH_KEY] = (
                    "info", "This request was already answered, so there was nothing to cancel."
                )
            st.rerun()


def _render_doctor_card(
    doctor: dict,
    *,
    users_collection,
    requests_collection,
    current_email: str | None,
    pending: dict | None,
) -> None:
    doctor_email = str(doctor.get("email") or "").strip().lower()

    container = entity_card(
        f"doctor-{doctor_email}",
        _md(format_person_name(doctor, doctor=True)),
        subtitle=_md(doctor.get("speciality")) or "Speciality not provided",
        fields=_doctor_fields(doctor),
        columns=1,
    )
    with container:
        if doctor_email == current_email:
            st.button("Your current practitioner", key=f"php_current_{doctor_email}", disabled=True,
                      icon=":material/check_circle:", width="stretch")
            return
        if pending and pending.get("doctor_email") == doctor_email:
            st.button("Request pending", key=f"php_pending_{doctor_email}", disabled=True,
                      icon=":material/hourglass_top:", width="stretch")
            return

        if st.button(
            "Request to enroll",
            key=f"php_request_{doctor_email}",
            type="primary",
            disabled=pending is not None,
            width="stretch",
            help="Cancel your pending request first" if pending is not None else None,
        ):
            user = st.session_state.get("authenticated_user") or {}
            _, error = request_primary_practitioner(users_collection, requests_collection, user, doctor_email)
            if error:
                st.session_state[FLASH_KEY] = ("error", error)
            else:
                st.session_state[FLASH_KEY] = (
                    "success",
                    f"Your request was sent to {format_person_name(doctor, doctor=True)}.",
                )
            st.rerun()


def _render_history(history: list[dict]) -> None:
    section_header("Request history", "Your most recent requests")
    rows = [
        {
            "Doctor": request.get("doctor_name") or request.get("doctor_email"),
            "Type": "Change practitioner" if request.get("request_type") == REQUEST_TYPE_CHANGE else "Enroll",
            "Status": status_label("connection", request.get("status")),
            "Sent": _format_time(request.get("created_at")),
        }
        for request in history
    ]
    data_table(rows)


def render() -> None:
    """Render the patient's My doctors page."""
    users_collection, requests_collection = _collections()

    page_header("My doctors", "Your Primary Health Practitioner and the doctors you can ask to take you on")
    if users_collection is None:
        error_message(
            "Doctor connections aren't available right now because the database isn't connected.",
            "Try again later.",
        )
        return

    patient_email = _patient_email()
    current = get_primary_practitioner(users_collection, requests_collection, patient_email)
    current_email = str(current.get("email") or "").strip().lower() if current else None
    pending = get_pending_practitioner_request(requests_collection, patient_email)

    render_practitioner_notifications()
    _show_flash()

    _render_current_practitioner(current)
    if pending:
        _render_pending(pending, requests_collection, patient_email)

    section_header(
        "Available doctors",
        "Request a different doctor to change your practitioner" if current else "Choose a doctor to request",
    )
    doctors = list_doctors(users_collection)
    if not doctors:
        empty_state(
            "No doctors available yet",
            "Doctors appear here once they join DeltaAI. Check back later.",
            icon=":material/medical_services:",
            key="no-doctors",
        )
    else:
        for row_start in range(0, len(doctors), GRID_COLUMNS):
            columns = st.columns(GRID_COLUMNS, gap="medium")
            for column, doctor in zip(columns, doctors[row_start:row_start + GRID_COLUMNS]):
                with column:
                    _render_doctor_card(
                        doctor,
                        users_collection=users_collection,
                        requests_collection=requests_collection,
                        current_email=current_email,
                        pending=pending,
                    )

    history = get_patient_request_history(requests_collection, patient_email)
    if history:
        _render_history(history)
