from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from prediction.cluster_controller import ClusterController
from prediction.cluster_result import ClusterAssignmentResult, ClusterComparison, ClusterSummary
from prediction.controller import DiseasePredictionController
from prediction.model_loader import ModelLoader
from prediction.prediction_request import PredictionRequest
from prediction.prediction_result import PredictionResult
from ui.components import card, field_grid, section_header
from ui.theme import BORDER, PRIMARY, TEXT, TEXT_MUTED

DEFAULT_MODEL_PATH = Path("models/model.pkl")
DEFAULT_SYMPTOMS_PATH = Path("models/symptoms.pkl")
DEFAULT_METADATA_PATH = Path("models/model_metadata.pkl")
DEFAULT_KMEANS_PATH = Path("models/kmeans_model.pkl")
DEFAULT_CLUSTER_METADATA_PATH = Path("models/cluster_metadata.pkl")
DEFAULT_CLUSTER_SYMPTOMS_PATH = Path("models/cluster_symptom_columns.pkl")

SYMPTOM_PICKER_KEY = "symptom_picker"
MODEL_DISCLAIMER = (
    "Model confidence is the classifier's relative score among the conditions it was trained on. "
    "It is not the chance that you have the condition, and this is not a diagnosis. "
    "Talk to a clinician about your symptoms."
)
SUBGROUP_NOTE = (
    "Subgroups come from K-Means clustering of past patient records. Being placed in a subgroup means your "
    "symptoms resemble that group's, nothing more. It is not a diagnosis."
)


def format_symptom(name: str) -> str:
    """Feature name to readable label: "spotting_ urination" -> "Spotting urination"."""
    return " ".join(str(name).replace("_", " ").split()).capitalize()


def render_asset_uploaders() -> tuple:
    """Optional custom model files, tucked away: most people use the bundled model."""
    with st.expander("Use your own model files", icon=":material/tune:"):
        st.caption("Leave these empty to use the bundled model. Files must match the format of the defaults.")
        model_file = st.file_uploader("Model (.pkl)", type=["pkl"], key="model_uploader")
        symptoms_file = st.file_uploader("Symptom list (.pkl)", type=["pkl"], key="symptoms_uploader")
        metadata_file = st.file_uploader("Model metadata (.pkl, optional)", type=["pkl"], key="metadata_uploader")
    return model_file, symptoms_file, metadata_file


@st.cache_resource
def _load_default_assets():
    """Cache default model assets so Cloud startup is not repeated every rerun."""
    loader = ModelLoader()
    model = loader.load_model(DEFAULT_MODEL_PATH)
    symptoms = loader.load_symptoms(DEFAULT_SYMPTOMS_PATH)
    metadata = None
    if DEFAULT_METADATA_PATH.exists():
        metadata = loader.load_metadata(DEFAULT_METADATA_PATH)
    return model, symptoms, metadata


def load_prediction_assets(model_file, symptoms_file, metadata_file):
    using_defaults = model_file is None and symptoms_file is None and metadata_file is None
    if using_defaults:
        if not DEFAULT_MODEL_PATH.exists() or not DEFAULT_SYMPTOMS_PATH.exists():
            raise FileNotFoundError(
                "Default model assets were not found in models/. Please upload model and symptoms files."
            )
        return _load_default_assets()

    loader = ModelLoader()

    model_source = model_file if model_file is not None else DEFAULT_MODEL_PATH
    symptoms_source = symptoms_file if symptoms_file is not None else DEFAULT_SYMPTOMS_PATH

    if model_file is None and not DEFAULT_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Default model not found at {DEFAULT_MODEL_PATH}. Please upload a model file."
        )
    if symptoms_file is None and not DEFAULT_SYMPTOMS_PATH.exists():
        raise FileNotFoundError(
            f"Default symptoms not found at {DEFAULT_SYMPTOMS_PATH}. "
            "Please upload a symptoms file."
        )

    model = loader.load_model(model_source)
    symptoms = loader.load_symptoms(symptoms_source)

    metadata = None
    metadata_source = metadata_file if metadata_file is not None else DEFAULT_METADATA_PATH
    if metadata_file is not None or DEFAULT_METADATA_PATH.exists():
        metadata = loader.load_metadata(metadata_source)

    return model, symptoms, metadata


@st.cache_resource
def _load_default_cluster_assets():
    """Cache default K-Means assets."""
    loader = ModelLoader()
    model = loader.load_model(DEFAULT_KMEANS_PATH)
    if DEFAULT_CLUSTER_SYMPTOMS_PATH.exists():
        symptoms = loader.load_symptoms(DEFAULT_CLUSTER_SYMPTOMS_PATH)
    else:
        symptoms = loader.load_symptoms(DEFAULT_SYMPTOMS_PATH)
    metadata = loader.load_metadata(DEFAULT_CLUSTER_METADATA_PATH)
    return model, symptoms, metadata


def load_cluster_assets():
    if not DEFAULT_KMEANS_PATH.exists():
        raise FileNotFoundError(
            f"Default K-Means model not found at {DEFAULT_KMEANS_PATH}."
        )
    if not DEFAULT_CLUSTER_METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Default cluster metadata not found at {DEFAULT_CLUSTER_METADATA_PATH}."
        )
    return _load_default_cluster_assets()


def _clear_symptoms() -> None:
    st.session_state[SYMPTOM_PICKER_KEY] = []


def render_symptom_picker(symptom_names: list[str]) -> list[str]:
    """Searchable symptom selection. Returns the model's own feature names, so preprocessing is unchanged."""
    selected = st.multiselect(
        "Symptoms",
        options=symptom_names,
        format_func=format_symptom,
        placeholder="Start typing a symptom, e.g. headache",
        key=SYMPTOM_PICKER_KEY,
        help="Type a few letters to see matching symptoms. Pick every symptom you have.",
    )
    count_col, clear_col = st.columns([3, 1], vertical_alignment="center")
    count = len(selected)
    count_col.markdown(f"**{count}** symptom{'s' if count != 1 else ''} selected" if count
                       else ":gray[No symptoms selected yet]")
    clear_col.button("Clear all", on_click=_clear_symptoms, disabled=not count, key="symptom_clear",
                     type="tertiary", icon=":material/close:")
    return selected


def render_analyze_button(disabled: bool) -> bool:
    return st.button("Analyze symptoms", type="primary", key="analyze_symptoms", disabled=disabled,
                     icon=":material/play_arrow:")


def _alternatives_chart(result: PredictionResult) -> alt.Chart:
    data = pd.DataFrame(
        {
            "Condition": [item.disease for item in result.ranked],
            "Model confidence": [item.probability for item in result.ranked],
            "Rank": ["Top prediction" if index == 0 else "Alternative" for index in range(len(result.ranked))],
        }
    )
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=4, height=18).encode(
        x=alt.X("Model confidence:Q", axis=alt.Axis(format="%", grid=True, gridColor=BORDER, tickCount=5,
                                                     labelColor=TEXT_MUTED, title=None),
                scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("Condition:N", sort=None, axis=alt.Axis(title=None, labelColor=TEXT, labelLimit=220, ticks=False,
                                                         domain=False)),
        color=alt.Color("Rank:N", scale=alt.Scale(domain=["Top prediction", "Alternative"], range=[PRIMARY, "#93C5FD"]),
                        legend=None),
        tooltip=[alt.Tooltip("Condition:N"), alt.Tooltip("Model confidence:Q", format=".1%")],
    )
    labels = bars.mark_text(align="left", dx=6, color=TEXT_MUTED).encode(
        text=alt.Text("Model confidence:Q", format=".0%"), color=alt.value(TEXT_MUTED)
    )
    return (bars + labels).properties(height=46 * len(data) + 10).configure_view(stroke=None).configure(background="transparent")


def render_model_output(result: PredictionResult) -> None:
    """Primary prediction and alternatives, labelled as model output."""
    with card("model-output", lane="model"):
        section_header("Disease prediction", "What the trained classifier predicts from your symptoms", badge="model")
        prediction_col, confidence_col = st.columns([3, 2])
        with prediction_col:
            st.markdown(":gray[Predicted condition]")
            st.markdown(f"## {result.top_disease}")
        with confidence_col:
            st.metric("Model confidence", f"{result.top_probability:.0%}",
                      help="The classifier's relative score for this condition, not a probability of having it.")
            st.progress(min(max(result.top_probability, 0.0), 1.0))
        if result.is_low_confidence:
            st.warning(
                f"Low model confidence: no condition reached "
                f"{DiseasePredictionController.CONFIDENCE_THRESHOLD:.0%}. Your symptoms fit several conditions "
                "similarly, so treat this result with extra caution.",
                icon=":material/warning:",
            )
        st.markdown(f"**Top {len(result.ranked)} model predictions**")
        st.altair_chart(_alternatives_chart(result), width="stretch")
        st.caption(MODEL_DISCLAIMER)


def render_prediction_result(result: PredictionResult) -> None:
    """Compatibility name for the model-output section."""
    render_model_output(result)


def render_predict_button() -> bool:
    return render_analyze_button(disabled=False)


def run_prediction(
    controller: DiseasePredictionController,
    selected_symptoms: list[str],
) -> PredictionResult:
    request = PredictionRequest(selected_symptoms=selected_symptoms)
    return controller.predict(request)


def render_cluster_summary_tables(summary: ClusterSummary) -> None:
    """Two tables: the cluster's most common symptoms and diagnoses."""
    symptoms_col, diseases_col = st.columns(2)
    with symptoms_col:
        st.markdown("**Common symptoms in this subgroup**")
        st.dataframe(
            [{"Symptom": format_symptom(item.name), "Share of patients": item.score} for item in summary.top_symptoms],
            hide_index=True,
            width="stretch",
            column_config={"Share of patients": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                                 max_value=1)},
        )
    with diseases_col:
        st.markdown("**Common diagnoses in this subgroup**")
        if summary.top_diseases:
            st.dataframe(
                [{"Diagnosis": item.name, "Share of patients": item.score} for item in summary.top_diseases],
                hide_index=True,
                width="stretch",
                column_config={"Share of patients": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                                     max_value=1)},
            )
        else:
            st.caption("No diagnosis information is available for this subgroup.")


def render_subgroup_result(result: ClusterAssignmentResult) -> None:
    """Closest patient subgroup, labelled as similarity grouping."""
    with card("subgroup-output", lane="subgroup"):
        section_header("Patient subgroup", "Past patients whose symptom patterns are most like yours", badge="subgroup")
        field_grid(
            [
                ("Subgroup", f"Cluster {result.cluster_id}"),
                ("Similarity", f"{result.confidence:.0%}"),
                ("Past patients in this subgroup", f"{result.summary.patient_count:,}"),
            ]
        )
        st.caption(
            "Similarity compares how close your symptoms are to this subgroup versus the others. A low value means "
            "your symptoms sit between several subgroups."
        )
        render_cluster_summary_tables(result.summary)
        st.caption(SUBGROUP_NOTE)


def render_cluster_assignment_result(result: ClusterAssignmentResult) -> None:
    """Compatibility name for the subgroup section."""
    render_subgroup_result(result)


def render_cluster_browse(controller: ClusterController) -> None:
    st.markdown("**Browse a subgroup**")
    cluster_id = st.selectbox(
        "Subgroup",
        options=controller.cluster_ids,
        key="browse_cluster_id",
        format_func=lambda value: f"Cluster {value}",
    )
    summary = controller.get_summary(int(cluster_id))
    st.caption(f"{summary.patient_count:,} past patient records")
    render_cluster_summary_tables(summary)


def render_cluster_compare(controller: ClusterController) -> None:
    st.markdown("**Compare two subgroups**")
    left_col, right_col = st.columns(2)
    left_id = left_col.selectbox(
        "First subgroup",
        options=controller.cluster_ids,
        index=0,
        key="compare_cluster_left",
        format_func=lambda value: f"Cluster {value}",
    )
    right_id = right_col.selectbox(
        "Second subgroup",
        options=controller.cluster_ids,
        index=1 if len(controller.cluster_ids) > 1 else 0,
        key="compare_cluster_right",
        format_func=lambda value: f"Cluster {value}",
    )
    render_cluster_comparison(controller.compare(int(left_id), int(right_id)))


def render_cluster_comparison(comparison: ClusterComparison) -> None:
    left_col, right_col = st.columns(2)
    for column, summary in ((left_col, comparison.left), (right_col, comparison.right)):
        with column:
            st.markdown(f"**Cluster {summary.cluster_id}**")
            st.caption(f"{summary.patient_count:,} past patient records")
            st.dataframe(
                [{"Symptom": format_symptom(item.name), "Share": item.score} for item in summary.top_symptoms],
                hide_index=True, width="stretch",
                column_config={"Share": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)},
            )
    shared_symptoms = ", ".join(format_symptom(name) for name in comparison.shared_symptoms) or "None"
    shared_diseases = ", ".join(comparison.shared_diseases) or "None"
    field_grid([("Shared common symptoms", shared_symptoms), ("Shared common diagnoses", shared_diseases)], columns=2)


def run_cluster_assignment(
    controller: ClusterController,
    selected_symptoms: list[str],
) -> ClusterAssignmentResult:
    request = PredictionRequest(selected_symptoms=selected_symptoms)
    return controller.assign(request)
