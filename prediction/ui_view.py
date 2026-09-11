from __future__ import annotations

from pathlib import Path

import streamlit as st

from prediction.cluster_controller import ClusterController
from prediction.cluster_result import ClusterAssignmentResult, ClusterComparison, ClusterSummary
from prediction.controller import DiseasePredictionController
from prediction.model_loader import ModelLoader
from prediction.prediction_request import PredictionRequest
from prediction.prediction_result import PredictionResult

DEFAULT_MODEL_PATH = Path("models/model.pkl")
DEFAULT_SYMPTOMS_PATH = Path("models/symptoms.pkl")
DEFAULT_METADATA_PATH = Path("models/model_metadata.pkl")
DEFAULT_KMEANS_PATH = Path("models/kmeans_model.pkl")
DEFAULT_CLUSTER_METADATA_PATH = Path("models/cluster_metadata.pkl")
DEFAULT_CLUSTER_SYMPTOMS_PATH = Path("models/cluster_symptom_columns.pkl")


def render_page_header() -> None:
    st.title("Disease Prediction")
    st.caption(
        "Select symptoms from the checklist, then use Predict for disease probabilities "
        "or Clusters for K-Means group matching. This is not a medical diagnosis."
    )


def render_asset_uploaders() -> tuple:
    st.subheader("Model Assets")
    model_file = st.file_uploader("Upload model (.pkl)", type=["pkl"], key="model_uploader")
    symptoms_file = st.file_uploader(
        "Upload symptoms (.pkl)",
        type=["pkl"],
        key="symptoms_uploader",
    )
    metadata_file = st.file_uploader(
        "Upload model metadata (.pkl, optional)",
        type=["pkl"],
        key="metadata_uploader",
    )
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


def render_symptom_checklist(symptom_names: list[str]) -> list[str]:
    st.subheader("Symptom Checklist")
    st.write("Tick all symptoms you are experiencing.")
    selected: list[str] = []

    columns = st.columns(3)
    for index, symptom in enumerate(symptom_names):
        column = columns[index % 3]
        label = symptom.replace("_", " ")
        if column.checkbox(label, key=f"symptom_{symptom}"):
            selected.append(symptom)

    return selected


def render_prediction_result(result: PredictionResult) -> None:
    st.subheader("Prediction Result")
    st.success(
        f"Most likely disease: **{result.top_disease}** "
        f"({result.top_probability:.1%} confidence)"
    )

    if result.is_low_confidence:
        st.warning(
            "Low confidence: none of the diseases reached a high confidence score "
            f"(threshold {DiseasePredictionController.CONFIDENCE_THRESHOLD:.0%}). "
            "Please review symptoms or consult a clinician."
        )

    st.markdown(f"### Top {DiseasePredictionController.TOP_N} Diseases")
    rows = [
        {
            "Rank": index,
            "Disease": item.disease,
            "Probability": f"{item.probability:.1%}",
        }
        for index, item in enumerate(result.ranked, start=1)
    ]
    st.dataframe(rows, use_container_width=True)


def render_predict_button() -> bool:
    return st.button("Predict Disease", type="primary", key="predict_disease_button")


def run_prediction(
    controller: DiseasePredictionController,
    selected_symptoms: list[str],
) -> PredictionResult:
    request = PredictionRequest(selected_symptoms=selected_symptoms)
    return controller.predict(request)


def render_cluster_layman_guide(n_clusters: int) -> None:
    st.info(
        f"**What is a cluster?**  \n"
        f"Think of clusters as {n_clusters} “patient groups” discovered from past data. "
        "People in the same group tend to report similar symptom patterns.  \n\n"
        "**How to use this tab**  \n"
        "1. Tick your symptoms above.  \n"
        "2. Click **Find Closest Cluster** to see which group you most resemble.  \n"
        "3. Use **Browse** to explore any group.  \n"
        "4. Use **Compare** to see how two groups differ.  \n\n"
        "This is a similarity grouping tool, not a diagnosis."
    )


def _summary_tables(summary: ClusterSummary) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top symptoms**")
        st.caption("Symptoms most often seen in this group (higher % = more common).")
        st.dataframe(
            [
                {
                    "Symptom": item.name.replace("_", " "),
                    "Frequency": f"{item.score:.1%}",
                }
                for item in summary.top_symptoms
            ],
            use_container_width=True,
        )
    with c2:
        st.markdown("**Common diseases**")
        st.caption("Conditions often linked with this group in the training data.")
        st.dataframe(
            [
                {
                    "Disease": item.name,
                    "Share": f"{item.score:.1%}",
                }
                for item in summary.top_diseases
            ],
            use_container_width=True,
        )


def render_cluster_assignment_result(result: ClusterAssignmentResult) -> None:
    st.subheader("Closest Cluster")
    st.success(
        f"You most closely match **Cluster {result.cluster_id}** "
        f"({result.confidence:.1%} confidence). "
        f"This group includes about **{result.summary.patient_count}** past patient records."
    )
    st.caption(
        "**Confidence** estimates how uniquely your symptoms fit this group versus the others. "
        "A higher value means a clearer match. Lower confidence means your symptoms could fit more than one group."
    )
    _summary_tables(result.summary)


def render_cluster_browse(controller: ClusterController) -> None:
    st.subheader("Browse Clusters")
    st.caption(
        "Explore each patient group even without matching your own symptoms. "
        "This helps you see what each cluster typically looks like."
    )
    cluster_id = st.selectbox(
        "Choose a cluster",
        options=controller.cluster_ids,
        key="browse_cluster_id",
        format_func=lambda value: f"Cluster {value}",
    )
    summary = controller.get_summary(int(cluster_id))
    st.write(
        f"**Cluster {summary.cluster_id}** has about **{summary.patient_count}** "
        "past patient records with similar symptom patterns."
    )
    _summary_tables(summary)


def render_cluster_compare(controller: ClusterController) -> None:
    st.subheader("Compare Two Clusters")
    st.caption(
        "Pick two groups to see how their common symptoms and diseases differ, "
        "and whether they share any patterns."
    )
    left_col, right_col = st.columns(2)
    with left_col:
        left_id = st.selectbox(
            "Cluster A",
            options=controller.cluster_ids,
            index=0,
            key="compare_cluster_left",
            format_func=lambda value: f"Cluster {value}",
        )
    with right_col:
        right_id = st.selectbox(
            "Cluster B",
            options=controller.cluster_ids,
            index=1 if len(controller.cluster_ids) > 1 else 0,
            key="compare_cluster_right",
            format_func=lambda value: f"Cluster {value}",
        )

    comparison = controller.compare(int(left_id), int(right_id))
    render_cluster_comparison(comparison)


def render_cluster_comparison(comparison: ClusterComparison) -> None:
    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown(f"### Cluster {comparison.left.cluster_id}")
        st.write(
            f"About **{comparison.left.patient_count}** past patient records in this group."
        )
        _summary_tables(comparison.left)
    with right_col:
        st.markdown(f"### Cluster {comparison.right.cluster_id}")
        st.write(
            f"About **{comparison.right.patient_count}** past patient records in this group."
        )
        _summary_tables(comparison.right)

    st.markdown("### What they share")
    st.caption("Patterns that appear in the top lists of both groups.")
    shared_symptoms = (
        ", ".join(name.replace("_", " ") for name in comparison.shared_symptoms)
        or "None in the top symptom lists"
    )
    shared_diseases = (
        ", ".join(comparison.shared_diseases) or "None in the top disease lists"
    )
    st.write(f"Shared top symptoms: {shared_symptoms}")
    st.write(f"Shared common diseases: {shared_diseases}")


def render_assign_cluster_button() -> bool:
    return st.button("Find Closest Cluster", type="primary", key="assign_cluster_button")


def run_cluster_assignment(
    controller: ClusterController,
    selected_symptoms: list[str],
) -> ClusterAssignmentResult:
    request = PredictionRequest(selected_symptoms=selected_symptoms)
    return controller.assign(request)
