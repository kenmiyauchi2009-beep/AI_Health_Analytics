import streamlit as st

from prediction.cluster_controller import ClusterController
from prediction.controller import DiseasePredictionController
from prediction.ui_view import (
    load_cluster_assets,
    load_prediction_assets,
    render_asset_uploaders,
    render_assign_cluster_button,
    render_cluster_assignment_result,
    render_cluster_browse,
    render_cluster_compare,
    render_cluster_layman_guide,
    render_page_header,
    render_predict_button,
    render_prediction_result,
    render_symptom_checklist,
    run_cluster_assignment,
    run_prediction,
)


def render() -> None:
    """Render the disease prediction page with Predict and Clusters sub-tabs."""
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
            f"Classifier: {metadata.get('model_type', 'unknown')} | "
            f"Features: {metadata.get('num_features', len(symptoms.names))} | "
            f"Diseases: {len(metadata.get('disease_labels', [])) or 'n/a'}"
        )

    selected_symptoms = render_symptom_checklist(symptoms.names)
    st.write(f"Selected symptoms: {len(selected_symptoms)}")

    predict_tab, clusters_tab = st.tabs(["Predict", "Clusters"])

    with predict_tab:
        if render_predict_button():
            try:
                controller = DiseasePredictionController(model=model, symptoms=symptoms)
                result = run_prediction(controller, selected_symptoms)
                render_prediction_result(result)
            except ValueError as error:
                st.error(str(error))

    with clusters_tab:
        try:
            kmeans_model, cluster_symptoms, cluster_metadata = load_cluster_assets()
            cluster_controller = ClusterController(
                model=kmeans_model,
                symptoms=cluster_symptoms,
                metadata=cluster_metadata,
            )
        except Exception as error:
            st.error(str(error))
            return

        st.caption(
            f"K-Means clusters: {cluster_metadata.get('n_clusters', len(cluster_controller.cluster_ids))} | "
            f"Features: {len(cluster_symptoms.names)}"
        )
        render_cluster_layman_guide(
            n_clusters=int(
                cluster_metadata.get("n_clusters", len(cluster_controller.cluster_ids))
            )
        )

        if render_assign_cluster_button():
            try:
                assignment = run_cluster_assignment(cluster_controller, selected_symptoms)
                render_cluster_assignment_result(assignment)
            except ValueError as error:
                st.error(str(error))

        st.divider()
        render_cluster_browse(cluster_controller)
        st.divider()
        render_cluster_compare(cluster_controller)
