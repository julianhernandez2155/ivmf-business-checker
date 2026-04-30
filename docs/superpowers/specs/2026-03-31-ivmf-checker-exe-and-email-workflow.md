# IVMF Business Checker — EXE Distribution + Email Notification Workflow

**Date:** 2026-03-31  
**Status:** Approved, ready for implementation planning  
**Author:** Julian Hernandez

---

## Overview

Two improvements to the IVMF Business Checker:

1. **EXE Distribution** — Package the existing Flask web dashboard as a standalone executable (Windows + Mac) so non-technical teams can run it without installing Python or dealing with a server.
2. **Email Notification Workflow** — A separate script that reads a completed run's results Excel and sends personalized emails via Microsoft Graph API to businesses flagged as Likely Closed or Uncertain, giving them 30 days to submit updated information.

These are independent — either can be built without the other.

---

## Part 1: EXE Distribution

### Context

The Business Checker is currently a Flask web app (`business_checker_app.py`) with a real-time SSE dashboard. It works well locally. The goal is to package it so any IVMF team (Alumni, BMOSG, etc.) can double-click and run it — no Python, no setup, no server. Each team manages their own Perplexity account and API key.

Usage pattern: quarterly or yearly, one team at a time, one batch per run.

### Distribution Model

PyInstaller bundles the entire app — Python runtime, Flask, pywebview, all dependencies, and the HTML template — into a self-contained executable. The user receives a folder:

```
BusinessChecker/
├── BusinessChecker.exe   (Windows)  or  BusinessChecker.app  (Mac)
├── Runs/                 (auto-created on first run, holds all run folders)
└── README_QUICKSTART.txt (one-page setup guide, written for non-technical users)
```

Two separate builds: `.exe` for Windows (team distribution), `.app` for Mac (Julian's dev machine). Both built from the same codebase via PyInstaller with platform-specific spec files. Windows build must be done on a Windows machine (PyInstaller cannot cross-compile).

### Native Window (pywebview)

The app opens in a native OS window, not a browser. `pywebview` creates a proper desktop window using the platform's built-in web engine (WebView2 on Windows, WebKit on Mac). No browser chrome, no URL bar, no tabs — looks and feels like a regular desktop application.

Entry point (`main.py`):
1. Starts Flask on `localhost:5001` in a background thread
2. Opens a `pywebview` window pointed at that address
3. When the window closes, the Flask server shuts down cleanly

Flask's `template_folder` must be patched for PyInstaller: at runtime, check for `sys._MEIPASS` (PyInstaller's temp extraction folder) and set the template/static paths accordingly.

### Known Packaging Risks

| Risk | Mitigation |
|------|------------|
| **Windows Defender / AV false positive** | PyInstaller exes commonly trigger enterprise AV. IVMF IT may need to whitelist the folder. Code signing is the long-term fix but not in v1 scope. |
| **Flask template path in bundle** | Must detect `sys._MEIPASS` and set `template_folder` / `static_folder` at app init. Without this, the app crashes on launch. |
| **Port conflict on user's machine** | If port 5001 is occupied, fall back to a random available port. Pass the port to pywebview's URL. |

### API Key

Keep the existing key input UI as-is. User opens the app, enters their Perplexity API key once. No `config.env` file needed. The key is stored in app memory for the session — on next launch they enter it again (or we can add a "save key" option later if teams ask for it).

### Run Management UX Improvements

The existing run system already auto-names runs from the spreadsheet name + timestamp (e.g., `MWBE_Certified_Businesses_2026-03-23_1327`). These targeted improvements make it more readable for non-technical users:

**1. Display label on run start**  
When starting a new run, the user can optionally enter a short display label (e.g., "Alumni Q1 2026"). If left blank, the auto-generated name is used as the display label. Stored in `run_meta.json` inside the run folder alongside `checkpoint.csv`.

```json
{
  "display_label": "Alumni Q1 2026",
  "auto_name": "MWBE_Certified_Businesses_2026-03-23_1327",
  "started_at": "2026-03-23T13:27:00",
  "total_rows": 141
}
```

**2. Run cards show progress**  
The Runs page lists each run with:
- Display label (or auto-name if no label set)
- Date started
- `85 / 141 rows (60%)` — checked count from `get_run_summary()`, total from `run_meta.json`

Note: `total_rows` must be written to `run_meta.json` at run creation time. `get_run_summary()` returns status counts but not total rows, and the input Excel isn't re-read for the run list.

**3. "Progress saved" banner**  
During an active run, a persistent banner reads:  
> "Progress is saved automatically after every row. Safe to close this window — resume your run anytime from the Runs page."

This removes the anxiety for non-technical users about losing work mid-session.

### What Does NOT Change

- The core checking logic (`tools/check_business.py`, `tools/checkpoint.py`, `tools/build_output.py`) is untouched
- The SSE streaming dashboard, pause/stop/resume, retry-failed, and export flows are unchanged
- The existing auto-naming scheme stays — display labels are additive, not a replacement

### Open Questions

- ~~**Windows-only or also Mac installer?**~~ Both builds needed (confirmed: Windows for teams, Mac for Julian)
- **Save key between sessions?** Not in scope for v1 — revisit if teams ask
- **AV whitelisting:** Check with IVMF IT whether unsigned PyInstaller exes can run on team machines, or if they need to whitelist the folder

---

## Part 2: Email Notification Workflow

### Context

After a completed run, some businesses are flagged as `Likely Closed` or `Uncertain`. Rather than silently removing them from the database, IVMF wants to notify each flagged business by email, give them 30 days to submit updated information, and only remove/update records after that window.

This is a **separate standalone script** — not part of the Business Checker EXE. It runs after a results Excel is produced.

### Tool Location

```
business_checker/
├── email_notifier/
│   ├── notify.py                  # Main script
│   ├── email_template.txt         # Plain-text email body template
│   ├── requirements.txt           # graph SDK, openpyxl, python-dotenv
│   └── .env.example               # AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET, SENDER_EMAIL, FORM_URL
└── workflows/
    └── notify_closed_businesses.md  # SOP for running the notifier
```

### How It Works

1. User provides the path to a completed `_Results.xlsx` file
2. Script reads all rows where `AI_Status` is `Likely Closed` or `Uncertain`
3. For each business with a valid email address, sends a personalized email via Microsoft Graph API
4. Businesses with no email address are logged as `NO_EMAIL` and skipped
5. Outputs a `notifications_log.csv` in the same folder as the results file

**Run command:**
```bash
python email_notifier/notify.py --results "Runs/MWBE_Certified_Businesses_2026-03-23_1327/MWBE_Certified_Businesses_Results.xlsx"
```

### Email

**Subject:** `Action Required: [Business Name] — IVMF Veteran Business Database`

**Body (template):**
```
Dear [Business Name],

Our records indicate that your business, [Business Name] ([City], [State]),
may no longer be operating or could not be verified through our standard review.

We want to make sure your information is accurate before making any changes
to the IVMF Veteran Business Database. If your business is still active,
please submit updated information using the link below within 30 days of
receiving this email ([Deadline Date]).

Submit updated information: [FORM_URL]

If we do not hear from you by [Deadline Date], your record may be removed
or marked inactive in our database.

Thank you for your continued service.

[Sender Name / IVMF]
```

Deadline date is calculated as `sent_date + 30 days`, formatted as `April 30, 2026`.

### Email Sending: Microsoft Graph API

Uses the Microsoft Graph `sendMail` endpoint with OAuth 2.0 client credentials flow (app-only auth). Requires a one-time Azure app registration with `Mail.Send` permission scoped to the sending mailbox.

Environment variables (in `email_notifier/.env`):
```
AZURE_CLIENT_ID=...
AZURE_TENANT_ID=...
AZURE_CLIENT_SECRET=...
SENDER_EMAIL=noreply@ivmf.syr.edu   # or Jim's address — TBD
FORM_URL=https://forms.office.com/... # TBD
```

### Output: notifications_log.csv

One row per business that was processed:

| Column | Description |
|--------|-------------|
| `Business_Name` | Business name from results file |
| `City` | City |
| `State` | State |
| `AI_Status` | Likely Closed or Uncertain |
| `Email` | Email address used (or blank) |
| `Notification_Status` | `SENT`, `NO_EMAIL`, `ERROR` |
| `Sent_At` | Timestamp |
| `Deadline_Date` | 30 days from sent timestamp |

This log is designed to be Salesforce-importable: standard column names, clean dates, one row per business. Manual import for now; automated sync can be added later.

### What This Tool Does NOT Do

- No automatic follow-up after 30 days (manual process)
- No direct Salesforce write (log is designed for easy manual import)
- No re-verification of businesses after they respond
- No form handling or response collection (form system is external)

### Open Questions — Confirm with Jim Before Building

These must be answered before implementation starts:

| Question | Why it matters |
|----------|---------------|
| Do the spreadsheets have a business email address column? | If not, the workflow cannot send anything — this is a hard blocker |
| What email address sends from? Jim's? A shared `noreply@`? | Determines Azure app registration scope |
| What is the form URL / form system? | Template needs a real link; IVMF may have their own system |
| What Salesforce fields map to which form fields? | Needed to design the form for clean import |

---

## What Is Out of Scope (Both Parts)

- Web deployment / Railway hosting (replaced by EXE model)
- Automated Salesforce integration (manual import from CSV for now)
- Multi-user / concurrent access (one team, one machine at a time)
- Automatic 30-day follow-up emails
- A help manual / user guide (noted as future addition)
