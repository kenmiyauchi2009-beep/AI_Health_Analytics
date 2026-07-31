from __future__ import annotations

import pandas as pd
import streamlit as st


def render_page_header() -> None:
    st.title("Streamlit Bio Explorer Dashboard v1")


def render_uploader():
    return st.file_uploader("Upload your CSV to start", type=["csv"])


def render_dataset_overview(df: pd.DataFrame) -> None:
    st.subheader("Dataset Overview")
    st.dataframe(df.head(10), use_container_width=True)
    c1, c2 = st.columns(2)
    c1.metric("Rows", len(df))
    c2.metric("Columns", len(df.columns))


def render_guardrails(numeric_cols: list[str], categorical_cols: list[str]) -> None:
    if not numeric_cols:
        st.warning("No numeric columns detected. Numeric plots are disabled.")
    if not categorical_cols:
        st.warning("No categorical columns detected. Grouped plots and filters are disabled.")


def render_sidebar_controls(
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> tuple[str | None, str | None, str | None]:
    st.sidebar.header("Controls")

    selected_cat_col = None
    selected_x_col = None
    selected_y_col = None

    if categorical_cols:
        selected_cat_col = st.sidebar.selectbox(
            "Categorical column (group/filter)",
            options=categorical_cols,
        )

    if numeric_cols:
        selected_x_col = st.sidebar.selectbox(
            "X-axis numeric column (scatter)",
            options=numeric_cols,
            index=0,
        )
        selected_y_col = st.sidebar.selectbox(
            "Y-axis numeric column (scatter)",
            options=numeric_cols,
            index=1 if len(numeric_cols) > 1 else 0,
        )

    return selected_cat_col, selected_x_col, selected_y_col


def render_filter_multiselect(df: pd.DataFrame, selected_cat_col: str | None) -> list:
    if not selected_cat_col or selected_cat_col not in df.columns:
        return []

    cat_values = df[selected_cat_col].dropna().unique().tolist()
    cat_values = sorted(cat_values, key=lambda value: str(value))
    return st.sidebar.multiselect(
        f"Filter values in {selected_cat_col}",
        options=cat_values,
        default=cat_values,
    )


def render_summary_metrics(filtered_df: pd.DataFrame) -> None:
    st.subheader("Summary Metrics (After Filtering)")
    st.metric("Total rows after filtering", len(filtered_df))
