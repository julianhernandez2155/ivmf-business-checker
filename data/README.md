# Data

Input spreadsheets for the Business Checker live here. **No data files are committed** — `.xlsx` is gitignored by the root `.gitignore`.

## Files expected here (locally)

- `BMOSG_All_Businesses.xlsx` — IVMF's 709-row veteran-owned business dataset (internal IVMF property, do not commit or share).
- Any other input spreadsheets you want to process.

## Usage

```bash
cd business_checker
python run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 3
```

Output runs land under `business_checker/Runs/` (also gitignored).

## Why a separate folder

Codex review #1 (`docs/codex-review-1-architecture.md`) flagged having real workbook files inside the source tree as a "working folder, not a controlled product" signal. Keeping inputs in `data/` keeps the application directory clean.
