# Business Checker — Setup Guide

This tool checks whether veteran-owned businesses are still actively operating
by searching the web using Perplexity AI. No technical background required.

---

## One-Time Setup (Do This Once)

### Step 1 — Install Python

If Python is not already installed on your computer:

- Go to https://www.python.org/downloads/
- Download the latest version and run the installer
- On Windows: check the box that says "Add Python to PATH" during installation

### Step 2 — Install Required Packages

Open a terminal (Mac: Spotlight → Terminal, Windows: Start → Command Prompt),
navigate to this folder, and run:

```
pip install -r requirements.txt
```

This installs everything the tool needs. You only do this once.

### Step 3 — Get a Perplexity API Key

1. Go to https://www.perplexity.ai/settings/api
2. Sign up or log in
3. Click "Generate API Key"
4. Copy the key (it starts with `pplx-`)

### Step 4 — Add Your API Key

1. Find the file called `.env.example` in this folder
2. Make a copy of it and name the copy `.env` (no ".example")
3. Open `.env` in any text editor (Notepad on Windows, TextEdit on Mac)
4. Replace `your-key-here` with your actual key:
   ```
   PERPLEXITY_API_KEY=pplx-abc123yourkeyhere
   ```
5. Save and close the file

---

## Running the Tool

### Option A — Desktop App (Recommended for most users)

Double-click `business_checker_gui.py` to open the app.

If double-clicking doesn't work, right-click → "Open With" → Python.

**What to do in the app:**
1. Your API key will load automatically from `.env`
2. Click **Test Key** to verify it works before starting
3. Click **New Run** and browse to your Excel file
4. Confirm the column mapping (the tool auto-detects name, city, state, website)
5. Choose a worker count (start with 1 if your account is new)
6. Click **Confirm & Start**
7. Watch live results in the log window
8. When complete, click **Export Results** to save the output Excel file

**Pausing and resuming:**
- Click **Pause** at any time — progress is saved automatically
- Click **Resume Run** to continue from where you left off
- If the program closes unexpectedly, just re-open and use **Resume Run**

### Option B — Command Line (For large unattended runs)

Open a terminal in this folder and run:

```
python run_checker.py --input your_file.xlsx --workers 3
```

The program will run automatically and save results to a new folder inside `Runs/`.
Press Ctrl+C to stop early — progress is saved and you can resume later.

---

## Worker Count Guide

The number of workers controls how many businesses are checked at once.
More workers = faster, but requires a higher Perplexity account tier.

| Workers | Speed | Perplexity Tier Required |
|---------|-------|--------------------------|
| 1       | Slower | Tier 0 (new accounts — free) |
| 3       | 3x faster | Tier 1 (after initial spending) |
| 8       | 8x faster | Tier 2 |

Check your tier at: https://www.perplexity.ai/settings/api

**When in doubt, start with 1 worker.** The tool will retry automatically if
rate limit errors occur.

---

## Output

Results are saved in the `Runs/` folder. Each run gets its own subfolder:

```
Runs/
└── YourFile_2026-03-17_1430/
    ├── YourFile.xlsx              (copy of your original input)
    ├── checkpoint.csv             (progress saved here — don't delete)
    ├── run.log                    (full log of the run)
    └── YourFile_Results.xlsx      (final output — created on Export)
```

The Results file has your original columns plus four new ones:

| Column | What it means |
|--------|---------------|
| AI_Status | Active / Likely Closed / Uncertain / No Web Presence |
| AI_Confidence | How confident the AI is (0–100) |
| AI_Evidence | What the AI found and where |
| AI_Checked_At | When the check was run |

---

## Cost Estimate

Approximately **$0.005–0.008 per business** using Perplexity's sonar model.

| Records | Estimated Cost |
|---------|----------------|
| 100     | ~$0.80         |
| 709     | ~$5–6          |
| 5,000   | ~$35–40        |
| 20,000  | ~$100–160      |

---

## Troubleshooting

**"Missing Dependencies" error on launch:**
Open a terminal in this folder and run: `pip install -r requirements.txt`

**"PERPLEXITY_API_KEY not found" error:**
Make sure you created a `.env` file (not `.env.example`) with your key inside.

**Rate limit errors (429):**
Reduce your worker count. The tool retries automatically, but fewer workers
will prevent the errors from happening in the first place.

**Tool stopped mid-run:**
No problem — use **Resume Run** in the GUI or re-run the same command in the
terminal. It picks up from where it left off.

**Results file won't export (file in use):**
Close the Results file in Excel first, then click Export again.
