import streamlit as st

from dashboard.data_service import apply_categorical_filter, detect_columns, load_uploaded_csv
from dashboard.plots_view import render_boxplot, render_count_plot, render_scatter_plot
from dashboard.ui_view import (
    render_dataset_overview,
    render_filter_multiselect,
    render_guardrails,
    render_page_header,
    render_sidebar_controls,
    render_summary_metrics,
    render_uploader,
)


def render() -> None:
    """Render the dashboard page."""
    render_page_header()
    uploaded_file = render_uploader()

    df, load_error = load_uploaded_csv(uploaded_file)
    if load_error:
        st.error(f"Could not read uploaded CSV: {load_error}")
        st.stop()

    if df is None:
        st.info("Upload a CSV file to begin exploring your data.")
        st.stop()

    st.success("Dataset uploaded successfully.")
    render_dataset_overview(df)

    numeric_cols, categorical_cols = detect_columns(df)
    render_guardrails(numeric_cols, categorical_cols)

    selected_cat_col, selected_num_col, selected_x_col, selected_y_col = render_sidebar_controls(
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

    render_summary_metrics(filtered_df, selected_num_col)

    st.subheader("Visualizations")
    render_count_plot(filtered_df, selected_cat_col)
    render_boxplot(filtered_df, selected_cat_col, selected_num_col)
    render_scatter_plot(filtered_df, selected_x_col, selected_y_col)
