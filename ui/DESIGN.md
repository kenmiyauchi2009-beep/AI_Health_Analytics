# DeltaAI UI conventions

Design tokens (colours, font, type scale, radii, status colours) live in `.streamlit/config.toml`.
The only custom CSS is `ui/theme.py`, injected once by `app.py`. Pages never add their own CSS.
Building blocks are in `ui/components.py`.

## Page anatomy

```python
actions = page_header(
    "Prescriptions",
    "Simulated prescriptions you have written",          # one line: what this page is for
    breadcrumb=[("My patients", page(MY_PATIENTS)), ("Pat Lee", page(PATIENT_OVERVIEW)), ("Prescriptions", None)],
)
actions.button("Create prescription", type="primary", icon=":material/add:")
show_flash()                                            # messages queued with flash() before a rerun
```

- Breadcrumbs only on pages below a sidebar destination (detail pages). They replace "Back to …" buttons.
- Sections: `section_header(title, description)`. Use `st.tabs` only when the content is genuinely parallel
  (Upcoming / History), not to hide steps of one task.
- Records (an appointment, a patient, a prescription, a note): `entity_card(key, title, subtitle=..., status=(kind, value), fields=[(label, value), ...])`,
  then add actions inside the returned container with `with container:`.
- Other grouped content: `with card(key):`. Do not use `st.container(border=True)`; `card()` gives the white surface.
- Charts and tables: `with chart_container(title, caption, key=...)`, tables via `data_table(rows, column_config=...)`.
- Metrics: `metric_row([(label, value, help), ...])` — only real numbers that help someone decide what to do.
- Empty lists: `empty_state(title, message, key=..., action_label=..., page=page(KEY))` — always offer the next step.
- Validation and failures: `show_errors(errors)` / `error_message(what, how_to_fix)`. Errors never blame the user.
- Destructive or irreversible actions: `open_dialog(key)` on click, and call `confirmation_dialog(key, ...)` every run.

## Analysis results: provenance

Results from different sources are always visually separated and labelled:

| Source | Badge (`section_header(..., badge=)`) | Card lane (`card(key, lane=)`) |
| --- | --- | --- |
| Logistic-regression prediction | `"model"` — Model output, blue | `"model"` |
| K-Means patient subgroup | `"subgroup"` — Subgroup analysis, teal | `"subgroup"` |
| LLM explanation | `"ai"` — AI explanation, gray | `"ai"` |

Teal is used only for subgroup content. Model probabilities are described as "model confidence", never
as certainty, and are always accompanied by the not-a-diagnosis note.

## Status colours

`status_badge(kind, status)` with kinds `appointment`, `prescription`, `connection`, `review`.
Green = done/good, orange = waiting on someone, red = problem/ended badly, blue = scheduled, gray = closed or neutral.
Never use red/green/orange for decoration.

## Copy

- Sentence case everywhere. Buttons start with a verb and say what happens ("Book appointment", not "Submit").
- No emoji in UI text; use Material icons (`icon=":material/…:"`) on buttons and badges where they help scanning.
- No ALL-CAPS labels, no "·"-joined metadata strings (use `fields=` or separate lines), no "←"/"→" in labels.
- Times are shown with their timezone. Prescriptions are always labelled simulated.

## Streamlit notes

- Navigation: `doctor_navigation.page(KEY)` / `patient_navigation.page(KEY)` for links, `go_to(KEY)` to switch.
- Add/remove buttons in editors use `on_click` callbacks, not `st.rerun()` mid-page (widgets not drawn in a run lose state).
- Use `width="stretch"` (not the deprecated `use_container_width`).
