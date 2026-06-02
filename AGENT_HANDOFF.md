# DeltaAI Agent Handoff

## Project Goal
Build a beginner-friendly Streamlit Bio Explorer dashboard with clear separation of concerns, upload-first flow, and easy future extension.

## Current Status
- Virtual environment `venv` was created.
- Dependencies were installed (`streamlit`, `pandas`, `numpy`, `matplotlib`, `seaborn`).
- `requirements.txt` exists and is populated from `pip freeze`.
- App has been refactored so `app.py` only orchestrates pages.
- Dashboard logic now lives in a dedicated page module and supporting service/view modules.

## Architecture (Current)

### 1) App-level orchestration
- **File:** `app.py`
- **Responsibility:** Route/orchestrate between pages only.
- **Behavior:** Uses sidebar navigation and defaults to `Dashboard` on load.

### 2) Dashboard page (feature orchestration)
- **File:** `pages/dashboard_page.py`
- **Responsibility:** Coordinate dashboard flow:
  - upload CSV
  - load dataframe safely
  - detect column types
  - render controls
  - apply filters
  - show metrics and plots

### 3) Data/service layer
- **File:** `dashboard/data_service.py`
- **Responsibility:**
  - `load_uploaded_csv(uploaded_file)` with safe error return
  - `detect_columns(df)` for numeric/categorical detection
  - `apply_categorical_filter(df, selected_cat_col, selected_values)` for safe filtering

### 4) UI view layer
- **File:** `dashboard/ui_view.py`
- **Responsibility:**
  - page header and uploader
  - dataset preview and size metrics
  - sidebar controls
  - guardrail warnings
  - summary metrics

### 5) Plot rendering layer
- **File:** `dashboard/plots_view.py`
- **Responsibility:**
  - count plot
  - boxplot
  - scatter plot
  - interpretation notes/captions under each chart

## Implemented Functional Requirements
- Upload-first behavior (no default dataset auto-load).
- Dataset preview, row count, column count.
- Auto-detection of numeric and categorical columns.
- Sidebar controls for:
  - categorical group/filter column
  - numeric column for boxplot + average metric
  - numeric x/y for scatter
- Categorical value filtering.
- Summary metrics after filtering:
  - total filtered rows
  - average of selected numeric column
- Visualizations:
  - count plot (categorical)
  - boxplot (numeric by categorical)
  - scatter plot (numeric x vs y)
- Guardrails:
  - warnings when numeric/categorical columns are missing
  - safe checks for missing/invalid columns
  - safe behavior on empty filtered results

## How To Run
From project root:

```bash
source venv/bin/activate
streamlit run app.py
```

Windows PowerShell equivalent:

```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

## Notes For Next Agent
- Keep `app.py` thin (page orchestration only).
- Add new pages under `pages/` and register them in `app.py`.
- Keep data logic in `dashboard/data_service.py`.
- Keep rendering/UI in view modules (`ui_view.py`, `plots_view.py`).
- Maintain beginner-readable style and explicit guardrails.

## Suggested Next Steps
1. Add at least one extra page (e.g., `About`, `Data Dictionary`, or `Insights`).
2. Add lightweight tests for service functions in `dashboard/data_service.py`.
3. Optionally simplify `requirements.txt` to top-level packages if desired.
4. Commit current work once ready.

## Git Snapshot Context
- Repository currently appears to be in an initial state with uncommitted files.
- Recent work includes creating and refactoring:
  - `app.py`
  - `dashboard/`
  - `pages/`
  - `requirements.txt`
