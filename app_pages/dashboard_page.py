import streamlit as st

from app_pages.registration_page import (
    create_patient_doctor_request,
    get_accepted_doctor_requests,
    get_pending_doctor_requests,
    get_users_collection,
    normalize_user_record,
    update_doctor_request_status,
)
from dashboard.data_service import apply_categorical_filter, detect_columns, load_uploaded_csv
from dashboard.plots_view import (
    render_count_plot,
    render_correlation_matrix,
    render_scatter_plot,
)
from dashboard.ui_view import (
    render_dataset_overview,
    render_filter_multiselect,
    render_guardrails,
    render_page_header,
    render_sidebar_controls,
    render_summary_metrics,
    render_uploader,
)


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


def _get_doctor_context() -> tuple[str, str, list[dict], list[dict]]:
    """Return the doctor greeting text and live patient data for the doctor workspace."""
    user = st.session_state.get("authenticated_user") or {}
    first_name = str(user.get("first_name") or "Doctor").strip()
    last_name = str(user.get("last_name") or "").strip()
    doctor_name = f"{first_name} {last_name}".strip() or "Doctor"
    speciality = str(user.get("speciality") or "General Medicine").strip() or "General Medicine"

    doctor_email = str(user.get("email") or "").strip().lower()
    pending_requests = get_pending_doctor_requests(doctor_email)
    accepted_requests = get_accepted_doctor_requests(doctor_email)

    display_requests = []
    for request in pending_requests:
        created_at = request.get("created_at")
        requested_time = "Recently"
        if hasattr(created_at, "strftime"):
            requested_time = created_at.strftime("%b %d, %Y %I:%M %p")
        display_requests.append(
            {
                "_id": request.get("_id"),
                "name": request.get("patient_name") or request.get("patient_email") or "Patient",
                "email": request.get("patient_email") or "",
                "note": request.get("note") or "",
                "requested_time": requested_time,
            }
        )

    my_patients = []
    for request in accepted_requests:
        my_patients.append(
            {
                "name": request.get("patient_name") or request.get("patient_email") or "Patient",
                "age": "N/A",
                "last_analysis": "Connection accepted and available for follow-up.",
            }
        )

    return doctor_name, speciality, display_requests, my_patients


def render_doctor_dashboard() -> None:
    """Render the doctor-specific landing workspace and patient management area."""
    doctor_name, speciality, patient_requests, my_patients = _get_doctor_context()

    st.title(f'Welcome Doctor "{doctor_name}"')
    st.subheader(speciality)

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("My Patients", len(my_patients))
    with metric_cols[1]:
        st.metric("Pending Requests", len(patient_requests))
    with metric_cols[2]:
        st.metric("Active Cases", len(my_patients))

    st.markdown("---")
    st.subheader("Patient Requests")
    if not patient_requests:
        st.info("There are no pending patient connection requests at the moment.")
    else:
        for index, request in enumerate(patient_requests):
            with st.container():
                st.write(f"**Patient Name:** {request['name']}")
                if request.get("email"):
                    st.write(f"**Email:** {request['email']}")
                if request.get("note"):
                    st.write(f"**Note:** {request['note']}")
                st.write(f"**Requested Time:** {request['requested_time']}")

                request_actions = st.columns([1, 1])
                with request_actions[0]:
                    if st.button("Accept", key=f"accept_request_{request['_id']}_{index}"):
                        update_doctor_request_status(request["_id"], "accepted")
                        st.rerun()
                with request_actions[1]:
                    if st.button("Decline", key=f"decline_request_{request['_id']}_{index}"):
                        update_doctor_request_status(request["_id"], "declined")
                        st.rerun()

                st.markdown("---")

    st.markdown("---")
    st.subheader("My Patients")
    if not my_patients:
        st.info("No patients assigned yet.")
    else:
        for patient_index, patient in enumerate(my_patients):
            patient_block = st.container()
            with patient_block:
                st.write(f"**{patient['name']}**")
                st.write(f"Age: {patient['age']}")
                st.write(f"Last Analysis: {patient['last_analysis']}")
                if st.button("View Patient", key=f"view_patient_{patient_index}"):
                    st.info(f"Opening profile for {patient['name']}")
                st.markdown("---")


def render_patient_doctor_request_form() -> None:
    """Allow a patient to submit a real doctor access request, persisted to MongoDB."""
    user = st.session_state.get("authenticated_user") or {}
    if get_user_role(user) != "Patient":
        return

    users_collection = get_users_collection()
    if users_collection is None:
        return

    doctors = []
    for record in users_collection.find({}):
        normalized = normalize_user_record(dict(record))
        if normalized and normalized.get("role") == "Doctor":
            doctors.append(normalized)

    if not doctors:
        st.info("No doctors are registered yet. Once a doctor account exists, you can request access here.")
        return

    doctor_options = {}
    for doctor in doctors:
        doctor_name = (
            f"{str(doctor.get('first_name') or '').strip()} {str(doctor.get('last_name') or '').strip()}"
        ).strip() or str(doctor.get("email") or "Doctor")
        doctor_options[doctor_name] = doctor.get("email")

    selected_doctor_name = st.selectbox("Request access from a doctor", list(doctor_options.keys()))
    note = st.text_area("Optional note", placeholder="Tell the doctor why you are requesting a follow-up.")

    if st.button("Send doctor request"):
        doctor_email = doctor_options.get(selected_doctor_name)
        if not doctor_email:
            st.error("Please choose a valid doctor.")
            return

        request = create_patient_doctor_request(user, doctor_email, note)
        if request is None:
            st.warning("You already have a pending request with this doctor, or the request could not be saved.")
            return

        st.success(f"Your request to {selected_doctor_name} was sent successfully.")


def render_patient_dashboard() -> None:
    """Render the normal patient dashboard."""
    render_page_header()
    uploaded_file = render_uploader()

    df, load_error = load_uploaded_csv(uploaded_file)
    if load_error:
        st.error(f"Could not read uploaded CSV: {load_error}")
        return

    if df is None:
        st.info("Upload a CSV file to begin exploring your data.")
    else:
        st.success("Dataset uploaded successfully.")
        render_dataset_overview(df)

        numeric_cols, categorical_cols = detect_columns(df)
        render_guardrails(numeric_cols, categorical_cols)

        selected_cat_col, selected_x_col, selected_y_col = render_sidebar_controls(
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols,
        )

        selected_values = render_filter_multiselect(df, selected_cat_col)
        filtered_df = apply_categorical_filter(df, selected_cat_col, selected_values)

        if selected_cat_col and selected_cat_col not in df.columns:
            st.warning(
                f"Selected categorical column `{selected_cat_col}` was not found. "
                "Skipping categorical filters."
            )

        render_summary_metrics(filtered_df)

        st.subheader("Visualizations")
        render_count_plot(filtered_df, selected_cat_col)
        render_scatter_plot(filtered_df, selected_x_col, selected_y_col)
        render_correlation_matrix(filtered_df, numeric_cols)

    st.markdown("---")
    st.subheader("Doctor Requests")
    render_patient_doctor_request_form()


def render() -> None:
    """Render the dashboard page, with a doctor-specific workspace for doctor accounts."""
    user = st.session_state.get("authenticated_user") or {}
    if get_user_role(user) == "Doctor":
        render_doctor_dashboard()
        return

    render_patient_dashboard()
