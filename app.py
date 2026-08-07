import streamlit as st

from app_pages.dashboard_page import render as render_dashboard_page
from app_pages.prediction_page import render as render_prediction_page

PAGE_OPTIONS = ["Dashboard", "Disease Prediction"]


def main() -> None:
    """App-level controller: orchestrates navigation across pages."""
    st.set_page_config(page_title="DeltaAI Bio Explorer", layout="wide")

    if "active_page" not in st.session_state:
        st.session_state.active_page = PAGE_OPTIONS[0]

    # Exclusive top navigation (avoids st.tabs running both pages on every load).
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
