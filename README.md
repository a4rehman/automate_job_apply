# AI Job Application Automation Agent

An enterprise-grade, TOS-compliant autonomous AI agent that discovers, matches,
analyzes, and **prepares** tailored job applications with a strict
**human-in-the-loop approval gate**. It never fabricates submissions and runs
safe dry-run cycles by default.

---

## 🌟 Key Capabilities

1. **Job Discovery Engine** — Multi-source RSS/API adapters (WeWorkRemotely,
   Remotive, Arbeitnow), CSV & manual import, email alert parsing. RemoteOK was
   removed after its feed was verified to return HTTP 410 Gone. Cryptographic
   description hashing + URL normalization dedupe across all providers, backed
   by partial and unique DB constraints so dedupe cannot be bypassed by a
   concurrent worker. `JobSourceConfig` rows back each source (with per-source
   health, rate-limit, and enable gating seeded at startup).
2. **AI Semantic Matching** — Parse PDF/DOCX resumes, verify skills, and produce a
   transparent 0–100 composite match score (skills coverage + experience + role fit).
   LLM abstraction (OpenAI-compatible / Ollama / vLLM / Anthropic) with an offline
   mock fallback so the whole pipeline runs without a live key.
3. **Application Package Synthesis (Human-In-The-Loop)** — AI-tailored resume bullets,
   bespoke cover letters, and screening Q&A drafts. Applications sit at
   `PENDING_APPROVAL` until a human reviews, edits, and explicitly approves.
4. **Background Automation & Scheduler** — An **hourly worker** (GitHub Actions,
   Asia/Karachi, `Asia/Karachi` timezone) runs a full cycle: discover → analyze →
   match gate → prepare → (dry-run submit). Database run-locking, per-run/daily
   limits, idempotency keys, and audit logging keep it safe and idempotent.
5. **Dashboard & Analytics** — Streamlit dashboard with live KPIs, job board,
   application review, automation settings, run history, and a manual "Run Cycle
   Now" trigger.

---

## 🏗️ Architecture

```
┌──────────────────────┐         ┌──────────────────────────────┐
│ GitHub Actions        │         │ Streamlit Cloud              │
│ hourly worker         │         │ dashboard (app.py)           │
│ (job discovery, AI    │         │ reads/writes same database   │
│  analysis, prepare)   │         └──────────────┬───────────────┘
└───────────┬───────────┘                        │
            │ polls RSS/API/CSV feeds            │
            ▼                                    ▼
      ┌──────────────────────────────────────────────┐
      │ Supabase PostgreSQL (jobs, apps, settings,   │
      │ scheduler_runs, notifications, audit)        │
      └──────────────────────────────────────────────┘
```

The worker runs **independently** of Streamlit: GitHub Actions runs the cycle
hourly (Asia/Karachi), and the Streamlit dashboard reads the shared database.

---

## 🚀 Local Setup

### 1. Backend + Worker

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
Copy-Item ..\.env.example .env    # Windows  |  cp ../.env.example .env  (Linux)

# Create tables, sync source configs, and seed demo data (demo@jobagent.ai / demo1234)
python -m app.seed

# Run a full automation cycle in DRY RUN (safe; no real submissions)
python -m app.workers.hourly_runner
```

### 2. Run the API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000    # interactive docs at http://localhost:8000/docs
```

### 3. Run the Streamlit dashboard

```bash
pip install -r requirements.txt   # root requirements.txt includes Streamlit
streamlit run app.py              # opens on http://localhost:8501
```

> Note: `backend/requirements.txt` covers the API + worker. The **root**
> `requirements.txt` covers Streamlit Cloud. Run the pipeline with `python -c
> "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"`
> first if your `DATABASE_URL` is PostgreSQL.

---

## 🧪 Tests

```bash
cd backend
python -m pytest tests -q
```

The suite covers pipeline idempotency (run locking, stale-lock recovery), URL/description
dedup hashing, semantic matching fallback (AI failure ⇒ score 0.0, never 85), skill/role/
experience scoring edge cases, daily-limit enforcement, dry-run `WOULD_SUBMIT` behavior,
per-source failure isolation, source config sync/gating, and the user-email
(pipeline reads email from `User`, not `UserProfile`) regression.

---

## ☁️ Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the full production guide: Supabase
setup, GitHub secrets, the hourly GitHub Actions workflow, Streamlit Cloud
deployment, and the `DRY_RUN` safety model.

---

## 🛡️ TOS & Ethical Compliance

1. **No CAPTCHA / anti-bot evasion**: The agent never bypasses CAPTCHAs, bot
   detection, or unauthorized scraping.
2. **Human-in-the-loop**: Applications are prepared as drafts and require explicit
   human approval before any submission.
3. **Safe by default**: `DRY_RUN=true` is the default; no real application is
   ever submitted without a human explicitly approving and enabling it.
4. **Open standards**: Uses public RSS/API feeds, permissive job portals, and
   direct file imports.
