import streamlit as st

from app_pages.dashboard_page import get_user_role, render as render_dashboard_page
from app_pages.doctor_navigation import doctor_pages
from app_pages.practitioner_page import (
    get_tab_label as get_practitioner_tab_label,
    render as render_practitioner_page,
    render_practitioner_notifications,
)
from app_pages.prediction_page import render as render_prediction_page
from app_pages.registration_page import render_auth_gate

PRACTITIONER_PAGE = "Primary Health Practitioner"
PAGE_OPTIONS = ["Dashboard", "Disease Prediction", PRACTITIONER_PAGE]


def main() -> None:
    """App-level controller: picks the pages available to the current user and runs the selected one."""
    st.set_page_config(page_title="DeltaAI Bio Explorer", layout="wide")

    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if st.session_state.get("authenticated_user") is None:
        pages = [st.Page(render_auth_gate, title="Sign in", url_path="sign-in", default=True)]
    elif get_user_role(st.session_state.authenticated_user) == "Doctor":
        # Doctors get separate pages: dashboard -> patient overview -> review analysis.
        pages = list(doctor_pages().values())
    else:
        pages = [st.Page(render_patient_app, title="DeltaAI Bio Explorer", url_path="home", default=True)]

    st.navigation(pages, position="hidden").run()


def render_patient_app() -> None:
    """Patient workspace: top navigation across the patient pages."""
    if st.session_state.get("active_page") not in PAGE_OPTIONS:
        st.session_state.active_page = PAGE_OPTIONS[0]

    with st.sidebar:
        st.write(f"Signed in as: {st.session_state.authenticated_user.get('email', 'User')}")
        if st.button("Logout"):
            st.session_state.pop("authenticated_user", None)
            st.session_state.pop("active_page", None)
            st.rerun()

    render_practitioner_notifications()

    # The PHP tab label changes once the patient has a practitioner, so keep a
    # stable option value and only vary what is displayed.
    practitioner_label = get_practitioner_tab_label()
    selected_page = st.segmented_control(
        "Navigation",
        options=PAGE_OPTIONS,
        format_func=lambda page: practitioner_label if page == PRACTITIONER_PAGE else page,
        key="active_page",
        label_visibility="collapsed",
    )
    if selected_page is None:
        selected_page = PAGE_OPTIONS[0]

    if selected_page == "Disease Prediction":
        render_prediction_page()
    elif selected_page == PRACTITIONER_PAGE:
        render_practitioner_page()
    else:
        render_dashboard_page()


if __name__ == "__main__":
    main()
