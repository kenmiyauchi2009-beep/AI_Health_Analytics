import streamlit as st

from app_pages.dashboard_page import render as render_dashboard_page
from app_pages.prediction_page import render as render_prediction_page
from app_pages.registration_page import render_auth_gate

PAGE_OPTIONS = ["Dashboard", "Disease Prediction"]


def main() -> None:
    """App-level controller: orchestrates navigation across pages."""
    st.set_page_config(page_title="DeltaAI Bio Explorer", layout="wide")

    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if st.session_state.get("authenticated_user") is None:
        render_auth_gate()
        return

    if "active_page" not in st.session_state:
        st.session_state.active_page = PAGE_OPTIONS[0]

    with st.sidebar:
        st.write(f"Signed in as: {st.session_state.authenticated_user.get('email', 'User')}")
        if st.button("Logout"):
            st.session_state.pop("authenticated_user", None)
            st.session_state.pop("active_page", None)
            st.rerun()

    selected_page = st.segmented_control(
        "Navigation",
        options=PAGE_OPTIONS,
        key="active_page",
        label_visibility="collapsed",
    )
    if selected_page is None:
        selected_page = PAGE_OPTIONS[0]

    if selected_page == "Disease Prediction":
        render_prediction_page()
    else:
        render_dashboard_page()


if __name__ == "__main__":
    main()
