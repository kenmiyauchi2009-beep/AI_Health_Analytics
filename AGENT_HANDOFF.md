# DeltaAI Agent Handoff

## Project Goal
Build a beginner-friendly Streamlit Bio Explorer app with clear separation of concerns, upload-first dashboard flow, disease prediction, and K-Means cluster matching from symptom checklists.

## Current Status
- Virtual environment `venv` exists.
- Lean Cloud-friendly `requirements.txt` (sklearn `>=1.7.2` for Python 3.14 wheels).
- `app.py` only orchestrates top-level pages.
- New health analysis page: searchable symptoms → one **Analyze symptoms** click runs the classifier and K-Means → Model output / Patient subgroup / AI explanation sections
- UI design system in `ui/` (see `ui/DESIGN.md`); theme tokens in `.streamlit/config.toml`
- Groq-powered assistant (`assistant/`) explains ML outputs only
- Secrets: `.streamlit/secrets.toml` (gitignored) with `GROQ_API_KEY`
- Tests: `python -m unittest tests.test_prediction tests.test_cluster tests.test_assistant tests.test_practitioner tests.test_registration tests.test_patient_overview tests.test_analysis_review tests.test_doctor_notes tests.test_prescriptions tests.test_appointments -v`

## Architecture (Current)

### 1) App-level orchestration
- **File:** `app.py`
- **Navigation:** `st.navigation(position="hidden")` + a grouped sidebar of `st.page_link`s (`app_pages/sidebar.py`); see "Page routing"
- **Page config + theme:** `st.set_page_config` and `ui.theme.apply_theme()` once in `app.py`

### 2) Data explorer (patient) and doctor dashboard
- **File:** `app_pages/dashboard_page.py` (`render_patient_dashboard` = Data explorer; `render_doctor_dashboard`, `render_my_patients_page`, `render_patient_requests_page`)
- Upload-first CSV explorer with count plot, scatter, correlation matrix (Altair, `dashboard/plots_view.py`); chart settings live on the page, not the sidebar
- Use `return` (not `st.stop()`) for early exits

### 3) New health analysis page
- **File:** `app_pages/prediction_page.py`; widgets in `prediction/ui_view.py`
- Step 1: `st.multiselect` over the model's own feature names (type-ahead search, readable labels via `format_symptom`); feature order still comes from `Symptoms.to_feature_vector()`
- **Analyze symptoms** runs both models, stores `latest_prediction`, `latest_cluster_assignment`, `selected_symptoms`, and saves the prediction to history
- Step 2 sections, each labelled by provenance: Disease prediction (Model output, Altair alternatives chart), Patient subgroup (Subgroup analysis + "Explore all patient subgroups" browse/compare), Ask about your results (AI explanation)
- Custom model uploaders are in the "Use your own model files" expander

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
- UI: patient subgroup section on the analysis results; browse/compare in an expander
- Assign shows: cluster id, confidence, top symptoms, common diseases
- Browse: pick any cluster 0–7
- Compare: two clusters side-by-side + shared top symptoms/diseases
- Top items: up to 5, scores `> 0` only
- Empty selection on assign → same style error as disease predict

## Decisions Locked In
- Disease confidence threshold: **0.50**
- Disease ranked display: **Top-1 + Top-3**
- Cluster confidence: **softmax(inverse distance)**
- Cluster UI: **Patient subgroup section on the analysis results** (replaced the old sub-tabs)
- Cloud: prefer Python **3.12** in Streamlit Advanced settings; `runtime.txt` is ignored

## How To Run
```bash
source venv/bin/activate
streamlit run app.py
```

## How To Verify
```bash
source venv/bin/activate
python -m unittest tests.test_prediction tests.test_cluster tests.test_assistant tests.test_practitioner tests.test_registration tests.test_patient_overview tests.test_analysis_review tests.test_doctor_notes tests.test_prescriptions tests.test_appointments -v
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
- **Add Doctor's note** opens the Doctor Notes box (see below)

## Doctor Notes
- **File:** `app_pages/doctor_notes_service.py` (`DoctorNote` dataclass + save/list, unit-tested); UI in `analysis_review_page.py`
- Stored separately in MongoDB collection `doctor_notes`: `patient_id` (patient's user `_id`), `patient_email`, `doctor_email`, `analysis_id`, `text`, `created_at`
- `get_patient_overview()` now also returns the patient's `id`
- Review Analysis page: **Add Doctor's note** → text box + **Save Note**; notes saved for that analysis are listed below, newest first
- The older `review_notes` field on analyses is no longer written by the UI (still shown on the overview if present)

## Simulated Prescriptions (educational demo)
- **Not real prescriptions.** Every screen and PDF page says SIMULATED / not legally valid / not sent to a pharmacy. Nothing is sent anywhere, and no medication details are pre-filled, suggested or derived from ML predictions (an analysis can only be *linked* for reference)
- **Files:** `prescription_service.py` (rules + data, unit-tested), `prescription_pdf.py` (fpdf2), `prescription_ui.py` (shared widgets), `prescription_doctor_pages.py` (doctor pages), `prescription_patient_page.py` (patient **My Prescriptions** tab)
- MongoDB collection `prescriptions`: `prescription_id` (`SIM-RX-YYYYMMDD-XXXXXX`, unique), `patient_id`/`patient_email`/`patient_name`, `doctor_id`/`doctor_email`/`doctor_name`, `analysis_id`, `doctor_note`, `medications[]` (name, dosage, frequency, duration, instructions), `status`, `is_simulated`, timestamps, `void_reason`, `audit_history[]` (action, by, at, details)
- Rules (enforced in the service): new → **draft**; drafts visible/editable/finalizable only by their author; create + finalize require being the patient's current Primary Health Practitioner; **finalized** is read-only; the author can **void** a finalized one with a reason (confirm dialog); voided stays in history; patients see only their own finalized + voided; every create/edit/status change is appended to `audit_history`
- Doctor flow: Patient Overview → **Prescriptions** section (counts) → **View Prescriptions** (`/patient-prescriptions`, filters Draft/Finalized/Voided, View/Edit) → **Create Prescription** / Edit (`/prescription-editor`, add/remove medication rows, Save as draft / Finalize) → detail (`/prescription-detail`, PDF, Finalize/Void, audit history)
- Finalize/void use `ui.components.confirmation_dialog` (keys `rx-finalize-…`, `rx-void-…`); navigation after a dialog goes through `rx_pending_page`
- Doctor-wide list: Clinical workspace > Prescriptions (`prescription_management_page.py`, `list_prescriptions_by_doctor`)

## Appointments
- **Files:** `availability_service.py` (settings, validation, slot generation), `appointment_service.py` (statuses + rules), both unit-tested in `tests/test_appointments.py`; UI in `availability_page.py` (doctor `/availability`), `appointment_doctor_page.py` (doctor `/appointments`), `appointment_patient_page.py` (patient **Appointments** tab), shared widgets in `appointment_ui.py`
- MongoDB `doctor_availability` (one doc per doctor, unique `doctor_email`): `timezone`, `slot_minutes` (15/30/45/60), `break_minutes`, `weekly` {"0".."6" (Mon..Sun): [{start, end} "HH:MM"]}, `blocked` [{start, end "YYYY-MM-DDTHH:MM" doctor-local, reason}]
- MongoDB `appointments`: patient/doctor email+id+name, `start_at`/`end_at` (**naive UTC**), `duration_minutes`, `timezone` (doctor's, used for display), `reason`, `status`, `expires_at`, `reschedule` {proposed_by, start_at, end_at, created_at, expires_at} or null, rejection/cancellation fields, `history` [{action, by, at, details}]
- Statuses: `pending` → `confirmed` | `rejected` | `expired` | `cancelled`; `confirmed` → `completed` | `no_show` (after start) | `cancelled`
- Slots: laid out from each interval start, every duration + break, must end inside the interval; past, blocked and reserved times removed. Booking window 30 days
- Reservations: pending (until `expires_at`) and confirmed appointments, plus pending reschedule proposals. `expires_at` = min(created + 24h, slot start). Expiry is lazy (`expire_stale()` runs on every read/write) — no background job
- Booking rules: only with the patient's current Primary Health Practitioner; future, valid, free slot; reason required; no overlapping active appointments for the patient (any doctor). After inserting, `_lost_race()` re-checks and deletes the later of two simultaneous bookings
- Reschedule: either party, on a future pending/confirmed appointment; original unchanged until the other party accepts; accepting moves the slot (and confirms a pending appointment)
- Pages: patient Book appointment / My appointments; doctor Appointment requests / My appointments / My availability
- Editors use `on_click` callbacks for add/remove rows (not `st.rerun()` mid-page) so every widget is drawn each run and keeps its value

## Page routing
- `app.py` always calls `st.navigation(..., position="hidden")` and picks the pages for the user; `app_pages/sidebar.py` draws the grouped links (Streamlit highlights the current page), profile summary and Log out
- Patient pages: `app_pages/patient_navigation.py`; doctor pages: `app_pages/doctor_navigation.py`. Each has `SIDEBAR_GROUPS`, `page(KEY)` for links/breadcrumbs and `go_to(KEY)` (`st.switch_page`, keeps session state; not callable from `on_click` callbacks)
- Doctor detail pages (patient overview, review analysis, patient prescriptions, editor, detail) are registered but not in the sidebar; they use breadcrumbs
- Signed out, every app URL shows the sign-in screen (no "page not found"); after sign-in the user stays on that URL if their role has it, otherwise goes to their home page
- Reloading the browser starts a new session, so the user must sign in again (auth is session-only)
- `AppTest` renders only the default page per run; set `at._page_hash = calc_hash("<url-path>")` to test another page

## UI design system
- Read `ui/DESIGN.md` before changing any page. Tokens: `.streamlit/config.toml` (IBM Plex Sans, palette, semantic status colours; "violet" is themed teal). CSS: only `ui/theme.py` (keyed `card-*` / `lane-*` containers, `data-testid` hooks)
- Components (`ui/components.py`): `page_header` (+ breadcrumb, returns actions slot), `section_header` (+ provenance badge), `card`, `entity_card`, `field_grid`, `metric_row`, `chart_container`, `form_section`, `status_badge`, `empty_state`, `show_errors`/`error_message`, `flash`/`show_flash`, `confirmation_dialog`/`open_dialog`, `search_and_filter`, `data_table`, `chat_message`
- Provenance: Model output (blue) / Subgroup analysis (teal) / AI explanation (gray) on both the patient results page and the doctor's Review analysis
- New patient pages: Home, Analysis history, Health profile (editable known conditions → `update_known_conditions`), AI assistant (any saved analysis), Profile. New doctor pages: My patients, Patient requests, Doctor's notes (`list_notes_by_doctor`), Prescriptions, AI assistant, Profile

## Notes For Next Agent
- Keep `app.py` thin.
- Do not hardcode symptom/disease/cluster labels; load from pickles/metadata.
- Reuse `PredictionRequest` + `Symptoms.to_feature_vector()` for both predict and cluster assign.
- Page modules live in `app_pages/` (not Streamlit’s reserved `pages/`).
- Medical disclaimer: not a clinical diagnosis tool.
