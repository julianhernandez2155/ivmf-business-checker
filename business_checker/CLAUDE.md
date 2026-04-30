# Agent Instructions — IVMF Business Checker

## Architecture: WAT Framework

This project follows the WAT pattern: **Workflows → Agent → Tools**

- `workflows/` — Markdown SOPs defining what to do, how to handle edge cases, and what's been learned
- Agent (Claude) — reads the workflow, coordinates execution, handles failures
- `tools/` — Python scripts that do deterministic execution (API calls, file I/O)

---

## Project Layout

```
business_checker/
├── tools/
│   ├── check_business.py    # Perplexity sonar API call — single business
│   ├── checkpoint.py        # CSV checkpoint read/write (thread-safe)
│   └── build_output.py      # Excel output assembly
├── workflows/
│   └── check_business_status.md   # Full SOP for this tool
├── business_checker_gui.py  # Tkinter GUI — thin shell over tools/
├── run_checker.py           # Headless concurrent runner for large batches
├── archive/                 # Old versions (do not delete)
├── Runs/                    # Run output folders (auto-created)
├── .env                     # PERPLEXITY_API_KEY (never commit this)
├── .env.example             # Template — commit this, not .env
├── requirements.txt         # pip dependencies
└── SETUP.md                 # Plain-English setup guide for non-technical users
```

---

## How to Operate

### Before coding anything new:
1. Read the relevant workflow in `workflows/`
2. Check `tools/` for existing functions before writing new ones
3. Keep business logic in `tools/` — not in the GUI or runner

### Key tools and what they do:

| Tool | Function | Notes |
|------|----------|-------|
| `tools/check_business.py` | `check_business(api_key, name, website, city, state)` | Calls Perplexity sonar, returns structured dict |
| `tools/checkpoint.py` | `load_checkpoint`, `save_checkpoint`, `rewrite_checkpoint`, `get_run_summary` | Thread-safe, shared by GUI and runner |
| `tools/build_output.py` | `build_output_excel(input_path, output_path, checkpoint_path)` | Uses openpyxl read_only mode |

### Running the tool standalone (for testing):
```bash
python -m tools.check_business
```
(Must use the `-m` form — running `python tools/check_business.py` directly
fails because the script imports from the `tools` package.)

### Running a batch (headless):
```bash
python run_checker.py --input file.xlsx --workers 3
```

### Rate limits (Perplexity sonar):
- Tier 0 (new): 1 QPS → use `--workers 1`
- Tier 1: 3 QPS → use `--workers 3`
- Tier 2: 8 QPS → use `--workers 8`

---

## When Things Fail

1. Read the full error message and traceback
2. Fix the script — do not retry a paid API call without diagnosing first
3. Update `workflows/check_business_status.md` with what you learned
4. If a checkpoint is corrupted, `tools/checkpoint.py` has `rewrite_checkpoint()` to rebuild it

## The .env File

`PERPLEXITY_API_KEY` lives in `.env`. Never hard-code it. Never commit it.
`.env.example` is the committed template — it contains the key name but not the value.

## Archives

Old versions are in `archive/`. Never delete them.
