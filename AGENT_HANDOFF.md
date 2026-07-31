# DeltaAI Agent Handoff

## Project Goal
Build a beginner-friendly Streamlit Bio Explorer app with clear separation of concerns, upload-first dashboard flow, and a disease-prediction page driven by pickle model assets.

## Current Status
- Virtual environment `venv` exists.
- Dependencies include `streamlit`, `pandas`, `numpy`, `matplotlib`, `seaborn`, and pinned `scikit-learn==1.6.1` (plus `joblib`, `scipy`).
- `app.py` only orchestrates pages.
- Pages:
  - `Dashboard` (CSV explore / plots)
  - `Disease Prediction` (symptom checklist → disease probabilities)
- Default model assets copied to:
  - `models/model.pkl`
  - `models/symptoms.pkl`
  - `models/model_metadata.pkl`
- Original root pickles still present (`disease_model.pkl`, `symptom_columns.pkl`, `model_metadata.pkl`).
- Prediction verification tests pass: `python -m unittest tests.test_prediction -v`

## Architecture (Current)

### 1) App-level orchestration
- **File:** `app.py`
- **Responsibility:** Route/orchestrate between pages only.
- **Navigation:** Top tabs (`st.tabs`) for `Dashboard` and `Disease Prediction`
- **Page config:** `st.set_page_config` is called once in `app.py`

### 2) Dashboard page
- **File:** `app_pages/dashboard_page.py`
- Uses `dashboard/data_service.py`, `dashboard/ui_view.py`, `dashboard/plots_view.py`
- Upload-first CSV explorer with count plot, scatter, correlation matrix
- Plot sizes capped to avoid Pillow decompression bomb errors

### 3) Disease Prediction page
- **File:** `app_pages/prediction_page.py`
- Coordinates prediction UI + controller flow

### 4) Prediction package (`prediction/`)
Core entities requested by product requirements:

| Entity | File | Responsibility |
|---|---|---|
| DiseasePredictionController | `prediction/controller.py` | Validate request, build features, call model, build result |
| Symptoms | `prediction/symptoms.py` | Load expandable symptom names from pickle; build binary feature vector |
| Model | loaded via loader | LogisticRegression from `models/model.pkl` (joblib) |
| PredictionRequest | `prediction/prediction_request.py` | Selected symptom list |
| PredictionResult | `prediction/prediction_result.py` | Top disease, confidence, top-N ranked probs, low-confidence flag |
| ModelLoader | `prediction/model_loader.py` | Load model/symptoms/metadata from default paths or uploads |
| User Interface | `prediction/ui_view.py` | Checklist, uploaders, result rendering |

## Disease Prediction Behavior
- Symptoms loaded from pickle (not hardcoded); currently 132 features.
- Multi-select checklist.
- Feature vector: ordered binary vector matching `symptoms.pkl`.
- Prediction uses `predict_proba`.
- Shows:
  - Top-1 most likely disease
  - Top-N ranked probabilities where **N = 3**
- Low-confidence flag when top probability **< 0.50**
- Empty selection error: user must select at least one symptom
- Defaults from `models/`; optional uploaders can override model/symptoms/metadata

## Decisions Locked In
- Confidence threshold: **0.50**
- Ranked display: **Top-1 + Top-3**
- Default assets: copy into `models/` (`C1`)
- sklearn pin: **`scikit-learn==1.6.1`** (`D1`)
- Model load method: **joblib** (plain pickle fails on this artifact)

## How To Run
```bash
source venv/bin/activate
streamlit run app.py
```

## How To Verify Prediction Logic
```bash
source venv/bin/activate
python -m unittest tests.test_prediction -v
```

## Notes For Next Agent
- Keep `app.py` thin (page orchestration only).
- Top-tab navigation uses `st.tabs` in `app.py` (sidebar page selectbox removed).
- Page modules live in `app_pages/` (not Streamlit's reserved `pages/` folder) so automatic multipage sidebar links are not shown.
- Important: page modules must use `return` (not `st.stop()`) for early exits, because `st.stop()` halts the whole script and leaves other tabs blank.
- Do not hardcode symptom names; always load from symptoms pickle.
- Keep prediction business logic in `prediction/`, UI in `prediction/ui_view.py`, page wiring in `app_pages/prediction_page.py`.
- Medical disclaimer remains important: this is not a clinical diagnosis tool.
- Avoid unbounded matplotlib figure sizes on dashboard plots.

## Suggested Next Steps
1. Add medical disclaimer emphasis / clinician-referral copy if product requires it.
2. Optionally add search/filter for long symptom checklist UX.
3. Commit current work once ready.
