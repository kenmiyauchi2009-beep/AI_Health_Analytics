# DeltaAI Agent Handoff

## Project Goal
Build a beginner-friendly Streamlit Bio Explorer app with clear separation of concerns, upload-first dashboard flow, disease prediction, and K-Means cluster matching from symptom checklists.

## Current Status
- Virtual environment `venv` exists.
- Lean Cloud-friendly `requirements.txt` (sklearn `>=1.7.2` for Python 3.14 wheels).
- `app.py` only orchestrates top-level pages.
- Pages:
  - `Dashboard` (CSV explore / plots)
  - `Disease Prediction` with sub-tabs: **Predict** | **Clusters**
- Classifier assets:
  - `models/model.pkl`
  - `models/symptoms.pkl`
  - `models/model_metadata.pkl`
- K-Means assets:
  - `models/kmeans_model.pkl` (8 clusters, 132 features)
  - `models/cluster_metadata.pkl` (sizes + summaries)
  - `models/cluster_symptom_columns.pkl` (same order as `symptoms.pkl`)
- Tests: `python -m unittest tests.test_prediction tests.test_cluster -v`

## Architecture (Current)

### 1) App-level orchestration
- **File:** `app.py`
- **Navigation:** Exclusive top `st.segmented_control` for `Dashboard` / `Disease Prediction`
- **Page config:** `st.set_page_config` once in `app.py`

### 2) Dashboard page
- **File:** `app_pages/dashboard_page.py`
- Upload-first CSV explorer with count plot, scatter, correlation matrix
- Plot sizes capped to avoid Pillow decompression bomb errors
- Use `return` (not `st.stop()`) for early exits

### 3) Disease Prediction page
- **File:** `app_pages/prediction_page.py`
- Shared symptom checklist above sub-tabs
- Sub-tabs:
  - **Predict** — logistic regression disease probabilities
  - **Clusters** — K-Means assign / browse / compare

### 4) Prediction package (`prediction/`)

| Piece | File | Responsibility |
|---|---|---|
| DiseasePredictionController | `controller.py` | Disease predict_proba flow |
| ClusterController | `cluster_controller.py` | Assign / browse / compare clusters |
| Symptoms | `symptoms.py` | Load feature names; binary feature vector |
| PredictionRequest | `prediction_request.py` | Selected symptom list (shared) |
| PredictionResult | `prediction_result.py` | Disease prediction output |
| Cluster result types | `cluster_result.py` | Assignment, summary, comparison |
| ModelLoader | `model_loader.py` | joblib/pickle loading |
| UI | `ui_view.py` | Checklist, predict UI, cluster UI |

## Disease Predict Behavior
- Binary feature vector from checklist order
- Top-1 disease + Top-3 probabilities
- Low-confidence flag if top probability **< 0.50**
- Empty selection → error message

## Cluster Behavior
- Confidence: **softmax of inverse distances** to centroids (C1)
- UI: **Predict | Clusters** sub-tabs (D3)
- Assign shows: cluster id, confidence, top symptoms, common diseases
- Browse: pick any cluster 0–7
- Compare: two clusters side-by-side + shared top symptoms/diseases
- Top items: up to 5, scores `> 0` only
- Empty selection on assign → same style error as disease predict

## Decisions Locked In
- Disease confidence threshold: **0.50**
- Disease ranked display: **Top-1 + Top-3**
- Cluster confidence: **softmax(inverse distance)**
- Cluster UI: **sub-tabs on Disease Prediction page**
- Cloud: prefer Python **3.12** in Streamlit Advanced settings; `runtime.txt` is ignored

## How To Run
```bash
source venv/bin/activate
streamlit run app.py
```

## How To Verify
```bash
source venv/bin/activate
python -m unittest tests.test_prediction tests.test_cluster -v
```

## Notes For Next Agent
- Keep `app.py` thin.
- Do not hardcode symptom/disease/cluster labels; load from pickles/metadata.
- Reuse `PredictionRequest` + `Symptoms.to_feature_vector()` for both predict and cluster assign.
- Page modules live in `app_pages/` (not Streamlit’s reserved `pages/`).
- Medical disclaimer: not a clinical diagnosis tool.
