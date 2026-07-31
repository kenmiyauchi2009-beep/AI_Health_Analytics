from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from dashboard.data_service import compute_correlation_matrix

# Keep rendered images safely under Pillow's decompression limit.
MAX_FIG_WIDTH = 16.0
MAX_FIG_HEIGHT = 12.0
PLOT_DPI = 100


def _cap_figsize(figsize: tuple[float, float]) -> tuple[float, float]:
    """Clamp figure size so plots stay within a safe pixel budget."""
    width, height = figsize
    return (min(float(width), MAX_FIG_WIDTH), min(float(height), MAX_FIG_HEIGHT))


def _show_plot(fig) -> None:
    """Render a matplotlib figure at a capped DPI."""
    st.pyplot(fig, dpi=PLOT_DPI)


def _get_categorical_label_settings(
    label_count: int,
    label_texts: list[str] | None = None,
) -> dict:
    """Pick figure size and label orientation based on label count and length."""
    max_label_len = (
        max(len(str(text)) for text in label_texts) if label_texts else 0
    )

    if label_count <= 8:
        figsize = (max(8, label_count * 1.1), 4.5)
        return {
            "figsize": _cap_figsize(figsize),
            "horizontal": False,
            "rotation": 0 if max_label_len <= 14 else 30,
            "fontsize": 10,
            "ha": "center",
        }
    if label_count <= 15:
        figsize = (max(10, label_count * 0.9), 5.5)
        return {
            "figsize": _cap_figsize(figsize),
            "horizontal": False,
            "rotation": 45,
            "fontsize": 9,
            "ha": "right",
        }
    if label_count <= 25:
        figsize = (max(12, label_count * 0.75), 6.5)
        return {
            "figsize": _cap_figsize(figsize),
            "horizontal": False,
            "rotation": 75,
            "fontsize": 8,
            "ha": "right",
        }

    figsize = (9, max(6, min(label_count * 0.35, MAX_FIG_HEIGHT)))
    return {
        "figsize": _cap_figsize(figsize),
        "horizontal": True,
        "rotation": 0,
        "fontsize": 8,
        "ha": "center",
    }


def _apply_tick_label_style(ax, axis: str, settings: dict) -> None:
    tick_labels = ax.get_xticklabels() if axis == "x" else ax.get_yticklabels()
    for label in tick_labels:
        label.set_rotation(settings["rotation"])
        label.set_ha(settings["ha"])
        label.set_fontsize(settings["fontsize"])


def _get_correlation_matrix_settings(column_count: int) -> dict:
    """Adjust correlation heatmap size and labels for readability."""
    if column_count <= 8:
        figsize = (max(6, column_count * 0.9), max(5, column_count * 0.85))
        return {
            "figsize": _cap_figsize(figsize),
            "annot": True,
            "annot_kws": {"size": 9},
            "rotation": 0,
            "fontsize": 10,
        }
    if column_count <= 14:
        figsize = (max(8, column_count * 0.75), max(6, column_count * 0.7))
        return {
            "figsize": _cap_figsize(figsize),
            "annot": True,
            "annot_kws": {"size": 7},
            "rotation": 45,
            "fontsize": 9,
        }

    figsize = (
        min(MAX_FIG_WIDTH, max(10, column_count * 0.45)),
        min(MAX_FIG_HEIGHT, max(8, column_count * 0.4)),
    )
    return {
        "figsize": _cap_figsize(figsize),
        "annot": False,
        "annot_kws": {"size": 6},
        "rotation": 90,
        "fontsize": 8,
    }


def render_count_plot(filtered_df: pd.DataFrame, selected_cat_col: str | None) -> None:
    if not selected_cat_col or selected_cat_col not in filtered_df.columns:
        return

    st.markdown(f"### Count Plot: {selected_cat_col}")
    count_data = filtered_df[selected_cat_col].value_counts(dropna=False)

    if len(count_data) > 0:
        labels = count_data.index.astype(str).tolist()
        settings = _get_categorical_label_settings(len(labels), labels)
        fig, ax = plt.subplots(figsize=settings["figsize"])

        if settings["horizontal"]:
            ax.barh(labels, count_data.values)
            ax.set_ylabel(selected_cat_col)
            ax.set_xlabel("Count")
            _apply_tick_label_style(ax, "y", settings)
        else:
            ax.bar(labels, count_data.values)
            ax.set_xlabel(selected_cat_col)
            ax.set_ylabel("Count")
            _apply_tick_label_style(ax, "x", settings)

        ax.set_title(f"Count of values in {selected_cat_col}")
        fig.tight_layout()
        _show_plot(fig)
        st.caption(
            "Interpretation: This chart shows how frequently each category appears "
            "in the filtered data."
        )
        plt.close(fig)
    else:
        st.info("No data available for count plot after filtering.")


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
    fig, ax = plt.subplots(figsize=_cap_figsize((8, 5)))
    scatter_df = filtered_df[[selected_x_col, selected_y_col]].dropna()

    if len(scatter_df) > 0:
        ax.scatter(scatter_df[selected_x_col], scatter_df[selected_y_col], alpha=0.7)
        ax.set_xlabel(selected_x_col)
        ax.set_ylabel(selected_y_col)
        ax.set_title(f"{selected_x_col} vs {selected_y_col}")
        fig.tight_layout()
        _show_plot(fig)
        st.caption(
            "Interpretation: Look for trends, clusters, and outliers to understand "
            "the relationship between these two numeric variables."
        )
        plt.close(fig)
    else:
        st.info("No valid rows for scatter plot after filtering.")
        plt.close(fig)


def render_correlation_matrix(
    filtered_df: pd.DataFrame,
    numeric_cols: list[str],
) -> None:
    st.markdown("### Correlation Matrix")
    corr_matrix = compute_correlation_matrix(filtered_df, numeric_cols)

    if corr_matrix is None:
        st.info(
            "At least 2 numeric columns with enough data are required "
            "for a correlation matrix."
        )
        return

    st.dataframe(corr_matrix.round(2), use_container_width=True)

    settings = _get_correlation_matrix_settings(len(corr_matrix.columns))
    fig, ax = plt.subplots(figsize=settings["figsize"])
    sns.heatmap(
        corr_matrix,
        annot=settings["annot"],
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        annot_kws=settings["annot_kws"],
        ax=ax,
    )
    ax.set_title("Correlation Matrix (Pearson)")
    ax.tick_params(axis="x", rotation=settings["rotation"], labelsize=settings["fontsize"])
    ax.tick_params(axis="y", rotation=0, labelsize=settings["fontsize"])
    fig.tight_layout()
    _show_plot(fig)
    st.caption(
        "Interpretation: Values close to 1 or -1 indicate strong positive or negative "
        "linear relationships. Values near 0 suggest little linear association."
    )
    plt.close(fig)
