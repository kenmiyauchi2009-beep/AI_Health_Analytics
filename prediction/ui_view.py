from __future__ import annotations

from pathlib import Path

import streamlit as st

from prediction.controller import DiseasePredictionController
from prediction.model_loader import ModelLoader
from prediction.prediction_request import PredictionRequest
from prediction.prediction_result import PredictionResult

DEFAULT_MODEL_PATH = Path("models/model.pkl")
DEFAULT_SYMPTOMS_PATH = Path("models/symptoms.pkl")
DEFAULT_METADATA_PATH = Path("models/model_metadata.pkl")


def render_page_header() -> None:
    st.title("Disease Prediction")
    st.caption(
        "Select symptoms from the checklist to estimate the most likely disease. "
        "This is not a medical diagnosis."
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
    return st.button("Predict Disease", type="primary")


def run_prediction(
    controller: DiseasePredictionController,
    selected_symptoms: list[str],
) -> PredictionResult:
    request = PredictionRequest(selected_symptoms=selected_symptoms)
    return controller.predict(request)
