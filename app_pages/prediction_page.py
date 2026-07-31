import streamlit as st

from prediction.controller import DiseasePredictionController
from prediction.ui_view import (
    load_prediction_assets,
    render_asset_uploaders,
    render_page_header,
    render_predict_button,
    render_prediction_result,
    render_symptom_checklist,
    run_prediction,
)


def render() -> None:
    """Render the disease prediction page."""
    render_page_header()
    model_file, symptoms_file, metadata_file = render_asset_uploaders()

    try:
        model, symptoms, metadata = load_prediction_assets(
            model_file=model_file,
            symptoms_file=symptoms_file,
            metadata_file=metadata_file,
        )
    except Exception as error:
        st.error(str(error))
        return

    if metadata is not None:
        st.caption(
            f"Model type: {metadata.get('model_type', 'unknown')} | "
            f"Features: {metadata.get('num_features', len(symptoms.names))} | "
            f"Diseases: {len(metadata.get('disease_labels', [])) or 'n/a'}"
        )

    selected_symptoms = render_symptom_checklist(symptoms.names)
    st.write(f"Selected symptoms: {len(selected_symptoms)}")

    if render_predict_button():
        try:
            controller = DiseasePredictionController(model=model, symptoms=symptoms)
            result = run_prediction(controller, selected_symptoms)
            render_prediction_result(result)
        except ValueError as error:
            st.error(str(error))
