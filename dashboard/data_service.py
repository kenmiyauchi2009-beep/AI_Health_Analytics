from __future__ import annotations

import pandas as pd


def load_uploaded_csv(uploaded_file) -> tuple[pd.DataFrame | None, str | None]:
    """Return dataframe and optional error message."""
    if uploaded_file is None:
        return None, None
    try:
        return pd.read_csv(uploaded_file), None
    except Exception as error:  # pragma: no cover - streamlit upload runtime behavior
        return None, str(error)


def detect_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return numeric columns and categorical columns."""
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(exclude="number").columns.tolist()
    return numeric_cols, categorical_cols


def apply_categorical_filter(
    df: pd.DataFrame,
    selected_cat_col: str | None,
    selected_values: list,
) -> pd.DataFrame:
    """Apply categorical value filtering safely."""
    if not selected_cat_col or selected_cat_col not in df.columns:
        return df.copy()
    if not selected_values:
        return df.iloc[0:0].copy()
    return df[df[selected_cat_col].isin(selected_values)].copy()
