"""Patient page for requesting (or changing) a Primary Health Practitioner."""

from __future__ import annotations

import streamlit as st

from app_pages.practitioner_service import (
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    STATUS_DECLINED,
    STATUS_PENDING,
    STATUS_REPLACED,
    cancel_practitioner_request,
    format_person_name,
    get_patient_request_history,
    get_pending_practitioner_request,
    get_primary_practitioner,
    get_primary_practitioner_email,
    get_unseen_decisions,
    list_doctors,
    mark_decisions_seen,
    request_primary_practitioner,
)
from app_pages.registration_page import get_requests_collection, get_users_collection

TAB_LABEL_REQUEST = "Request for Primary Health Practitioner"
TAB_LABEL_CHANGE = "Request to change the Primary Health Practitioner"
GRID_COLUMNS = 3

STATUS_LABELS = {
    STATUS_PENDING: "⏳ Pending",
    STATUS_ACCEPTED: "✅ Accepted",
    STATUS_DECLINED: "❌ Declined",
    STATUS_CANCELLED: "Cancelled",
    STATUS_REPLACED: "Ended (changed practitioner)",
}


def _collections():
    users_collection = get_users_collection()
    if users_collection is None:
        return None, None
    return users_collection, get_requests_collection()


def _patient_email() -> str:
    user = st.session_state.get("authenticated_user") or {}
    return str(user.get("email") or "").strip().lower()


def _format_time(value) -> str:
    return value.strftime("%b %d, %Y %I:%M %p") if hasattr(value, "strftime") else "Recently"


def get_tab_label() -> str:
    """Return the tab label, which depends on whether the patient already has a PHP."""
    users_collection, requests_collection = _collections()
    if get_primary_practitioner_email(users_collection, requests_collection, _patient_email()):
        return TAB_LABEL_CHANGE
    return TAB_LABEL_REQUEST


def render_practitioner_notifications() -> None:
    """Tell the patient when a doctor has accepted or declined their request."""
    _, requests_collection = _collections()
    decisions = get_unseen_decisions(requests_collection, _patient_email())
    if not decisions:
        return

    for decision in decisions:
        doctor_name = decision.get("doctor_name") or decision.get("doctor_email") or "The doctor"
        if decision.get("status") == STATUS_ACCEPTED:
            st.success(f"{doctor_name} accepted your request and is now your Primary Health Practitioner.")
        else:
            st.error(f"{doctor_name} declined your request to become your Primary Health Practitioner.")

    if st.button("Dismiss notifications", key="dismiss_php_notifications"):
        mark_decisions_seen(requests_collection, _patient_email())
        st.rerun()


def _render_doctor_details(doctor: dict) -> None:
    st.markdown(f"#### {format_person_name(doctor, doctor=True)}")
    st.write(f"**Specialization:** {doctor.get('speciality') or 'Not provided'}")
    st.write(f"**Degree:** {doctor.get('degree') or 'Not provided'}")
    if doctor.get("yoe") not in (None, ""):
        st.write(f"**Experience:** {doctor.get('yoe')} years")
    if doctor.get("clinic_or_hospital"):
        st.write(f"**Clinic / Hospital:** {doctor['clinic_or_hospital']}")


def _render_doctor_card(
    doctor: dict,
    *,
    users_collection,
    requests_collection,
    current_email: str | None,
    pending: dict | None,
) -> None:
    doctor_email = str(doctor.get("email") or "").strip().lower()

    with st.container(border=True):
        _render_doctor_details(doctor)

        if doctor_email == current_email:
            st.button("Your current practitioner", key=f"php_current_{doctor_email}", disabled=True)
            return
        if pending and pending.get("doctor_email") == doctor_email:
            st.button("Request pending", key=f"php_pending_{doctor_email}", disabled=True)
            return

        if st.button(
            "Request to enroll",
            key=f"php_request_{doctor_email}",
            type="primary",
            disabled=pending is not None,
            use_container_width=True,
        ):
            user = st.session_state.get("authenticated_user") or {}
            _, error = request_primary_practitioner(users_collection, requests_collection, user, doctor_email)
            if error:
                st.session_state["php_flash"] = ("error", error)
            else:
                st.session_state["php_flash"] = (
                    "success",
                    f"Your request was sent to {format_person_name(doctor, doctor=True)}.",
                )
            st.rerun()


def render() -> None:
    """Render the Primary Health Practitioner tab for patients."""
    users_collection, requests_collection = _collections()
    if users_collection is None:
        st.warning("MongoDB is not configured, so practitioner requests are unavailable.")
        return

    patient_email = _patient_email()
    current = get_primary_practitioner(users_collection, requests_collection, patient_email)
    current_email = str(current.get("email") or "").strip().lower() if current else None
    pending = get_pending_practitioner_request(requests_collection, patient_email)

    st.title(TAB_LABEL_CHANGE if current else TAB_LABEL_REQUEST)

    flash = st.session_state.pop("php_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    if current:
        st.subheader("Your Primary Health Practitioner")
        with st.container(border=True):
            _render_doctor_details(current)
        st.caption("You can have only one Primary Health Practitioner. Requesting another doctor replaces your current one once they accept.")
    else:
        st.caption("Choose a doctor below to request them as your Primary Health Practitioner.")

    if pending:
        st.info(
            f"Your request to {pending.get('doctor_name') or pending.get('doctor_email')} is pending "
            f"(sent {_format_time(pending.get('created_at'))}). You can send a new request after the doctor "
            "responds or after you cancel this one."
        )
        if st.button("Cancel pending request", key="php_cancel_pending"):
            cancel_practitioner_request(requests_collection, pending["_id"], patient_email)
            st.rerun()

    st.markdown("---")
    st.subheader("Available doctors")
    doctors = list_doctors(users_collection)
    if not doctors:
        st.info("No doctors are registered yet.")
    else:
        for row_start in range(0, len(doctors), GRID_COLUMNS):
            columns = st.columns(GRID_COLUMNS)
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
        st.markdown("---")
        st.subheader("Your requests")
        for request in history:
            status = STATUS_LABELS.get(request.get("status"), str(request.get("status") or "").capitalize())
            st.write(
                f"**{request.get('doctor_name') or request.get('doctor_email')}** · {status} · "
                f"sent {_format_time(request.get('created_at'))}"
            )
