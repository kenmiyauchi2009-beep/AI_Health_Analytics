"""Charts for the patient Data explorer, drawn with Altair in the app palette.

Builders (``build_*``) return Altair charts and can be tested without Streamlit; ``render_*`` place them in
chart cards. Altair renders in the browser, so there is no image-size limit to guard against.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data_service import compute_correlation_matrix
from ui.components import chart_container

PRIMARY = "#2563EB"
NEGATIVE = "#BE123C"  # warm pole for negative correlations; the diverging midpoint is neutral slate
NEUTRAL_MID = "#F1F5F9"
TEXT = "#0F172A"
TEXT_MUTED = "#64748B"
AXIS = "#CBD5E1"
GRID = "#E2E8F0"
SURFACE = "#FFFFFF"

VERTICAL_BAR_LIMIT = 12  # more categories than this switch to horizontal bars so labels stay readable
BAR_ROW_PX = 24
MAX_CHART_HEIGHT = 720
HEATMAP_LABEL_LIMIT = 14  # annotate cells with values up to this many columns
HEATMAP_CELL_PX = 44


def _style(chart: alt.Chart) -> alt.Chart:
    """Recessive axes and gridlines, no outer frame."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure(background="transparent")
        .configure_axis(
            gridColor=GRID,
            domainColor=AXIS,
            tickColor=AXIS,
            labelColor=TEXT_MUTED,
            titleColor=TEXT,
            titleFontWeight=500,
            labelFontSize=12,
            titleFontSize=12,
            labelLimit=180,
        )
        .configure_legend(labelColor=TEXT_MUTED, titleColor=TEXT, titleFontWeight=500)
    )


def _show(chart: alt.Chart) -> None:
    st.altair_chart(chart, width="stretch")


def build_count_chart(filtered_df: pd.DataFrame, column: str) -> alt.Chart | None:
    """Bar chart of how often each value of ``column`` appears (missing values included)."""
    count_data = filtered_df[column].value_counts(dropna=False)
    if len(count_data) == 0:
        return None

    data = pd.DataFrame({"value": count_data.index.astype(str), "count": count_data.values})
    tooltip = [alt.Tooltip("value:N", title=column), alt.Tooltip("count:Q", title="Count")]

    if len(data) <= VERTICAL_BAR_LIMIT:
        long_labels = data["value"].str.len().max() > 12
        chart = alt.Chart(data).mark_bar(color=PRIMARY, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("value:N", sort="-y", title=column, axis=alt.Axis(labelAngle=-30 if long_labels else 0)),
            y=alt.Y("count:Q", title="Count", axis=alt.Axis(tickMinStep=1)),
            tooltip=tooltip,
        ).properties(height=320)
    else:
        chart = alt.Chart(data).mark_bar(color=PRIMARY, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y("value:N", sort="-x", title=column),
            x=alt.X("count:Q", title="Count", axis=alt.Axis(tickMinStep=1)),
            tooltip=tooltip,
        ).properties(height=min(MAX_CHART_HEIGHT, max(320, BAR_ROW_PX * len(data))))
    return _style(chart)


def build_scatter_chart(filtered_df: pd.DataFrame, x_col: str, y_col: str) -> alt.Chart | None:
    """Scatter of two numeric columns, rows with a missing value left out."""
    scatter_df = filtered_df[[x_col, y_col]].dropna()
    if len(scatter_df) == 0:
        return None
    if x_col == y_col:
        data = pd.DataFrame({"x": scatter_df.iloc[:, 0].values, "y": scatter_df.iloc[:, 0].values})
    else:
        data = scatter_df.rename(columns={x_col: "x", y_col: "y"})

    chart = alt.Chart(data).mark_circle(
        size=64, color=PRIMARY, opacity=0.7, stroke=SURFACE, strokeWidth=1
    ).encode(
        x=alt.X("x:Q", title=x_col, scale=alt.Scale(zero=False)),
        y=alt.Y("y:Q", title=y_col, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("x:Q", title=x_col), alt.Tooltip("y:Q", title=y_col)],
    ).properties(height=360)
    return _style(chart)


def build_correlation_chart(corr_matrix: pd.DataFrame) -> alt.Chart:
    """Heatmap of Pearson correlations, blue for positive and rose for negative, neutral at zero."""
    columns = [str(column) for column in corr_matrix.columns]
    matrix = corr_matrix.copy()
    matrix.index = columns
    matrix.columns = columns
    data = (
        matrix.rename_axis("row").reset_index()
        .melt(id_vars="row", var_name="column", value_name="r")
        .dropna(subset=["r"])
    )
    data["r"] = data["r"].astype(float).round(2)

    base = alt.Chart(data).encode(
        x=alt.X("column:N", sort=columns, title=None, axis=alt.Axis(labelAngle=-45 if len(columns) > 6 else 0)),
        y=alt.Y("row:N", sort=columns, title=None),
    )
    cells = base.mark_rect(stroke=SURFACE, strokeWidth=2).encode(
        color=alt.Color(
            "r:Q",
            title="Correlation",
            scale=alt.Scale(domain=[-1, 0, 1], range=[NEGATIVE, NEUTRAL_MID, PRIMARY]),
            legend=alt.Legend(orient="right", gradientLength=160),
        ),
        tooltip=[
            alt.Tooltip("row:N", title="Column"),
            alt.Tooltip("column:N", title="Compared with"),
            alt.Tooltip("r:Q", title="Correlation", format=".2f"),
        ],
    )
    layers = cells
    if len(columns) <= HEATMAP_LABEL_LIMIT:
        labels = base.mark_text(fontSize=11).encode(
            text=alt.Text("r:Q", format=".2f"),
            color=alt.condition("abs(datum.r) >= 0.6", alt.value(SURFACE), alt.value(TEXT)),
        )
        layers = cells + labels
    height = min(MAX_CHART_HEIGHT, max(240, HEATMAP_CELL_PX * len(columns)))
    return _style(layers.properties(height=height))


def render_count_plot(filtered_df: pd.DataFrame, selected_cat_col: str | None) -> None:
    if not selected_cat_col or selected_cat_col not in filtered_df.columns:
        return

    with chart_container(
        f"Count of values in {selected_cat_col}",
        "How often each value appears in the filtered rows.",
        key="explorer-count",
    ):
        chart = build_count_chart(filtered_df, selected_cat_col)
        if chart is None:
            st.info("No rows match your filters. Select more values in Chart settings.", icon=":material/info:")
            return
        _show(chart)


def render_scatter_plot(
    filtered_df: pd.DataFrame,
    selected_x_col: str | None,
    selected_y_col: str | None,
) -> None:
    if not selected_x_col or not selected_y_col:
        return
    if selected_x_col not in filtered_df.columns or selected_y_col not in filtered_df.columns:
        return

    with chart_container(
        f"{selected_x_col} compared with {selected_y_col}",
        "Each dot is one row. Look for trends, clusters and outliers.",
        key="explorer-scatter",
    ):
        chart = build_scatter_chart(filtered_df, selected_x_col, selected_y_col)
        if chart is None:
            st.info(
                "No filtered rows have values in both columns. Choose other columns or select more values.",
                icon=":material/info:",
            )
            return
        _show(chart)


def render_correlation_matrix(
    filtered_df: pd.DataFrame,
    numeric_cols: list[str],
) -> None:
    with chart_container(
        "Correlation matrix",
        "Pearson correlation between numeric columns. Values near 1 or -1 mean a strong positive or negative "
        "linear relationship; values near 0 mean little linear relationship.",
        key="explorer-correlation",
    ):
        corr_matrix = compute_correlation_matrix(filtered_df, numeric_cols)
        if corr_matrix is None:
            st.info(
                "A correlation matrix needs at least 2 numeric columns and 2 rows with data.",
                icon=":material/info:",
            )
            return

        heatmap_tab, table_tab = st.tabs(["Heatmap", "Table"])
        with heatmap_tab:
            _show(build_correlation_chart(corr_matrix))
        with table_tab:
            st.dataframe(corr_matrix.round(2), width="stretch")
