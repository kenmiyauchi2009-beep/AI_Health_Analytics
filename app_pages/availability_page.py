"""Doctor page for configuring working hours, appointment length, breaks, timezone and blocked periods."""

from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta

import streamlit as st

from app_pages.appointment_service import doctor_busy
from app_pages.availability_service import (
    MAX_BREAK_MINUTES,
    SLOT_DURATIONS,
    WEEKDAYS,
    default_availability,
    generate_slots,
    get_availability,
    local_today,
    parse_local_datetime,
    parse_time,
    save_availability,
    timezone_options,
    to_local,
)
from app_pages.doctor_navigation import APPOINTMENTS, DASHBOARD, go_to
from app_pages.registration_page import get_appointments_collection, get_availability_collection

EDITOR_KEY = "availability_editor"


def _doctor() -> dict:
    return st.session_state.get("authenticated_user") or {}


def _key(editor: dict, name: str) -> str:
    # The nonce gives each editing session fresh widgets, so stale values never leak in.
    return f"avail_{editor['nonce']}_{name}"


def _init_editor(saved: dict | None) -> dict:
    availability = saved or default_availability(_doctor().get("email"))
    # "times" keeps each interval's values in the editor too: Streamlit drops a widget's state on runs
    # where it isn't drawn (e.g. while its day is unticked), and we restore it from here.
    editor = {
        "nonce": secrets.token_hex(4),
        "days": {},
        "times": {},
        "next_row": 0,
        "blocked": list(availability.get("blocked") or []),
    }
    st.session_state[_key(editor, "timezone")] = availability["timezone"]
    st.session_state[_key(editor, "slot")] = availability["slot_minutes"]
    st.session_state[_key(editor, "break")] = availability["break_minutes"]
    for day in range(7):
        intervals = (availability.get("weekly") or {}).get(str(day)) or []
        editor["days"][day] = []
        st.session_state[_key(editor, f"working_{day}")] = bool(intervals)
        for interval in intervals or [{"start": "09:00", "end": "17:00"}]:
            _add_interval(editor, day, parse_time(interval["start"]), parse_time(interval["end"]))
    st.session_state[EDITOR_KEY] = editor
    return editor


def _add_interval(editor: dict, day: int, start: time, end: time) -> None:
    row = editor["next_row"]
    editor["next_row"] += 1
    editor["days"][day].append(row)
    editor["times"][row] = (start, end)
    st.session_state[_key(editor, f"{row}_start")] = start
    st.session_state[_key(editor, f"{row}_end")] = end


def _add_next_interval(editor: dict, day: int) -> None:
    """Button callback: a one-hour interval starting where the day's last one ends."""
    last_end = datetime.combine(date.today(), editor["times"][editor["days"][day][-1]][1])
    start = min(last_end, datetime.combine(date.today(), time(22, 0)))
    _add_interval(editor, day, start.time(), (start + timedelta(hours=1)).time())


def _remove_interval(editor: dict, day: int, row: int) -> None:
    editor["days"][day].remove(row)
    editor["times"].pop(row, None)


def _render_day(editor: dict, day: int) -> list[dict]:
    with st.container(border=True):
        working = st.checkbox(f"**{WEEKDAYS[day]}**", key=_key(editor, f"working_{day}"))
        if not working:
            return []
        intervals = []
        for row in editor["days"][day]:
            start_key, end_key = _key(editor, f"{row}_start"), _key(editor, f"{row}_end")
            st.session_state.setdefault(start_key, editor["times"][row][0])
            st.session_state.setdefault(end_key, editor["times"][row][1])
            start_col, end_col, remove_col = st.columns([2, 2, 1], vertical_alignment="bottom")
            start = start_col.time_input("Start", key=start_key, step=timedelta(minutes=15))
            end = end_col.time_input("End", key=end_key, step=timedelta(minutes=15))
            editor["times"][row] = (start, end)
            remove_col.button(
                "Remove", key=_key(editor, f"{row}_remove"), disabled=len(editor["days"][day]) == 1,
                on_click=_remove_interval, args=(editor, day, row),
            )
            intervals.append({"start": f"{start:%H:%M}", "end": f"{end:%H:%M}"})
        st.button("+ Add interval", key=_key(editor, f"add_{day}"), on_click=_add_next_interval, args=(editor, day))
        return intervals


def _render_blocked(editor: dict) -> None:
    st.subheader("Blocked dates and times")
    st.caption("Vacations, holidays or any time you can't see patients. Blocked times never appear as bookable slots.")
    if not editor["blocked"]:
        st.caption("Nothing blocked.")
    for index, block in enumerate(list(editor["blocked"])):
        start, end = parse_local_datetime(block["start"]), parse_local_datetime(block["end"])
        text_col, remove_col = st.columns([5, 1], vertical_alignment="center")
        text_col.write(f"**{start:%a %b %d, %Y %I:%M %p}** → **{end:%a %b %d, %Y %I:%M %p}**"
                       + (f" · {block['reason']}" if block.get("reason") else ""))
        remove_col.button("Remove", key=_key(editor, f"block_remove_{index}"),
                          on_click=editor["blocked"].pop, args=(index,))

    with st.expander("Add a blocked period"):
        all_day = st.checkbox("Whole days", value=True, key=_key(editor, "block_all_day"))
        start_col, end_col = st.columns(2)
        start_date = start_col.date_input("From", key=_key(editor, "block_start_date"))
        end_date = end_col.date_input("To", key=_key(editor, "block_end_date"))
        if all_day:
            start = datetime.combine(start_date, time(0, 0))
            end = datetime.combine(end_date + timedelta(days=1), time(0, 0))
        else:
            start = datetime.combine(start_date, start_col.time_input("From time", value=time(9, 0),
                                                                      key=_key(editor, "block_start_time")))
            end = datetime.combine(end_date, end_col.time_input("To time", value=time(17, 0),
                                                                key=_key(editor, "block_end_time")))
        reason = st.text_input("Reason (optional)", placeholder="e.g. Vacation", key=_key(editor, "block_reason"))
        if st.button("Add blocked period", key=_key(editor, "block_add")):
            if start >= end:
                st.error("The blocked period must end after it starts.")
            else:
                editor["blocked"].append({"start": f"{start:%Y-%m-%dT%H:%M}", "end": f"{end:%Y-%m-%dT%H:%M}",
                                          "reason": reason.strip()})
                st.rerun()


def _render_preview(saved: dict) -> None:
    st.subheader("Preview bookable slots")
    now = datetime.utcnow()
    chosen = st.date_input("Date", value=local_today(saved, now), key="availability_preview_date")
    busy = doctor_busy(get_appointments_collection(), _doctor().get("email"), now)
    slots = generate_slots(saved, chosen, now, busy)
    if not slots:
        st.info("No bookable slots on this date.")
        return
    tz_name = saved["timezone"]
    st.write(" · ".join(f"{to_local(start, tz_name):%I:%M %p}" for start, _ in slots))
    st.caption(f"Times in {tz_name}. Already-reserved and blocked times are left out.")


def render_page() -> None:
    """Doctor availability settings."""
    nav_back, nav_appointments, _ = st.columns([1, 1, 3])
    if nav_back.button("← Back to dashboard", key="availability_back"):
        go_to(DASHBOARD)
    if nav_appointments.button("Appointments", key="availability_appointments"):
        go_to(APPOINTMENTS)

    st.title("My Availability")
    flash_message = st.session_state.pop("availability_flash", None)
    if flash_message:
        st.success(flash_message)

    collection = get_availability_collection()
    if collection is None:
        st.warning("MongoDB is not configured, so availability can't be saved.")
        return
    saved = get_availability(collection, _doctor().get("email"))
    if saved is None:
        st.info("You haven't set your availability yet, so patients can't book appointments with you.")
    editor = st.session_state.get(EDITOR_KEY) or _init_editor(saved)

    settings = st.columns(3)
    tz_options = timezone_options()
    timezone_name = settings[0].selectbox("Timezone", options=tz_options, key=_key(editor, "timezone"))
    slot_minutes = settings[1].selectbox(
        "Appointment duration", options=SLOT_DURATIONS, format_func=lambda value: f"{value} minutes",
        key=_key(editor, "slot"),
    )
    break_minutes = settings[2].number_input(
        "Break between appointments (minutes)", min_value=0, max_value=MAX_BREAK_MINUTES, step=5,
        key=_key(editor, "break"),
    )

    st.subheader("Working days and hours")
    st.caption("Add more than one interval to a day for split shifts, e.g. 09:00-12:00 and 13:00-17:00.")
    weekly = {}
    columns = st.columns(2)
    for day in range(7):
        with columns[day % 2]:
            weekly[str(day)] = _render_day(editor, day)

    _render_blocked(editor)

    st.divider()
    save_col, reset_col, _ = st.columns([1, 1, 3])
    if save_col.button("Save availability", type="primary", key=_key(editor, "save")):
        errors = save_availability(collection, _doctor(), {
            "timezone": timezone_name,
            "slot_minutes": slot_minutes,
            "break_minutes": int(break_minutes),
            "weekly": weekly,
            "blocked": editor["blocked"],
        })
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state.pop(EDITOR_KEY, None)
            st.session_state["availability_flash"] = "Availability saved. Existing appointments are not affected."
            st.rerun()
    if reset_col.button("Discard changes", key=_key(editor, "reset")):
        st.session_state.pop(EDITOR_KEY, None)
        st.rerun()

    if saved is not None:
        st.divider()
        _render_preview(saved)
