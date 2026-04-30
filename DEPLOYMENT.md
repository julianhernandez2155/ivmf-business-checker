# Deployment Guide — IVMF Business Checker Web App

## Overview

This guide covers converting the business checker from a local Python/Tkinter app into a web app deployed on Railway. Colleagues will be able to upload an Excel file, monitor progress, and download results — no local setup required.

**Why Railway, not Vercel:** The batch job takes hours. Vercel serverless functions time out per invocation. Railway runs a persistent server that won't kill a long-running process.

---

## Architecture

```
Browser
  └─ Upload Excel file
  └─ Submit job (POST /run)
  └─ Poll progress (GET /status/<job_id>)
  └─ Download results (GET /download/<job_id>)

Railway Server (FastAPI)
  └─ Receives upload → saves file to disk
  └─ Spawns background thread → runs existing run_checker logic
  └─ Writes checkpoint.csv as before
  └─ Serves results .xlsx when done
```

The existing `tools/` and `run_checker.py` logic stays completely unchanged. You're adding a thin web layer on top.

---

## What Needs to Be Built

### 1. FastAPI web server (`web_app.py`)

Endpoints:
- `POST /run` — accepts file upload + worker count, starts background job, returns `job_id`
- `GET /status/<job_id>` — returns progress (checked / total, status counts, estimated cost)
- `GET /download/<job_id>` — returns the output `.xlsx` when the job is complete
- `GET /` — serves a basic HTML upload form

Job state stored in memory (a dict keyed by `job_id`). Good enough for one-at-a-time internal use. No database needed.

### 2. Simple HTML frontend (one file, no framework)

- File upload form (Excel only)
- Worker count selector (1/3/8 with Perplexity tier labels)
- Progress bar that polls `/status/<job_id>` every 5 seconds
- Download button that appears when status is `complete`

### 3. Railway configuration

- `Procfile` or `railway.json` pointing to the FastAPI server
- Environment variable: `PERPLEXITY_API_KEY` set in Railway dashboard
- Python 3.11+ runtime

---

## Step-by-Step Deployment

### Prerequisites

- Railway account at [railway.app](https://railway.app) (free tier works)
- Railway CLI: `npm install -g @railway/cli`
- This repo pushed to GitHub

### 1. Create the Railway project

```bash
railway login
railway init
# Select "Empty Project" when prompted
```

### 2. Set the environment variable

In the Railway dashboard, go to your service → Variables:

```
PERPLEXITY_API_KEY = your_key_here
```

Or via CLI:
```bash
railway variables set PERPLEXITY_API_KEY=your_key_here
```

Never commit the key. The `.env` file is for local dev only.

### 3. Add a Procfile

Create `Procfile` in the project root (same level as `requirements.txt`):

```
web: uvicorn web_app:app --host 0.0.0.0 --port $PORT
```

Railway injects `$PORT` automatically.

### 4. Update requirements.txt

Add the web server dependencies:

```
fastapi>=0.110.0
uvicorn>=0.27.0
python-multipart>=0.0.9
```

### 5. Deploy

```bash
railway up
```

Railway detects Python, installs `requirements.txt`, and starts the server. On first deploy it takes ~2 minutes. Subsequent deploys are faster.

Your app URL will be something like `https://your-project.up.railway.app`.

---

## File Storage

Uploaded files and run output are stored in `/tmp` on the Railway instance. This is ephemeral — files are lost on redeploy or restart. That's fine for this use case since:

1. The job runs start-to-finish in one session
2. Results are downloaded immediately after completion
3. The checkpoint system already handles interrupted runs

If you ever need persistent storage (e.g., resuming a job after a server restart), Railway supports volumes for $0.25/GB/month. Not needed for v1.

---

## Access Control

The current design has no authentication. Anyone with the URL can use it.

For IVMF internal use, options in order of complexity:

| Option | Effort | Notes |
|--------|--------|-------|
| Share URL only within IVMF | Zero | Fine if the URL is not public-facing |
| HTTP Basic Auth via Railway | Low | Set `BASIC_AUTH_USER` + `BASIC_AUTH_PASS` env vars, add middleware in FastAPI |
| Railway private networking | Medium | Requires VPN or Railway team plan |

For v1, sharing the URL privately is probably enough.

---

## Cost

| Item | Cost |
|------|------|
| Railway Hobby plan | $5/month |
| Compute (1 vCPU / 512 MB RAM) | ~$5–10/month depending on run frequency |
| Perplexity API | Separate — same cost as running locally |

Railway's free tier (Starter) has a $5 credit/month and sleeps after 30 days of inactivity. Fine for occasional internal use.

---

## Local Development

Before deploying, test the web app locally:

```bash
cd business_checker
uvicorn web_app:app --reload --port 8000
```

Open `http://localhost:8000`. The `.env` file will be picked up automatically via `python-dotenv`.

---

## What Stays the Same

Everything in `tools/` is unchanged. The checkpoint system, the Perplexity API calls, the Excel output format — all identical. Railway just provides the always-on server that lets colleagues trigger runs without needing Python installed locally.
