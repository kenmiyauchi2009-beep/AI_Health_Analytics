import streamlit as st

from pages.dashboard_page import render as render_dashboard_page


def main() -> None:
    """App-level controller: orchestrates navigation across pages."""
    pages = {
        "Dashboard": render_dashboard_page,
    }

    if "active_page" not in st.session_state:
        st.session_state.active_page = "Dashboard"

    st.sidebar.header("Navigation")
    st.sidebar.selectbox(
        "Choose page",
        options=list(pages.keys()),
        key="active_page",
    )

    pages[st.session_state.active_page]()


if __name__ == "__main__":
    main()
