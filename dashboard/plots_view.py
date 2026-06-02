from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def render_count_plot(filtered_df: pd.DataFrame, selected_cat_col: str | None) -> None:
    if not selected_cat_col or selected_cat_col not in filtered_df.columns:
        return

    st.markdown(f"### Count Plot: {selected_cat_col}")
    fig, ax = plt.subplots(figsize=(8, 4))
    count_data = filtered_df[selected_cat_col].value_counts(dropna=False)

    if len(count_data) > 0:
        ax.bar(count_data.index.astype(str), count_data.values)
        ax.set_xlabel(selected_cat_col)
        ax.set_ylabel("Count")
        ax.set_title(f"Count of values in {selected_cat_col}")
        ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig)
        st.caption(
            "Interpretation: This chart shows how frequently each category appears "
            "in the filtered data."
        )
    else:
        st.info("No data available for count plot after filtering.")
    plt.close(fig)


def render_boxplot(
    filtered_df: pd.DataFrame,
    selected_cat_col: str | None,
    selected_num_col: str | None,
) -> None:
    if not selected_cat_col or not selected_num_col:
        return
    if selected_cat_col not in filtered_df.columns or selected_num_col not in filtered_df.columns:
        return

    st.markdown(f"### Boxplot: {selected_num_col} by {selected_cat_col}")
    fig, ax = plt.subplots(figsize=(9, 4))
    plot_df = filtered_df[[selected_cat_col, selected_num_col]].dropna()

    if len(plot_df) > 0:
        grouped_values = []
        labels = []
        for category, group in plot_df.groupby(selected_cat_col):
            values = group[selected_num_col].dropna().values
            if len(values) > 0:
                grouped_values.append(values)
                labels.append(str(category))

        if grouped_values:
            ax.boxplot(grouped_values, tick_labels=labels)
            ax.set_xlabel(selected_cat_col)
            ax.set_ylabel(selected_num_col)
            ax.set_title(f"{selected_num_col} distribution by {selected_cat_col}")
            ax.tick_params(axis="x", rotation=45)
            st.pyplot(fig)
            st.caption(
                "Interpretation: Compare medians, spread, and potential outliers "
                "across categories."
            )
        else:
            st.info("Not enough grouped numeric data for the boxplot.")
    else:
        st.info("No valid rows for boxplot after filtering.")
    plt.close(fig)


def render_scatter_plot(
    filtered_df: pd.DataFrame,
    selected_x_col: str | None,
    selected_y_col: str | None,
) -> None:
    if not selected_x_col or not selected_y_col:
        return
    if selected_x_col not in filtered_df.columns or selected_y_col not in filtered_df.columns:
        return

    st.markdown(f"### Scatter Plot: {selected_x_col} vs {selected_y_col}")
    fig, ax = plt.subplots(figsize=(8, 5))
    scatter_df = filtered_df[[selected_x_col, selected_y_col]].dropna()

    if len(scatter_df) > 0:
        ax.scatter(scatter_df[selected_x_col], scatter_df[selected_y_col], alpha=0.7)
        ax.set_xlabel(selected_x_col)
        ax.set_ylabel(selected_y_col)
        ax.set_title(f"{selected_x_col} vs {selected_y_col}")
        st.pyplot(fig)
        st.caption(
            "Interpretation: Look for trends, clusters, and outliers to understand "
            "the relationship between these two numeric variables."
        )
    else:
        st.info("No valid rows for scatter plot after filtering.")
    plt.close(fig)
