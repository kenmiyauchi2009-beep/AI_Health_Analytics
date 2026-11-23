# Screenshots

This folder holds the screenshots used in the root [README](../../README.md). The README already has a reference for every file listed below. Each reference is commented out until its image exists, so the README never shows a broken image.

## How to add a screenshot

1. Run the app locally (see [Installation](../../README.md#installation-and-local-setup)) and sign in with a **demo account that uses fictional data**.
2. Capture the page at a desktop width (about 1400px wide is ideal). Crop out the browser's address bar and bookmarks.
3. Save it as a PNG in this folder, **using the exact filename from the checklist below**.
4. In the root `README.md`, find the matching commented-out line, for example:

   ```markdown
   <!-- ![Patient home](docs/screenshots/patient-home.png) -->
   ```

   and remove the `<!--` and `-->` so it becomes:

   ```markdown
   ![Patient home](docs/screenshots/patient-home.png)
   ```

5. Check the README preview on GitHub to confirm the image shows.

## Privacy rules

Every screenshot will be public. Before saving one, check that it contains:

- **Only fictional people.** Use made-up names and emails such as `demo.patient@example.com`. Never use real patient information.
- **No credentials.** Make sure no MongoDB connection string, Groq API key or password appears anywhere, including in error messages or the terminal.
- **No personal email addresses** in the sidebar profile or the sign-in form.

## Naming conventions

- Lowercase words separated by hyphens: `appointment-booking.png`, not `Appointment Booking.png`.
- Name the file after the page or feature it shows, not the date it was taken.
- PNG format.

## Screenshot checklist

### Patient experience

| File | Page to capture | Status |
|---|---|---|
| `login-registration.png` | Sign-in screen (or the sign-up form) | [ ] Needed |
| `patient-home.png` | Home: upcoming appointment, latest analysis, connected doctor | [ ] Needed |
| `symptom-selection.png` | New health analysis, step 1: several symptoms selected | [ ] Needed |
| `disease-prediction.png` | Step 2: model output card and the alternative-predictions chart | [ ] Needed |
| `patient-subgroup.png` | Step 2: patient subgroup (K-Means cluster) card | [ ] Needed |
| `ai-assistant.png` | AI explanation section with one answered question | [ ] Needed |
| `appointment-booking.png` | Book appointment: available time slots for a date | [ ] Needed |
| `patient-prescriptions.png` | My prescriptions: a finalized simulated prescription | [ ] Needed |

### Doctor experience

| File | Page to capture | Status |
|---|---|---|
| `doctor-dashboard.png` | Doctor dashboard: requests and analyses waiting for review | [ ] Needed |
| `patient-overview.png` | Patient overview: profile and analysis history | [ ] Needed |
| `analysis-review.png` | Review analysis: model output, subgroup, AI assistant and doctor's note | [ ] Needed |
| `appointment-management.png` | Appointment requests or My appointments | [ ] Needed |
| `availability.png` | My availability: weekly hours and blocked time | [ ] Needed |
| `prescription-management.png` | Prescription editor or detail page with audit history | [ ] Needed |

After adding a screenshot, change its status here to `[x] Added`.
