"""Reusable building blocks for every page. Built from Streamlit-native elements; the card look comes
from keyed containers styled once in ui/theme.py.

Conventions
- Keys passed in must be unique on the page; helpers prefix them (``card-``) so the CSS applies.
- Text is sentence case. Buttons start with a verb.
- Status colours are semantic only: green = done/good, orange = waiting, red = problem, blue = scheduled/info,
  gray = closed/neutral, teal (``BADGE_COLOR_TEAL``) = patient-subgroup content.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Callable, Iterable, Sequence

import streamlit as st

from ui.theme import BADGE_COLOR_TEAL

# ---------------------------------------------------------------- statuses

# kind -> status -> (label, badge colour, material icon)
STATUSES: dict[str, dict[str, tuple[str, str, str]]] = {
    "appointment": {
        "pending": ("Pending", "orange", ":material/hourglass_top:"),
        "confirmed": ("Confirmed", "blue", ":material/event_available:"),
        "rejected": ("Rejected", "red", ":material/block:"),
        "expired": ("Expired", "gray", ":material/timer_off:"),
        "cancelled": ("Cancelled", "gray", ":material/event_busy:"),
        "completed": ("Completed", "green", ":material/check_circle:"),
        "no_show": ("No-show", "red", ":material/person_off:"),
    },
    "prescription": {
        "draft": ("Draft", "gray", ":material/edit_note:"),
        "finalized": ("Finalized", "green", ":material/verified:"),
        "voided": ("Voided", "red", ":material/cancel:"),
    },
    "connection": {
        "pending": ("Pending", "orange", ":material/hourglass_top:"),
        "accepted": ("Accepted", "green", ":material/check_circle:"),
        "declined": ("Declined", "red", ":material/block:"),
        "cancelled": ("Cancelled", "gray", ":material/close:"),
        "replaced": ("Ended", "gray", ":material/swap_horiz:"),
    },
    "review": {
        "reviewed": ("Reviewed", "green", ":material/task_alt:"),
        "unreviewed": ("Not reviewed", "gray", ":material/pending:"),
    },
}

PROVENANCE = {
    "model": ("Model output", "blue", ":material/model_training:"),
    "subgroup": ("Subgroup analysis", BADGE_COLOR_TEAL, ":material/hub:"),
    "ai": ("AI explanation", "gray", ":material/auto_awesome:"),
}


def status_label(kind: str, status: str | None) -> str:
    return STATUSES.get(kind, {}).get(str(status or ""), (str(status or "").replace("_", " ").capitalize(),))[0]


def status_badge(kind: str, status: str | None) -> None:
    """Coloured badge for a record's status, e.g. status_badge("appointment", "confirmed")."""
    label, color, icon = STATUSES.get(kind, {}).get(
        str(status or ""), (str(status or "Unknown").replace("_", " ").capitalize(), "gray", None)
    )
    st.badge(label, color=color, icon=icon)


def provenance_badge(kind: str) -> None:
    """Says where a result came from: "model", "subgroup" or "ai"."""
    label, color, icon = PROVENANCE[kind]
    st.badge(label, color=color, icon=icon)


# ---------------------------------------------------------------- page structure


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def breadcrumbs(items: Sequence[tuple[str, object | None]]) -> None:
    """Trail like Patients / Pat Lee / Analysis. Each item is (label, st.Page or None for the current page)."""
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        for index, (label, page) in enumerate(items):
            if index:
                st.markdown(":gray[/]", width="content")
            if page is not None:
                st.page_link(page, label=label, width="content")
            else:
                st.markdown(f":gray[{label}]", width="content")


def page_header(
    title: str,
    subtitle: str | None = None,
    *,
    breadcrumb: Sequence[tuple[str, object | None]] | None = None,
):
    """Title, one-line purpose and an actions slot on the right. Returns the actions container.

    Usage: ``actions = page_header("Appointments", "Requests and upcoming visits")``,
    then ``actions.button("Book appointment", type="primary")``.
    """
    if breadcrumb:
        breadcrumbs(breadcrumb)
    text_col, actions_col = st.columns([1, 1], vertical_alignment="bottom")
    with text_col:
        st.title(title, anchor=False)
        if subtitle:
            st.markdown(f":gray[{subtitle}]")
    actions = actions_col.container(horizontal=True, horizontal_alignment="right", gap="small")
    return actions


def section_header(title: str, description: str | None = None, *, badge: str | None = None):
    """Section title with optional provenance badge ("model", "subgroup", "ai") and description.

    Returns a right-aligned container for a section-level action.
    """
    text_col, action_col = st.columns([3, 1], vertical_alignment="bottom")
    with text_col:
        if badge:
            provenance_badge(badge)
        st.subheader(title, anchor=False)
        if description:
            st.markdown(f":gray[{description}]")
    return action_col.container(horizontal=True, horizontal_alignment="right")


# ---------------------------------------------------------------- cards


def card(key: str, *, raised: bool = False, lane: str | None = None):
    """A white card surface. ``lane`` ("model", "subgroup", "ai") adds the provenance edge.

    Returns an ``st.container`` to use as a context manager.
    """
    prefix = "card-raised-" if raised else "card-"
    if lane:
        prefix = f"card-lane-{lane}-"
    return st.container(key=f"{prefix}{_slug(key)}")


def field_grid(fields: Iterable[tuple[str, object]], columns: int = 3) -> None:
    """Label-over-value pairs in a grid. Empty values show as an em dash."""
    fields = list(fields)
    if not fields:
        return
    cols = st.columns(min(columns, len(fields)))
    for index, (label, value) in enumerate(fields):
        with cols[index % len(cols)]:
            shown = value if value not in (None, "") else "—"
            st.markdown(f":gray[{label}]  \n{shown}")


def entity_card(
    key: str,
    title: str,
    *,
    subtitle: str | None = None,
    status: tuple[str, str | None] | None = None,
    fields: Iterable[tuple[str, object]] = (),
    columns: int = 3,
):
    """Card for one record (appointment, patient, prescription): title, status badge, details.

    ``status`` is (kind, value) for ``status_badge``. Returns the card container so callers can add
    notices and actions below the details.
    """
    container = card(key)
    with container:
        with st.container(horizontal=True, vertical_alignment="top", gap="small"):
            st.markdown(f"**{title}**" + (f"  \n:gray[{subtitle}]" if subtitle else ""), width="stretch")
            if status:
                status_badge(*status)
        field_grid(fields, columns)
    return container


def metric_card(label: str, value, *, help: str | None = None, key: str | None = None) -> None:
    with card(f"metric-{key or label}"):
        st.metric(label, value, help=help)


def metric_row(metrics: Sequence[tuple[str, object]] | Sequence[tuple[str, object, str]], *, key: str = "m") -> None:
    """A row of metric cards. Each item is (label, value) or (label, value, help)."""
    cols = st.columns(len(metrics))
    for index, (col, metric) in enumerate(zip(cols, metrics)):
        with col:
            metric_card(metric[0], metric[1], help=metric[2] if len(metric) > 2 else None, key=f"{key}-{index}")


@contextmanager
def chart_container(title: str, caption: str | None = None, *, key: str):
    """Card with a title for a chart or table."""
    with card(f"chart-{key}"):
        st.markdown(f"**{title}**")
        if caption:
            st.caption(caption)
        yield


@contextmanager
def form_section(title: str, description: str | None = None, *, key: str):
    """A titled card grouping related form fields."""
    with card(f"form-{key}"):
        st.markdown(f"**{title}**")
        if description:
            st.caption(description)
        yield


# ---------------------------------------------------------------- feedback


def empty_state(
    title: str,
    message: str | None = None,
    *,
    icon: str = ":material/inbox:",
    key: str,
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
    page=None,
) -> None:
    """Centred message for an empty list, with an optional next step (a button callback or a page link)."""
    with card(f"empty-{key}"):
        st.markdown(f"### {icon}", text_alignment="center")
        st.markdown(f"**{title}**", text_alignment="center")
        if message:
            st.markdown(f":gray[{message}]", text_alignment="center")
        if action_label and (on_action or page):
            with st.container(horizontal=True, horizontal_alignment="center"):
                if page is not None:
                    st.page_link(page, label=action_label, icon=":material/arrow_forward:")
                else:
                    st.button(action_label, key=f"empty-action-{key}", on_click=on_action, type="primary")


def error_message(message: str, recovery: str | None = None) -> None:
    """Error that says what happened and how to fix it."""
    st.error(f"{message} {recovery or ''}".strip(), icon=":material/error:")


def show_errors(errors: Iterable[str]) -> bool:
    """Show each validation error; returns True if there were any."""
    errors = list(errors)
    for error in errors:
        st.error(error, icon=":material/error:")
    return bool(errors)


@contextmanager
def loading(message: str = "Loading…"):
    with st.spinner(message):
        yield


def flash(message: str, *, kind: str = "success", key: str = "flash") -> None:
    """Queue a message to show after the next rerun (e.g. after saving)."""
    st.session_state[f"_flash_{key}"] = (kind, message)


def show_flash(key: str = "flash") -> None:
    queued = st.session_state.pop(f"_flash_{key}", None)
    if queued:
        kind, message = queued
        icon = {"success": ":material/check_circle:", "error": ":material/error:",
                "warning": ":material/warning:"}.get(kind, ":material/info:")
        getattr(st, kind)(message, icon=icon)


def confirmation_dialog(
    key: str,
    *,
    title: str,
    message: str,
    confirm_label: str,
    on_confirm: Callable[[str], list[str] | None],
    reason_label: str | None = None,
    reason_required: bool = False,
    danger: bool = False,
    cancel_label: str = "Cancel",
) -> None:
    """Confirmation modal that stays open across reruns until confirmed, cancelled or dismissed.

    Open it with ``open_dialog(key)``; call this every run after that (it does nothing while closed).
    ``on_confirm(reason)`` returns a list of errors, which are shown in the dialog; an empty list closes it.
    """
    flag = f"_dialog_{key}"
    if not st.session_state.get(flag):
        return

    def close() -> None:
        st.session_state.pop(flag, None)

    @st.dialog(title, on_dismiss=close)
    def _dialog() -> None:
        st.markdown(message)
        reason = ""
        if reason_label:
            reason = st.text_area(reason_label, key=f"{flag}_reason")
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button(confirm_label, type="primary", key=f"{flag}_confirm", width="stretch",
                              icon=":material/warning:" if danger else None):
            if reason_required and not reason.strip():
                st.error(f"{reason_label} is required.", icon=":material/error:")
                return
            errors = on_confirm(reason.strip()) or []
            if show_errors(errors):
                return
            close()
            st.session_state.pop(f"{flag}_reason", None)
            st.rerun()
        if cancel_col.button(cancel_label, key=f"{flag}_cancel", width="stretch"):
            close()
            st.rerun()

    _dialog()


def open_dialog(key: str) -> None:
    st.session_state[f"_dialog_{key}"] = True


# ---------------------------------------------------------------- lists and tables


def search_and_filter(
    key: str,
    *,
    placeholder: str = "Search",
    filters: Sequence[str] = (),
    default_filters: Sequence[str] | None = None,
    format_filter: Callable[[str], str] = str,
) -> tuple[str, list[str]]:
    """Search box plus optional multi-select filter chips. Returns (lowercase query, selected filters)."""
    search_col, filter_col = st.columns([2, 3], vertical_alignment="bottom")
    query = search_col.text_input("Search", placeholder=placeholder, key=f"{key}-search",
                                  label_visibility="collapsed", icon=":material/search:")
    selected: list[str] = []
    if filters:
        selected = filter_col.pills(
            "Filter", options=list(filters), selection_mode="multi",
            default=list(default_filters if default_filters is not None else filters),
            format_func=format_filter, key=f"{key}-filter", label_visibility="collapsed",
        ) or []
    return query.strip().lower(), list(selected)


def data_table(rows: list[dict], *, column_config: dict | None = None, height: str | int = "auto") -> None:
    """Consistent read-only table."""
    st.dataframe(rows, hide_index=True, width="stretch", column_config=column_config, height=height)


# ---------------------------------------------------------------- chat


AVATARS = {"user": ":material/person:", "assistant": ":material/auto_awesome:"}


def chat_message(role: str, content: str) -> None:
    with st.chat_message(role, avatar=AVATARS.get(role)):
        st.markdown(content)
