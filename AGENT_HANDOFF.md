# DeltaAI Agent Handoff

## Project Goal
Build a beginner-friendly Streamlit Bio Explorer app with clear separation of concerns, upload-first dashboard flow, disease prediction, and K-Means cluster matching from symptom checklists.

## Current Status
- Virtual environment `venv` exists.
- Lean Cloud-friendly `requirements.txt` (sklearn `>=1.7.2` for Python 3.14 wheels).
- `app.py` only orchestrates top-level pages.
- Disease Prediction with sub-tabs: **Predict** | **Clusters**, plus **Ask AI** panel below results
- Groq-powered assistant (`assistant/`) explains ML outputs only
- Secrets: `.streamlit/secrets.toml` (gitignored) with `GROQ_API_KEY`
- Tests: `python -m unittest tests.test_prediction tests.test_cluster tests.test_assistant tests.test_practitioner tests.test_registration tests.test_patient_overview tests.test_analysis_review -v`

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
- Below both tabs: **Ask AI about your results** (requires Predict and/or Cluster result first)

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

### 5) AI assistant package (`assistant/`)

| Entity | File | Responsibility |
|---|---|---|
| AIQuery | `ai_query.py` | User question |
| PatientAnalysisContext | `patient_analysis_context.py` | Symptoms + prediction + cluster payload |
| ChatMessage | `chat_message.py` | Chat turn |
| AIResponse | `ai_response.py` | Answer / refusal / suggestions |
| LLMClient | `llm_client.py` | Groq Python SDK chat completions |
| PromptBuilder | `prompt_builder.py` | System + grounded context prompt |
| SafetyGuard | `safety_guard.py` | Block diagnosis-outside-pipeline / unrelated Qs |
| ConversationManager | `conversation_manager.py` | Session chat history |
| AIResultAssistant | `ai_result_assistant.py` | Orchestrates ask flow |
| UI | `ui_view.py` | Chat panel + suggested questions |

## Ask AI Behavior
- Uses Groq model `openai/gpt-oss-20b` by default (`llama-3.1-8b-instant` retired for free/dev)
- Optional override: `GROQ_MODEL` in `.streamlit/secrets.toml`
- Requires at least one of: disease prediction result, cluster assignment result
- Suggested questions:
  - Why was this disease predicted?
  - Why am I in this cluster?
  - What does confidence mean?
  - How is my symptom profile similar to this cluster?
- Refuses independent diagnosis / unrelated topics
- API key from `.streamlit/secrets.toml` → `GROQ_API_KEY`

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
python -m unittest tests.test_prediction tests.test_cluster tests.test_assistant tests.test_practitioner tests.test_registration tests.test_patient_overview tests.test_analysis_review -v
```

## Groq setup
1. Put your key in `.streamlit/secrets.toml`:
   ```toml
   GROQ_API_KEY = "your_real_key"
   ```
2. Example template: `.streamlit/secrets.toml.example`
3. For Streamlit Cloud, add the same secret in the app settings.

## Patient Overview (doctor)
- **Files:** `app_pages/patient_overview_page.py` (UI), `app_pages/patient_overview_service.py` (data, unit-tested)
- Every patient **Predict Disease** run is saved to MongoDB collection `patient_analyses` (symptoms, top disease, confidence, top-3, low-confidence flag)
- Doctor clicks **View Patient** → sets `st.session_state.viewing_patient_email` and switches to the **Patient Overview page** (`/patient-overview`); **← Back to dashboard** clears it
- Shows profile (name, age from `date_of_birth`, `known_conditions`) + analysis history (date, symptoms, prediction, confidence)
- **Review Analysis** marks the analysis reviewed (`reviewed`, `reviewed_by`, `reviewed_at`) and opens the Review Analysis page
- Only the patient's current Primary Health Practitioner can open the overview
- Patient sign-up has an optional comma-separated **Known Conditions** field (stored as a list)

## Review Analysis (doctor)
- **Files:** `app_pages/analysis_review_page.py` (UI), `app_pages/analysis_review_service.py` (data, unit-tested)
- Separate page (`/review-analysis`): **Review Analysis** sets `st.session_state.reviewing_analysis_id` and switches pages; **← Back to patient overview** clears it
- Sections: Patient Reported Symptoms → Disease Predictions (model prediction, confidence, other predictions) → Patient Subgroup (cluster, similarity, common symptoms, common diagnoses) → **Why this Cluster** → AI Assistant → **Add Doctor's note**
- Cluster is **recomputed** from the saved symptoms (not stored), so old analyses get one too
- **Why this Cluster**: symptom overlap with the cluster's top symptoms + next-closest cluster and the similarity gap (flags < 5% as uncertain)
- **Doctor AI assistant** reuses `AIResultAssistant` with `DoctorPromptBuilder`, `DoctorSafetyGuard` (doctor suggestions) and `DoctorAnalysisContext` (adds analysis date, known conditions, earlier analyses for comparison). Chat history is per analysis (`doctor_ai_<analysis id>`)
- **Add Doctor's note** is a placeholder (shows a "coming soon" toast) — not implemented yet

## Page routing
- `app.py` always calls `st.navigation(..., position="hidden")` and picks the pages for the user: Sign in (signed out), the patient app (segmented control, unchanged), or the doctor pages
- Doctor pages live in `app_pages/doctor_navigation.py`: Doctor Dashboard (default) → Patient Overview → Review Analysis. Move between them with `go_to(...)` (`st.switch_page`), which keeps session state
- Reloading the browser starts a new session, so the user must sign in again (auth is session-only)
- `AppTest` renders only the default page per run; set `at._page_hash = calc_hash("<url-path>")` to test another page

## Notes For Next Agent
- Keep `app.py` thin.
- Do not hardcode symptom/disease/cluster labels; load from pickles/metadata.
- Reuse `PredictionRequest` + `Symptoms.to_feature_vector()` for both predict and cluster assign.
- Page modules live in `app_pages/` (not Streamlit’s reserved `pages/`).
- Medical disclaimer: not a clinical diagnosis tool.
