"""Streamlit pieces shared by the doctor and patient appointment pages: the appointment card, the slot
picker and the reschedule / cancel controls.

All times are stored as naive UTC and shown in the doctor's timezone, which is always printed next to them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

import streamlit as st

from app_pages.appointment_service import (
    ACTIVE_STATUSES,
    ROLE_DOCTOR,
    ROLE_PATIENT,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_REJECTED,
    active_proposal,
    cancel_appointment,
    doctor_busy,
    propose_reschedule,
    respond_to_reschedule,
    role_of,
)
from app_pages.availability_service import available_dates, generate_slots, get_availability, to_local
from app_pages.registration_page import get_appointments_collection, get_availability_collection
from ui.components import confirmation_dialog, entity_card, flash, open_dialog, show_errors

# Flash messages queued by appointment actions and shown by the appointment pages after the rerun.
FLASH_KEY = "appointments"


# ---------------------------------------------------------------- formatting


def clock(value: datetime) -> str:
    """9:30 AM (no leading zero)."""
    return value.strftime("%I:%M %p").lstrip("0")


def format_day(value: date | datetime) -> str:
    return value.strftime("%a, %b %d, %Y")


def format_when(start: datetime, tz_name: str) -> str:
    """Date and start time in the doctor's timezone, e.g. "Wed, Nov 18, 2026, 10:00 AM (Europe/London)"."""
    local = to_local(start, tz_name)
    return f"{format_day(local)}, {clock(local)} ({tz_name})"


def format_time_range(start: datetime, end: datetime, tz_name: str) -> str:
    return f"{clock(to_local(start, tz_name))} – {clock(to_local(end, tz_name))}"


def format_created(value) -> str:
    return f"{format_day(value)}, {clock(value)} (UTC)" if hasattr(value, "strftime") else "—"


def format_remaining(until: datetime, now: datetime) -> str:
    minutes = max(0, int((until - now).total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _other(role: str | None) -> str:
    return ROLE_DOCTOR if role == ROLE_PATIENT else ROLE_PATIENT


def _other_name(appointment: dict, viewer_role: str) -> str:
    return appointment["patient_name"] if viewer_role == ROLE_DOCTOR else appointment["doctor_name"]


# ---------------------------------------------------------------- slot picking


def booking_options(doctor_email: str, now: datetime) -> tuple[dict | None, list, list[date]]:
    """(availability, busy intervals, bookable dates) for a doctor. availability is None if never published."""
    availability = get_availability(get_availability_collection(), doctor_email)
    if availability is None:
        return None, [], []
    busy = doctor_busy(get_appointments_collection(), doctor_email, now)
    return availability, busy, available_dates(availability, now, busy)


def render_slot_picker(availability: dict, busy: list, dates: list[date], key: str, now: datetime) -> datetime | None:
    """A date, then one of its free times as pills. Returns the chosen UTC start, or None if no time is picked."""
    tz_name = availability["timezone"]
    chosen_date = st.selectbox(
        "Date",
        options=dates,
        format_func=lambda value: value.strftime("%A, %b %d, %Y"),
        key=f"{key}_date",
    )
    slots = generate_slots(availability, chosen_date, now, busy)
    if not slots:
        st.caption("No free times left on this date. Choose another date.")
        return None
    labels = {start: clock(to_local(start, tz_name)) for start, _ in slots}
    # One pills widget per date, so a time picked on one date never carries over to another.
    return st.pills(
        f"Time ({tz_name})",
        options=list(labels),
        format_func=labels.get,
        selection_mode="single",
        key=f"{key}_time_{chosen_date.isoformat()}",
        help=f"Each appointment lasts {availability['slot_minutes']} minutes. Times are in {tz_name}.",
    )


# ---------------------------------------------------------------- appointment card


def appointment_card(appointment: dict, viewer_role: str, now: datetime, key: str):
    """Card for one appointment, seen by ``viewer_role``. Returns the container so callers can add actions."""
    tz_name = appointment["timezone"]
    status = appointment["status"]
    other_label = "Patient" if viewer_role == ROLE_DOCTOR else "Doctor"
    fields = [
        (other_label, _other_name(appointment, viewer_role)),
        ("Duration", f"{appointment['duration_minutes']} minutes"),
        ("Requested", format_created(appointment.get("created_at"))),
    ]
    if status == STATUS_PENDING and appointment.get("expires_at"):
        fields.append(("Expires in", format_remaining(appointment["expires_at"], now)))

    container = entity_card(
        key,
        format_when(appointment["start_at"], tz_name),
        subtitle=format_time_range(appointment["start_at"], appointment["end_at"], tz_name),
        status=("appointment", status),
        fields=fields,
        columns=len(fields),
    )
    with container:
        st.markdown(f":gray[Reason for visit]  \n{appointment.get('reason') or '—'}")
        _render_status_note(appointment, viewer_role)
    return container


def _render_status_note(appointment: dict, viewer_role: str) -> None:
    status = appointment["status"]
    if status == STATUS_PENDING and appointment.get("expires_at"):
        if viewer_role == ROLE_DOCTOR:
            st.caption(":material/hourglass_top: Respond before it expires, or the request lapses and the "
                       "slot is released.")
        else:
            st.caption(f":material/hourglass_top: Waiting for {appointment['doctor_name']} to approve. "
                       "If they don't respond in time, the request expires and the slot is released.")
    elif status == STATUS_REJECTED:
        reason = appointment.get("rejection_reason") or "No reason given."
        st.caption(f":material/info: Declined by {appointment['doctor_name']}. Reason: {reason}")
    elif status == STATUS_CANCELLED:
        who = "you" if appointment.get("cancelled_by") == viewer_role else f"the {appointment.get('cancelled_by')}"
        reason = appointment.get("cancellation_reason")
        st.caption(f":material/info: Cancelled by {who}." + (f" Reason: {reason}" if reason else ""))
    elif status == STATUS_EXPIRED:
        st.caption(":material/info: The doctor didn't respond in time, so this request expired and the slot "
                   "was released.")


# ---------------------------------------------------------------- reschedule and cancel


def _can_change(appointment: dict, now: datetime) -> bool:
    return appointment["status"] in ACTIVE_STATUSES and appointment["start_at"] > now


def _reschedule_flag(key: str) -> str:
    return f"{key}_reschedule_open"


def _toggle_reschedule(key: str) -> None:
    flag = _reschedule_flag(key)
    st.session_state[flag] = not st.session_state.get(flag, False)


def render_reschedule_proposal(appointment: dict, actor_email: str, now: datetime, key: str) -> bool:
    """Highlight a waiting reschedule proposal: the recipient can accept or keep the original time.

    Returns True if a proposal is waiting (so callers don't offer another reschedule).
    """
    if not _can_change(appointment, now):
        return False
    proposal = active_proposal(appointment, now)
    if not proposal:
        return False
    role = role_of(appointment, actor_email)
    new_time = format_when(proposal["start_at"], appointment["timezone"])
    expires = format_remaining(proposal["expires_at"], now)
    if proposal["proposed_by"] == role:
        st.info(f"You proposed moving this to **{new_time}**. Waiting for the {_other(role)} to respond "
                f"(expires in {expires}). The original time stays booked until then.",
                icon=":material/update:")
        return True

    proposer = appointment["doctor_name"] if proposal["proposed_by"] == ROLE_DOCTOR else appointment["patient_name"]
    st.warning(f"{proposer} proposed a new time: **{new_time}**. The original time stays booked until you "
               f"respond (expires in {expires}).", icon=":material/update:")
    with st.container(horizontal=True, gap="small"):
        if st.button("Accept new time", key=f"{key}_resched_accept", type="primary", icon=":material/check:"):
            _respond(appointment, actor_email, True, now)
        if st.button("Keep original time", key=f"{key}_resched_reject"):
            _respond(appointment, actor_email, False, now)
    return True


def render_change_controls(appointment: dict, actor_email: str, now: datetime, key: str,
                           *, reschedule_label: str = "Reschedule", cancel: bool = True,
                           leading_actions: Callable[[], None] | None = None) -> None:
    """Reschedule and Cancel buttons for a future active appointment, plus the reschedule panel and
    cancel dialog. Shows a waiting reschedule proposal instead of the Reschedule button.

    ``leading_actions`` draws extra buttons at the start of the same row (e.g. Accept / Reject).
    """
    if not _can_change(appointment, now):
        if leading_actions:
            with st.container(horizontal=True, gap="small"):
                leading_actions()
        return
    has_proposal = render_reschedule_proposal(appointment, actor_email, now, key)
    open_flag = _reschedule_flag(key)
    if has_proposal:
        st.session_state.pop(open_flag, None)

    dialog_key = f"{key}_cancel"
    with st.container(horizontal=True, gap="small"):
        if leading_actions:
            leading_actions()
        if not has_proposal:
            st.button(reschedule_label, key=f"{key}_resched_toggle", icon=":material/edit_calendar:",
                      on_click=_toggle_reschedule, args=(key,))
        if cancel:
            st.button("Cancel appointment", key=f"{key}_cancel_open", icon=":material/event_busy:",
                      on_click=open_dialog, args=(dialog_key,))

    if not has_proposal and st.session_state.get(open_flag):
        _render_reschedule_panel(appointment, actor_email, now, key)

    if cancel:
        _render_cancel_dialog(appointment, actor_email, now, dialog_key)


def _render_reschedule_panel(appointment: dict, actor_email: str, now: datetime, key: str) -> None:
    role = role_of(appointment, actor_email)
    st.markdown("**Propose a new time**")
    st.caption(f"The current time stays booked until the {_other(role)} accepts the new one.")
    availability, busy, dates = booking_options(appointment["doctor_email"], now)
    if availability is None:
        st.caption("The doctor hasn't published their availability, so there are no other times to offer.")
        new_start = None
    elif not dates:
        st.caption("There are no other free times in the next 30 days.")
        new_start = None
    else:
        new_start = render_slot_picker(availability, busy, dates, f"{key}_resched", now)

    with st.container(horizontal=True, gap="small"):
        if new_start is not None and st.button("Propose new time", key=f"{key}_resched_submit", type="primary"):
            errors = propose_reschedule(
                get_appointments_collection(), get_availability_collection(),
                appointment["_id"], actor_email, new_start, now,
            )
            if not show_errors(errors):
                st.session_state.pop(_reschedule_flag(key), None)
                flash(f"Proposed {format_when(new_start, appointment['timezone'])}. "
                      f"Waiting for the {_other(role)} to respond.", key=FLASH_KEY)
                st.rerun()
        st.button("Close", key=f"{key}_resched_close", on_click=_toggle_reschedule, args=(key,))


def _render_cancel_dialog(appointment: dict, actor_email: str, now: datetime, dialog_key: str) -> None:
    role = role_of(appointment, actor_email)
    other = _other_name(appointment, role or ROLE_PATIENT)

    def confirm(reason: str) -> list[str]:
        errors = cancel_appointment(get_appointments_collection(), appointment["_id"], actor_email, reason, now)
        if not errors:
            flash("Appointment cancelled. The time slot has been released.", key=FLASH_KEY)
        return errors

    confirmation_dialog(
        dialog_key,
        title="Cancel appointment?",
        message=f"Your appointment with {other} on **{format_when(appointment['start_at'], appointment['timezone'])}** "
                f"will be cancelled and the time slot released. {other} will see that you cancelled.",
        confirm_label="Cancel appointment",
        on_confirm=confirm,
        reason_label="Reason (optional)",
        danger=True,
        cancel_label="Keep appointment",
    )


def _respond(appointment: dict, actor_email: str, accept: bool, now: datetime) -> None:
    errors = respond_to_reschedule(
        get_appointments_collection(), get_availability_collection(), appointment["_id"], actor_email, accept, now
    )
    if not show_errors(errors):
        flash("Appointment moved to the new time." if accept else "Kept the original time.", key=FLASH_KEY)
        st.rerun()
