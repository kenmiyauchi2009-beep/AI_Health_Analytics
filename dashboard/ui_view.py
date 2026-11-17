"""Layout pieces for the patient Data explorer. All controls live on the page (the sidebar is navigation only)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import chart_container, data_table, form_section, metric_row, page_header

PREVIEW_ROWS = 10


def render_page_header() -> None:
    page_header("Data explorer", "Upload a CSV file to summarise its columns and chart how they relate")


def render_uploader():
    with form_section(
        "Upload data",
        "Comma-separated file with a header row. It is only used in this session and is not saved.",
        key="explorer-upload",
    ):
        return st.file_uploader("CSV file", type=["csv"], key="explorer_upload")


def render_summary_metrics(df: pd.DataFrame, filtered_df: pd.DataFrame) -> None:
    metric_row(
        [
            ("Rows", len(df), "Rows in the uploaded file"),
            ("Columns", len(df.columns), "Columns in the uploaded file"),
            ("Rows after filters", len(filtered_df), "Rows used by the charts below"),
        ],
        key="explorer",
    )


def render_dataset_overview(df: pd.DataFrame) -> None:
    with chart_container(
        "Data preview",
        f"First {min(PREVIEW_ROWS, len(df))} of {len(df)} rows",
        key="explorer-preview",
    ):
        data_table(df.head(PREVIEW_ROWS))


def render_guardrails(numeric_cols: list[str], categorical_cols: list[str]) -> None:
    if not numeric_cols:
        st.warning(
            "This file has no numeric columns, so the scatter plot and correlation matrix are hidden.",
            icon=":material/info:",
        )
    if not categorical_cols:
        st.warning(
            "This file has no text or category columns, so the count plot and filters are hidden.",
            icon=":material/info:",
        )


def render_chart_settings(
    df: pd.DataFrame,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> tuple[str | None, list, str | None, str | None]:
    """Chart settings card. Returns (categorical column, filter values, x column, y column)."""
    selected_cat_col = None
    selected_values: list = []
    selected_x_col = None
    selected_y_col = None

    if not numeric_cols and not categorical_cols:
        return selected_cat_col, selected_values, selected_x_col, selected_y_col

    with form_section("Chart settings", "Choose the columns the charts use and filter the rows.", key="explorer-settings"):
        group_col, axes_col = st.columns(2, gap="medium")
        with group_col:
            if categorical_cols:
                selected_cat_col = st.selectbox(
                    "Group by column",
                    options=categorical_cols,
                    key="explorer_cat_col",
                    help="Used for the count plot and to filter rows",
                )
                selected_values = render_filter_multiselect(df, selected_cat_col)
        with axes_col:
            if numeric_cols:
                selected_x_col = st.selectbox(
                    "Scatter plot x-axis",
                    options=numeric_cols,
                    index=0,
                    key="explorer_x_col",
                )
                selected_y_col = st.selectbox(
                    "Scatter plot y-axis",
                    options=numeric_cols,
                    index=1 if len(numeric_cols) > 1 else 0,
                    key="explorer_y_col",
                )

    return selected_cat_col, selected_values, selected_x_col, selected_y_col


def render_filter_multiselect(df: pd.DataFrame, selected_cat_col: str | None) -> list:
    if not selected_cat_col or selected_cat_col not in df.columns:
        return []

    cat_values = df[selected_cat_col].dropna().unique().tolist()
    cat_values = sorted(cat_values, key=lambda value: str(value))
    return st.multiselect(
        f"Show values of {selected_cat_col}",
        options=cat_values,
        default=cat_values,
        key=f"explorer_filter_{selected_cat_col}",
        help="Rows with other values are left out of the charts",
    )
