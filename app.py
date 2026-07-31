import streamlit as st

from app_pages.dashboard_page import render as render_dashboard_page
from app_pages.prediction_page import render as render_prediction_page


def main() -> None:
    """App-level controller: orchestrates navigation across pages."""
    st.set_page_config(page_title="DeltaAI Bio Explorer", layout="wide")

    dashboard_tab, prediction_tab = st.tabs(["Dashboard", "Disease Prediction"])

    with dashboard_tab:
        render_dashboard_page()

    with prediction_tab:
        render_prediction_page()


if __name__ == "__main__":
    main()
