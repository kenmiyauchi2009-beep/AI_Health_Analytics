# Screenshots

This folder holds the screenshots used in the root [README](../../README.md). All 14 screenshots in the checklist below have been added. They were captured from the real app running on fictional demonstration accounts and an in-memory copy of the data, not a real database. To replace one, keep its filename so the README picks up the new image automatically.

## How to add or replace a screenshot

1. Run the app locally (see [Installation](../../README.md#installation-and-local-setup)) and sign in with a **demo account that uses fictional data**.
2. Capture the page at a desktop width (about 1400px wide is ideal). Crop out the browser's address bar and bookmarks.
3. Save it as a PNG in this folder, **using the exact filename from the checklist below**.
4. For a **new** screenshot, add a short caption and an image line to the Application preview section of the root `README.md`:

   ```markdown
   ![Patient home](docs/screenshots/patient-home.png)
   ```

   Replacing an existing file needs no README change.

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
| `login-registration.png` | Sign-in screen (or the sign-up form) | [x] Added |
| `patient-home.png` | Home: upcoming appointment, latest analysis, connected doctor | [x] Added |
| `symptom-selection.png` | New health analysis, step 1: several symptoms selected | [x] Added |
| `disease-prediction.png` | Step 2: model output card and the alternative-predictions chart | [x] Added |
| `patient-subgroup.png` | Step 2: patient subgroup (K-Means cluster) card | [x] Added |
| `ai-assistant.png` | AI explanation section with one answered question | [x] Added |
| `appointment-booking.png` | Book appointment: available time slots for a date | [x] Added |
| `patient-prescriptions.png` | My prescriptions: a finalized simulated prescription | [x] Added |

### Doctor experience

| File | Page to capture | Status |
|---|---|---|
| `doctor-dashboard.png` | Doctor dashboard: requests and analyses waiting for review | [x] Added |
| `patient-overview.png` | Patient overview: profile and analysis history | [x] Added |
| `analysis-review.png` | Review analysis: model output, subgroup, AI assistant and doctor's note | [x] Added |
| `appointment-management.png` | Appointment requests or My appointments | [x] Added |
| `availability.png` | My availability: weekly hours and blocked time | [x] Added |
| `prescription-management.png` | Prescription editor or detail page with audit history | [x] Added |

Mark any new screenshot as `[x] Added` in this table.
