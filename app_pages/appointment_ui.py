"""Streamlit pieces shared by the doctor and patient appointment pages."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import (
    ACTIVE_STATUSES,
    ROLE_DOCTOR,
    ROLE_PATIENT,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_NO_SHOW,
    STATUS_PENDING,
    STATUS_REJECTED,
    active_proposal,
    cancel_appointment,
    doctor_busy,
    format_slot,
    propose_reschedule,
    respond_to_reschedule,
    role_of,
)
from app_pages.availability_service import available_dates, generate_slots, get_availability, to_local
from app_pages.registration_page import get_appointments_collection, get_availability_collection

FLASH_KEY = "appointment_flash"

STATUS_LABELS = {
    STATUS_PENDING: "⏳ Pending",
    STATUS_CONFIRMED: "✅ Confirmed",
    STATUS_REJECTED: "❌ Rejected",
    STATUS_EXPIRED: "⌛ Expired",
    STATUS_CANCELLED: "🚫 Cancelled",
    STATUS_COMPLETED: "🏁 Completed",
    STATUS_NO_SHOW: "👻 No-show",
}


def flash(message: str, kind: str = "success") -> None:
    st.session_state[FLASH_KEY] = (kind, message)


def show_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        getattr(st, message[0])(message[1])


def show_errors(errors: list[str]) -> bool:
    for error in errors:
        st.error(error)
    return bool(errors)


def format_created(value) -> str:
    return value.strftime("%b %d, %Y %I:%M %p UTC") if hasattr(value, "strftime") else "—"


def format_remaining(until: datetime, now: datetime) -> str:
    minutes = max(0, int((until - now).total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def render_slot_picker(doctor_email: str, key: str, now: datetime) -> datetime | None:
    """Pick one of the doctor's free slots: a date first, then a time. Returns the UTC start or None."""
    availability = get_availability(get_availability_collection(), doctor_email)
    if availability is None:
        st.info("This doctor hasn't published their availability yet.")
        return None

    busy = doctor_busy(get_appointments_collection(), doctor_email, now)
    dates = available_dates(availability, now, busy)
    if not dates:
        st.info("No free appointment slots in the next 30 days.")
        return None

    tz_name = availability["timezone"]
    chosen_date = st.selectbox(
        f"Available dates ({tz_name})",
        options=dates,
        format_func=lambda value: value.strftime("%A, %b %d, %Y"),
        key=f"{key}_date",
    )
    slots = generate_slots(availability, chosen_date, now, busy)
    starts = {start: end for start, end in slots}
    return st.selectbox(
        "Available times",
        options=list(starts),
        format_func=lambda start: (
            f"{to_local(start, tz_name):%I:%M %p} - {to_local(starts[start], tz_name):%I:%M %p}"
        ),
        key=f"{key}_time",
    )


def render_appointment_details(appointment: dict, viewer_role: str, now: datetime) -> None:
    tz_name = appointment["timezone"]
    other = appointment["patient_name"] if viewer_role == ROLE_DOCTOR else appointment["doctor_name"]
    st.markdown(f"**{format_slot(appointment['start_at'], tz_name)}** · {STATUS_LABELS.get(appointment['status'])}")
    left, right = st.columns(2)
    left.write(f"**{'Patient' if viewer_role == ROLE_DOCTOR else 'Doctor'}:** {other}")
    left.write(f"**Duration:** {appointment['duration_minutes']} minutes")
    right.write(f"**Reason for visit:** {appointment.get('reason') or '—'}")
    right.write(f"**Requested:** {format_created(appointment.get('created_at'))}")

    status = appointment["status"]
    if status == STATUS_PENDING and appointment.get("expires_at"):
        st.caption(f"Awaiting doctor approval · expires in {format_remaining(appointment['expires_at'], now)}")
    elif status == STATUS_REJECTED:
        st.error(f"Rejected by the doctor. Reason: {appointment.get('rejection_reason') or 'not given'}")
    elif status == STATUS_CANCELLED:
        who = "you" if appointment.get("cancelled_by") == viewer_role else f"the {appointment.get('cancelled_by')}"
        reason = appointment.get("cancellation_reason")
        st.warning(f"Cancelled by {who}." + (f" Reason: {reason}" if reason else ""))
    elif status == STATUS_EXPIRED:
        st.caption("The doctor didn't respond in time, so this request expired and the slot was released.")


def render_reschedule_controls(appointment: dict, actor_email: str, now: datetime, key: str) -> None:
    """Respond to the other party's proposal, show your own pending one, or propose a new time."""
    if appointment["status"] not in ACTIVE_STATUSES or appointment["start_at"] <= now:
        return
    role = role_of(appointment, actor_email)
    proposal = active_proposal(appointment, now)
    if proposal:
        new_time = format_slot(proposal["start_at"], appointment["timezone"])
        if proposal["proposed_by"] == role:
            st.info(f"You proposed moving this to **{new_time}**. Waiting for the {_other(role)} to respond.")
            return
        st.info(f"The {proposal['proposed_by']} proposed moving this to **{new_time}**.")
        accept_col, reject_col = st.columns(2)
        if accept_col.button("Accept new time", key=f"{key}_resched_accept", type="primary"):
            _respond(appointment, actor_email, True, now)
        if reject_col.button("Keep original time", key=f"{key}_resched_reject"):
            _respond(appointment, actor_email, False, now)
        return

    with st.expander("Reschedule"):
        st.caption("The current time stays booked until the other party accepts the new one.")
        new_start = render_slot_picker(appointment["doctor_email"], f"{key}_resched", now)
        if new_start and st.button("Propose new time", key=f"{key}_resched_submit"):
            errors = propose_reschedule(
                get_appointments_collection(), get_availability_collection(),
                appointment["_id"], actor_email, new_start, now,
            )
            if not show_errors(errors):
                flash(f"Proposed {format_slot(new_start, appointment['timezone'])}. "
                      f"Waiting for the {_other(role)} to respond.")
                st.rerun()


def render_cancel_control(appointment: dict, actor_email: str, now: datetime, key: str) -> None:
    if appointment["status"] not in ACTIVE_STATUSES or appointment["start_at"] <= now:
        return
    with st.expander("Cancel appointment"):
        reason = st.text_input("Reason (optional)", key=f"{key}_cancel_reason")
        if st.button("Confirm cancellation", key=f"{key}_cancel_confirm"):
            errors = cancel_appointment(get_appointments_collection(), appointment["_id"], actor_email, reason, now)
            if not show_errors(errors):
                flash("Appointment cancelled. The time slot has been released.")
                st.rerun()


def _respond(appointment: dict, actor_email: str, accept: bool, now: datetime) -> None:
    errors = respond_to_reschedule(
        get_appointments_collection(), get_availability_collection(), appointment["_id"], actor_email, accept, now
    )
    if not show_errors(errors):
        flash("Appointment moved to the new time." if accept else "Kept the original time.")
        st.rerun()


def _other(role: str | None) -> str:
    return ROLE_DOCTOR if role == ROLE_PATIENT else ROLE_PATIENT
