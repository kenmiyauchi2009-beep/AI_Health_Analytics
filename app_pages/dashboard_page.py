import streamlit as st

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

    role = str(user.get("role") or user.get("user_type") or "").strip()
    if role:
        return role.capitalize()

    if user.get("speciality") or user.get("medical_license_number") or user.get("clinic_or_hospital"):
        return "Doctor"

    return "Patient"


def _get_doctor_context() -> tuple[str, str, list[dict], list[dict]]:
    """Return the doctor greeting text and patient data for the doctor workspace."""
    user = st.session_state.get("authenticated_user") or {}
    first_name = str(user.get("first_name") or "Doctor").strip()
    last_name = str(user.get("last_name") or "").strip()
    doctor_name = f"{first_name} {last_name}".strip() or "Doctor"
    speciality = str(user.get("speciality") or "General Medicine").strip() or "General Medicine"

    if "doctor_patient_requests" not in st.session_state:
        st.session_state.doctor_patient_requests = [
            {
                "name": "John Smith",
                "age": 34,
                "profile": "Diabetes",
                "requested_time": "Today, 09:40 AM",
            },
            {
                "name": "Emma Johnson",
                "age": 28,
                "profile": "Hypertension",
                "requested_time": "Yesterday, 04:15 PM",
            },
        ]

    if "doctor_my_patients" not in st.session_state:
        st.session_state.doctor_my_patients = [
            {
                "name": "John Smith",
                "age": 34,
                "last_analysis": "Blood pressure stable; follow-up due this week.",
            }
        ]

    return doctor_name, speciality, st.session_state.doctor_patient_requests, st.session_state.doctor_my_patients


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
                st.write(f"**Age:** {request['age']}")
                st.write(f"**Patient Profile:** {request['profile']}")
                st.write(f"**Requested Time:** {request['requested_time']}")

                request_actions = st.columns([1, 1])
                with request_actions[0]:
                    if st.button("Accept", key=f"accept_request_{index}"):
                        st.session_state.doctor_my_patients.append(
                            {
                                "name": request["name"],
                                "age": request["age"],
                                "last_analysis": "New connection accepted; no analysis yet.",
                            }
                        )
                        st.session_state.doctor_patient_requests.pop(index)
                        st.rerun()
                with request_actions[1]:
                    if st.button("Decline", key=f"decline_request_{index}"):
                        st.session_state.doctor_patient_requests.pop(index)
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
        return

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


def render() -> None:
    """Render the dashboard page, with a doctor-specific workspace for doctor accounts."""
    user = st.session_state.get("authenticated_user") or {}
    if get_user_role(user).lower() == "doctor":
        render_doctor_dashboard()
        return

    render_patient_dashboard()
