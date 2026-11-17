"""Doctor workspace pages (Dashboard, My patients, Patient requests) and the patient Data explorer."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app_pages.appointment_service import format_slot, list_for_doctor
from app_pages.doctor_navigation import (
    APPOINTMENT_REQUESTS,
    APPOINTMENTS,
    AVAILABILITY,
    MY_PATIENTS,
    PATIENT_REQUESTS,
    REVIEW_ANALYSIS,
    REVIEWING_ANALYSIS_KEY,
    VIEWING_PATIENT_KEY,
    go_to,
    page,
)
from app_pages.patient_overview_page import open_patient_overview
from app_pages.patient_overview_service import calculate_age, get_patient_analyses, review_analysis
from app_pages.practitioner_service import REQUEST_TYPE_CHANGE, respond_to_practitioner_request
from app_pages.registration_page import (
    get_accepted_doctor_requests,
    get_analyses_collection,
    get_appointments_collection,
    get_pending_doctor_requests,
    get_requests_collection,
    get_users_collection,
)
from dashboard.data_service import apply_categorical_filter, detect_columns, load_uploaded_csv
from dashboard.plots_view import (
    render_count_plot,
    render_correlation_matrix,
    render_scatter_plot,
)
from dashboard.ui_view import (
    render_chart_settings,
    render_dataset_overview,
    render_guardrails,
    render_page_header,
    render_summary_metrics,
    render_uploader,
)
from ui.components import (
    card,
    confirmation_dialog,
    empty_state,
    entity_card,
    error_message,
    flash,
    metric_row,
    open_dialog,
    page_header,
    search_and_filter,
    section_header,
    show_flash,
)

DASHBOARD_LIST_LIMIT = 5


def get_user_role(user: dict | None) -> str:
    """Return the normalized role for the current user, with a fallback for legacy doctor records."""
    if not isinstance(user, dict):
        return "Patient"

    role_value = str(user.get("role") or user.get("user_type") or "").strip()
    normalized_role = role_value.lower()

    if normalized_role in {"doctor", "dr", "physician", "clinician", "medical_doctor"}:
        return "Doctor"
    if normalized_role in {"patient", "user", "member"}:
        return "Patient"
    if role_value:
        return role_value.capitalize()

    if user.get("speciality") or user.get("medical_license_number") or user.get("clinic_or_hospital"):
        return "Doctor"

    return "Patient"


# ---------------------------------------------------------------- formatting


def _md(text) -> str:
    """Escape user-entered text so it renders literally inside st.markdown."""
    value = str(text or "")
    for char in "\\`*_[]<>#|~$":
        value = value.replace(char, f"\\{char}")
    return value


def _format_date(value) -> str:
    return value.strftime("%b %d, %Y") if hasattr(value, "strftime") else "Unknown date"


def _format_utc(value) -> str | None:
    return value.strftime("%b %d, %Y %I:%M %p UTC") if hasattr(value, "strftime") else None


def _summarize_analysis(analysis: dict) -> str:
    """Prediction and model confidence for one saved analysis."""
    return (
        f"{analysis.get('top_disease') or 'Unknown'} "
        f"({float(analysis.get('top_probability') or 0):.0%} model confidence)"
    )


def _greeting(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


# ---------------------------------------------------------------- data


def _current_doctor() -> tuple[dict, str]:
    user = st.session_state.get("authenticated_user") or {}
    return user, str(user.get("email") or "").strip().lower()


def _load_patient_requests(doctor_email: str) -> list[dict]:
    """Pending Primary Health Practitioner requests addressed to this doctor, shaped for display."""
    display_requests = []
    for request in get_pending_doctor_requests(doctor_email):
        display_requests.append(
            {
                "_id": request.get("_id"),
                "name": request.get("patient_name") or request.get("patient_email") or "Patient",
                "email": request.get("patient_email") or "",
                "note": request.get("note") or "",
                "requested_time": _format_utc(request.get("created_at")) or "Recently",
                "is_change": request.get("request_type") == REQUEST_TYPE_CHANGE,
            }
        )
    return display_requests


def _load_my_patients(doctor_email: str) -> list[dict]:
    """Accepted patients with age, latest analysis and the analyses still to review."""
    accepted_requests = get_accepted_doctor_requests(doctor_email)
    users_collection = get_users_collection() if accepted_requests else None
    analyses_collection = get_analyses_collection() if accepted_requests else None
    my_patients = []
    for request in accepted_requests:
        patient_email = str(request.get("patient_email") or "").strip().lower()
        patient = users_collection.find_one({"email": patient_email}) if users_collection is not None else None
        age = calculate_age((patient or {}).get("date_of_birth"))
        analyses = get_patient_analyses(analyses_collection, patient_email)
        my_patients.append(
            {
                "name": request.get("patient_name") or patient_email or "Patient",
                "email": patient_email,
                "age": age,
                "latest": analyses[0] if analyses else None,
                "unreviewed": [analysis for analysis in analyses if not analysis.get("reviewed")],
            }
        )
    return my_patients


# ---------------------------------------------------------------- actions


def _respond_to_request(request: dict, *, accept: bool) -> bool:
    """Accept or decline a patient's Primary Health Practitioner request. Returns False if it was no longer pending."""
    user = st.session_state.get("authenticated_user") or {}
    return respond_to_practitioner_request(
        get_users_collection(),
        get_requests_collection(),
        request["_id"],
        user.get("email"),
        accept=accept,
    )


def _accept_request(request: dict) -> None:
    if _respond_to_request(request, accept=True):
        flash(f"{request['name']} is now your patient.")
    else:
        flash("This request is no longer waiting for a reply. The patient may have withdrawn it.", kind="warning")
    st.rerun()


def _decline_dialog(request: dict) -> None:
    def decline(_reason: str) -> list[str]:
        if not _respond_to_request(request, accept=False):
            return ["This request is no longer waiting for a reply. Close this dialog to see the latest requests."]
        flash(f"You declined the request from {request['name']}.")
        return []

    confirmation_dialog(
        f"decline-request-{request['_id']}",
        title="Decline this request?",
        message=f"{_md(request['name'])} will be told you declined. They can then ask another doctor.",
        confirm_label="Decline request",
        on_confirm=decline,
        danger=True,
    )


def _open_analysis_review(patient_email: str, analysis: dict) -> None:
    """Same as Review analysis on the patient overview: mark it reviewed and open the review page."""
    user = st.session_state.get("authenticated_user") or {}
    review_analysis(get_analyses_collection(), analysis["_id"], patient_email, user.get("email"))
    st.session_state[VIEWING_PATIENT_KEY] = patient_email
    st.session_state[REVIEWING_ANALYSIS_KEY] = str(analysis["_id"])
    go_to(REVIEW_ANALYSIS)


# ---------------------------------------------------------------- doctor dashboard


def _render_upcoming(upcoming: list[dict]) -> None:
    action = section_header("Upcoming appointments", "Your next confirmed visits")
    action.page_link(page(APPOINTMENTS), label="View all", icon=":material/calendar_month:")
    if not upcoming:
        empty_state(
            "No upcoming appointments",
            "Confirmed visits appear here. Keep your availability up to date so patients can book.",
            icon=":material/event_available:",
            key="dashboard-upcoming",
            action_label="Set your availability",
            page=page(AVAILABILITY),
        )
        return

    with card("dashboard-upcoming"):
        for index, appointment in enumerate(upcoming[:DASHBOARD_LIST_LIMIT]):
            if index:
                st.divider()
            st.markdown(
                f"**{_md(appointment.get('patient_name') or appointment.get('patient_email') or 'Patient')}**  \n"
                f":gray[{format_slot(appointment['start_at'], appointment.get('timezone') or 'UTC')}]"
            )
            if appointment.get("reason"):
                st.caption(_md(appointment["reason"]))
        if len(upcoming) > DASHBOARD_LIST_LIMIT:
            st.caption(f"{len(upcoming) - DASHBOARD_LIST_LIMIT} more in My appointments.")


def _attention_row(icon: str, text: str, link_key: str, link_label: str) -> None:
    text_col, link_col = st.columns([3, 2], vertical_alignment="center")
    text_col.markdown(f"{icon} {text}")
    with link_col.container(horizontal=True, horizontal_alignment="right"):
        st.page_link(page(link_key), label=link_label, icon=":material/arrow_forward:", width="content")


def _render_needs_attention(appointment_requests: list, patient_requests: list, my_patients: list[dict]) -> None:
    section_header("Needs your attention", "Requests waiting for your reply and analyses to review")

    to_review = sorted(
        ((patient, analysis) for patient in my_patients for analysis in patient["unreviewed"]),
        key=lambda item: item[1].get("created_at") or datetime.min,
        reverse=True,
    )
    if not appointment_requests and not patient_requests and not to_review:
        empty_state(
            "You're all caught up",
            "New requests and analyses from your patients will appear here.",
            icon=":material/task_alt:",
            key="dashboard-attention",
            action_label="View my patients",
            page=page(MY_PATIENTS),
        )
        return

    with card("dashboard-attention"):
        rows = 0
        if appointment_requests:
            _attention_row(
                ":material/inbox:",
                f"{_plural(len(appointment_requests), 'appointment request')} waiting for a reply",
                APPOINTMENT_REQUESTS,
                "Review",
            )
            rows += 1
        if patient_requests:
            if rows:
                st.divider()
            _attention_row(
                ":material/person_add:",
                f"{_plural(len(patient_requests), 'patient')} asking you to be their practitioner",
                PATIENT_REQUESTS,
                "Review",
            )
            rows += 1

        if to_review:
            if rows:
                st.divider()
            st.markdown(f"**Analyses to review** :gray[({len(to_review)})]")
            for patient, analysis in to_review[:DASHBOARD_LIST_LIMIT]:
                text_col, button_col = st.columns([3, 1], vertical_alignment="center")
                text_col.markdown(
                    f"{_md(patient['name'])}  \n"
                    f":gray[{_md(_summarize_analysis(analysis))}, {_format_date(analysis.get('created_at'))}]"
                )
                if button_col.button("Review", key=f"dashboard_review_{analysis['_id']}", width="stretch"):
                    _open_analysis_review(patient["email"], analysis)
            if len(to_review) > DASHBOARD_LIST_LIMIT:
                st.caption(
                    f"{len(to_review) - DASHBOARD_LIST_LIMIT} more. Open a patient from My patients to see all of them."
                )


def render_doctor_dashboard() -> None:
    """Doctor landing page: today's numbers, upcoming visits and what needs a reply."""
    user, doctor_email = _current_doctor()
    last_name = str(user.get("last_name") or "").strip()
    first_name = str(user.get("first_name") or "").strip()
    salutation = f"Dr. {last_name or first_name}" if (last_name or first_name) else "Doctor"
    speciality = str(user.get("speciality") or "General Medicine").strip() or "General Medicine"

    page_header(f"{_greeting()}, {salutation}", speciality)
    show_flash()

    patient_requests = _load_patient_requests(doctor_email)
    my_patients = _load_my_patients(doctor_email)
    appointment_requests, upcoming_appointments, _ = list_for_doctor(get_appointments_collection(), user.get("email"))

    metric_row(
        [
            ("My patients", len(my_patients), "Patients who have you as their Primary Health Practitioner"),
            ("Patient requests", len(patient_requests), "Connection requests waiting for your reply"),
            ("Appointment requests", len(appointment_requests), "Appointment requests waiting for your reply"),
            ("Upcoming appointments", len(upcoming_appointments), "Confirmed visits that haven't happened yet"),
        ],
        key="doctor-dashboard",
    )

    upcoming_col, attention_col = st.columns(2, gap="medium")
    with upcoming_col:
        _render_upcoming(upcoming_appointments)
    with attention_col:
        _render_needs_attention(appointment_requests, patient_requests, my_patients)


# ---------------------------------------------------------------- patient requests


def render_patient_requests_page() -> None:
    """Connection requests from patients who want this doctor as their Primary Health Practitioner."""
    _, doctor_email = _current_doctor()
    patient_requests = _load_patient_requests(doctor_email)

    page_header("Patient requests", "Patients asking you to be their Primary Health Practitioner")
    show_flash()

    if not patient_requests:
        empty_state(
            "No requests waiting",
            "When a patient asks you to be their Primary Health Practitioner, the request appears here.",
            icon=":material/person_add:",
            key="patient-requests",
            action_label="View my patients",
            page=page(MY_PATIENTS),
        )
        return

    for request in patient_requests:
        container = entity_card(
            f"request-{request['_id']}",
            _md(request["name"]),
            subtitle=_md(request["email"]) or None,
            status=("connection", "pending"),
            fields=[
                ("Requested", request["requested_time"]),
                ("Request type", "Switch practitioner" if request["is_change"] else "New patient"),
            ],
            columns=2,
        )
        with container:
            if request["is_change"]:
                st.info(
                    "This patient wants to switch to you from their current Primary Health Practitioner.",
                    icon=":material/swap_horiz:",
                )
            if request["note"]:
                st.markdown(f":gray[Note from the patient]  \n{_md(request['note'])}")
            with st.container(horizontal=True, gap="small"):
                if st.button("Accept request", key=f"accept_request_{request['_id']}", type="primary",
                             icon=":material/check:"):
                    _accept_request(request)
                if st.button("Decline", key=f"decline_request_{request['_id']}"):
                    open_dialog(f"decline-request-{request['_id']}")

    for request in patient_requests:
        _decline_dialog(request)


# ---------------------------------------------------------------- my patients


def _clear_patient_search() -> None:
    st.session_state["my-patients-search"] = ""


def render_my_patients_page() -> None:
    """Patients who have this doctor as their Primary Health Practitioner."""
    _, doctor_email = _current_doctor()
    my_patients = _load_my_patients(doctor_email)

    page_header("My patients", "Patients who have you as their Primary Health Practitioner")
    show_flash()

    if not my_patients:
        empty_state(
            "No patients yet",
            "Patients appear here after you accept their connection request.",
            icon=":material/group:",
            key="my-patients",
            action_label="Review patient requests",
            page=page(PATIENT_REQUESTS),
        )
        return

    query, _ = search_and_filter("my-patients", placeholder="Search by name or email")
    shown = [
        patient for patient in my_patients
        if not query or query in str(patient["name"]).lower() or query in patient["email"]
    ]
    if not shown:
        empty_state(
            "No patients match your search",
            "Check the spelling, or search by email address instead.",
            icon=":material/search_off:",
            key="my-patients-search",
            action_label="Clear search",
            on_action=_clear_patient_search,
        )
        return

    st.caption(_plural(len(shown), "patient"))
    columns = st.columns(2, gap="medium")
    for index, patient in enumerate(shown):
        latest = patient["latest"]
        unreviewed = len(patient["unreviewed"])
        status = None
        if latest is not None:
            status = ("review", "unreviewed" if unreviewed else "reviewed")
        with columns[index % 2]:
            container = entity_card(
                f"patient-{patient['email'] or index}",
                _md(patient["name"]),
                subtitle=_md(patient["email"]) or None,
                status=status,
                fields=[
                    ("Age", patient["age"] if patient["age"] is not None else "Not provided"),
                    ("Analyses to review", unreviewed),
                    ("Latest analysis", _md(_summarize_analysis(latest)) if latest else "No analyses yet"),
                    ("Analysed on", _format_date(latest.get("created_at")) if latest else None),
                ],
                columns=2,
            )
            with container:
                if st.button(
                    "Open profile",
                    key=f"view_patient_{index}",
                    disabled=not patient["email"],
                    icon=":material/person:",
                ):
                    open_patient_overview(patient["email"])


# ---------------------------------------------------------------- patient data explorer


def render_patient_dashboard() -> None:
    """Patient Data explorer: upload a CSV, then filter it and chart its columns."""
    render_page_header()
    uploaded_file = render_uploader()

    df, load_error = load_uploaded_csv(uploaded_file)
    if load_error:
        error_message(
            "We couldn't read that file.",
            f"Check that it is a comma-separated CSV with a header row, then upload it again. Details: {load_error}",
        )
        return

    if df is None:
        empty_state(
            "No data yet",
            "Upload a CSV file above to see an overview of its columns and charts.",
            icon=":material/upload_file:",
            key="data-explorer",
        )
        return

    render_data_explorer(df)


def render_data_explorer(df) -> None:
    """Everything below the uploader for a loaded DataFrame (split out so it can be tested without an upload)."""
    numeric_cols, categorical_cols = detect_columns(df)

    metrics_slot = st.container()
    render_guardrails(numeric_cols, categorical_cols)

    selected_cat_col, selected_values, selected_x_col, selected_y_col = render_chart_settings(
        df,
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
    )
    filtered_df = apply_categorical_filter(df, selected_cat_col, selected_values)

    if selected_cat_col and selected_cat_col not in df.columns:
        st.warning(
            f"The column {selected_cat_col} was not found, so no filter is applied.",
            icon=":material/warning:",
        )

    with metrics_slot:
        render_summary_metrics(df, filtered_df)
    render_dataset_overview(df)

    section_header("Charts", "Based on the rows that match your filters")
    render_count_plot(filtered_df, selected_cat_col)
    render_scatter_plot(filtered_df, selected_x_col, selected_y_col)
    render_correlation_matrix(filtered_df, numeric_cols)


def render() -> None:
    """Render the dashboard page, with a doctor-specific workspace for doctor accounts."""
    user = st.session_state.get("authenticated_user") or {}
    if get_user_role(user) == "Doctor":
        render_doctor_dashboard()
        return

    render_patient_dashboard()
