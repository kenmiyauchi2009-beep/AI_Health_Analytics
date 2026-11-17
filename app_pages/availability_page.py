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
from app_pages.registration_page import get_appointments_collection, get_availability_collection
from ui.components import error_message, flash, form_section, page_header, show_errors, show_flash

EDITOR_KEY = "availability_editor"
FLASH_KEY = "availability"


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


# ---------------------------------------------------------------- weekly hours


def _render_day(editor: dict, day: int) -> list[dict]:
    day_col, hours_col = st.columns([1, 3], vertical_alignment="top")
    with day_col:
        working = st.toggle(WEEKDAYS[day], key=_key(editor, f"working_{day}"))
    with hours_col:
        if not working:
            st.markdown(":gray[Unavailable]")
            return []
        intervals = []
        rows = editor["days"][day]
        for row in rows:
            start_key, end_key = _key(editor, f"{row}_start"), _key(editor, f"{row}_end")
            st.session_state.setdefault(start_key, editor["times"][row][0])
            st.session_state.setdefault(end_key, editor["times"][row][1])
            with st.container(horizontal=True, gap="small", vertical_alignment="center"):
                start = st.time_input(f"{WEEKDAYS[day]} start", key=start_key, step=timedelta(minutes=15),
                                      label_visibility="collapsed", width=140)
                st.markdown(":gray[to]", width="content")
                end = st.time_input(f"{WEEKDAYS[day]} end", key=end_key, step=timedelta(minutes=15),
                                    label_visibility="collapsed", width=140)
                st.button(
                    "Remove", key=_key(editor, f"{row}_remove"), type="tertiary", icon=":material/close:",
                    disabled=len(rows) == 1, help="Remove these hours",
                    on_click=_remove_interval, args=(editor, day, row),
                )
            editor["times"][row] = (start, end)
            intervals.append({"start": f"{start:%H:%M}", "end": f"{end:%H:%M}"})
        st.button("Add hours", key=_key(editor, f"add_{day}"), type="tertiary", icon=":material/add:",
                  on_click=_add_next_interval, args=(editor, day))
        return intervals


# ---------------------------------------------------------------- blocked periods


def _format_block(block: dict) -> str:
    start, end = parse_local_datetime(block["start"]), parse_local_datetime(block["end"])
    if start.time() == end.time() == time(0, 0) and end > start:
        last_day = (end - timedelta(days=1)).date()
        if last_day == start.date():
            return f"{start:%a, %b %d, %Y}, all day"
        return f"{start:%a, %b %d, %Y} to {last_day:%a, %b %d, %Y}, all day"
    return f"{start:%a, %b %d, %Y, %I:%M %p} to {end:%a, %b %d, %Y, %I:%M %p}"


def _add_block(editor: dict) -> None:
    """Button callback: add the blocked period from the form fields, or record why it can't be added."""
    state = st.session_state
    start_date, end_date = state[_key(editor, "block_start_date")], state[_key(editor, "block_end_date")]
    if state.get(_key(editor, "block_all_day"), True):
        start = datetime.combine(start_date, time(0, 0))
        end = datetime.combine(end_date + timedelta(days=1), time(0, 0))
    else:
        start = datetime.combine(start_date, state.get(_key(editor, "block_start_time")) or time(9, 0))
        end = datetime.combine(end_date, state.get(_key(editor, "block_end_time")) or time(17, 0))
    if start >= end:
        editor["block_error"] = "The blocked period must end after it starts. Choose a later end date or time."
        return
    editor.pop("block_error", None)
    editor["blocked"].append({"start": f"{start:%Y-%m-%dT%H:%M}", "end": f"{end:%Y-%m-%dT%H:%M}",
                              "reason": str(state.get(_key(editor, "block_reason")) or "").strip()})
    state[_key(editor, "block_reason")] = ""


def _render_blocked(editor: dict) -> None:
    if not editor["blocked"]:
        st.markdown(":gray[Nothing blocked.]")
    for index, block in enumerate(list(editor["blocked"])):
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            with st.container(gap=None):
                st.markdown(f":material/event_busy: {_format_block(block)}")
                if block.get("reason"):
                    st.caption(block["reason"])
            st.button("Remove", key=_key(editor, f"block_remove_{index}"), type="tertiary",
                      icon=":material/close:", help="Remove this blocked period",
                      on_click=editor["blocked"].pop, args=(index,))

    with st.expander("Add a blocked period", icon=":material/add:"):
        all_day = st.checkbox("Whole days", value=True, key=_key(editor, "block_all_day"))
        start_col, end_col = st.columns(2)
        start_col.date_input("From", key=_key(editor, "block_start_date"))
        end_col.date_input("To", key=_key(editor, "block_end_date"))
        if not all_day:
            start_col.time_input("From time", value=time(9, 0), key=_key(editor, "block_start_time"))
            end_col.time_input("To time", value=time(17, 0), key=_key(editor, "block_end_time"))
        st.text_input("Reason (optional)", placeholder="For example: vacation", key=_key(editor, "block_reason"))
        if editor.get("block_error"):
            show_errors([editor["block_error"]])
        st.button("Add blocked period", key=_key(editor, "block_add"), icon=":material/add:",
                  on_click=_add_block, args=(editor,))


# ---------------------------------------------------------------- preview


def _render_preview(saved: dict) -> None:
    now = datetime.utcnow()
    tz_name = saved["timezone"]
    chosen = st.date_input("Date", value=local_today(saved, now), key="availability_preview_date")
    busy = doctor_busy(get_appointments_collection(), _doctor().get("email"), now)
    slots = generate_slots(saved, chosen, now, busy)
    if not slots:
        st.markdown(":gray[No bookable times on this date.]")
        return
    st.markdown(" ".join(f":blue-badge[{to_local(start, tz_name).strftime('%I:%M %p').lstrip('0')}]"
                         for start, _ in slots))
    st.caption(f"{len(slots)} bookable times, shown in {tz_name}. Reserved and blocked times are left out.")


# ---------------------------------------------------------------- page


def render_page() -> None:
    """Doctor availability settings."""
    page_header("My availability", "Set the hours patients can book with you.")
    show_flash(FLASH_KEY)

    collection = get_availability_collection()
    if collection is None:
        error_message("Availability can't be loaded or saved because the database isn't configured.",
                      "Check the MongoDB settings and reload the page.")
        return
    saved = get_availability(collection, _doctor().get("email"))
    if saved is None:
        st.info("Patients can't book appointments with you until you save your availability.",
                icon=":material/info:")
    editor = st.session_state.get(EDITOR_KEY) or _init_editor(saved)

    with form_section("General", "Applies to every appointment.", key="availability-general"):
        settings = st.columns(3)
        timezone_name = settings[0].selectbox("Timezone", options=timezone_options(), key=_key(editor, "timezone"))
        slot_minutes = settings[1].selectbox(
            "Appointment duration", options=SLOT_DURATIONS, format_func=lambda value: f"{value} minutes",
            key=_key(editor, "slot"),
        )
        break_minutes = settings[2].number_input(
            "Break between appointments (minutes)", min_value=0, max_value=MAX_BREAK_MINUTES, step=5,
            key=_key(editor, "break"),
        )

    with form_section("Weekly hours",
                      "Times are in your timezone. Add more hours to a day for split shifts, "
                      "for example 9:00 AM to 12:00 PM and 1:00 PM to 5:00 PM.",
                      key="availability-weekly"):
        weekly = {str(day): _render_day(editor, day) for day in range(7)}

    with form_section("Blocked dates and times",
                      "Vacations, holidays or any time you can't see patients. Blocked times are never bookable.",
                      key="availability-blocked"):
        _render_blocked(editor)

    errors_slot = st.container()
    with st.container(horizontal=True, gap="small"):
        if st.button("Save availability", type="primary", key=_key(editor, "save"), icon=":material/save:"):
            errors = save_availability(collection, _doctor(), {
                "timezone": timezone_name,
                "slot_minutes": slot_minutes,
                "break_minutes": int(break_minutes),
                "weekly": weekly,
                "blocked": editor["blocked"],
            })
            if errors:
                with errors_slot:
                    show_errors(errors)
            else:
                st.session_state.pop(EDITOR_KEY, None)
                flash("Availability saved. Existing appointments are not affected.", key=FLASH_KEY)
                st.rerun()
        if st.button("Discard changes", key=_key(editor, "reset"), icon=":material/undo:"):
            st.session_state.pop(EDITOR_KEY, None)
            st.rerun()

    if saved is not None:
        with form_section("Preview bookable times", "What patients can book on a given date, based on your saved "
                          "availability.", key="availability-preview"):
            _render_preview(saved)
