# Deployment Guide

Production topology:

```
GitHub Actions (hourly cron)
        |
        v
  hourly_runner  --->  Supabase PostgreSQL  <---  Streamlit Community Cloud
   (migrate + cycle)        (shared data)             (dashboard + approvals)
        |
        +--> job sources / AI (Gemini) / SMTP / Telegram
```

The worker never runs inside Streamlit. Streamlit is a read/write dashboard
over the same database and can be restarted at any time without affecting
scheduling.

---

## A. Supabase Database

1. Create a project at <https://supabase.com>.
2. **Settings → Database → Connection string → URI**. Copy the string and
   replace the password placeholder. Use the Session Pooler (port 5432) for
   the worker, or the Transaction Pooler (port 6543) for the app.
3. Set `DATABASE_URL` to that value. A plain `postgresql://` URL is
   automatically rewritten to `postgresql+asyncpg://` at runtime.
4. Keep `DB_SSL_MODE=require`.

### Schema setup

The worker applies the schema and then runs idempotent migrations:

```bash
cd backend
python -m app.workers.hourly_runner --migrate-only
```

This runs `Base.metadata.create_all` (creates any missing tables) and then
applies every migration in `app/core/database.py` that has not been recorded
in the `schema_migrations` table. Migrations add columns and unique indexes
that `create_all` cannot add to an existing table, so it is safe to re-run on
every deploy. A failure aborts and rolls back rather than leaving a
half-applied schema.

### Backups

Supabase provides daily backups on paid plans. Because the schema evolves
through migrations, take a logical dump before your first production cycle:

```bash
pg_dump "$DATABASE_URL" > backup-$(date +%F).sql
```

---

## B. GitHub Actions (Hourly Worker)

Workflow: `.github/workflows/hourly-job-automation.yml`

- Schedule: `'5 * * * *'` (hourly at minute 5)
- `workflow_dispatch` for manual runs
- `concurrency` group `hourly-job-automation` with `cancel-in-progress: false`,
  so a slow cycle is never interrupted mid-write
- Exit codes: `0` success/skipped, `1` failed, `2` partial success
  (some work succeeded, some failed — the run is flagged but data is kept)

### Repository secrets (Settings → Secrets and variables → Actions)

| Secret | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | Supabase connection string |
| `SECRET_KEY` | yes | JWT/session signing |
| `AUTO_SUBMIT_ENABLED` | no | Master submission switch, keep `false` |
| `DRY_RUN` | no | Defaults to `true` in the workflow |
| `DB_SSL_MODE` | no | Defaults to `require` |
| `GEMINI_API_KEY` | no | Enables real AI analysis |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | no | Alternative AI provider |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | no | Email applications + alerts |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | no | Telegram alerts |

Run it once from the Actions tab to confirm the secrets resolve and the cycle
completes before relying on the schedule.

---

## C. Streamlit Community Cloud

1. Deploy from the repository, entrypoint `app.py`.
2. Add app secrets under **Settings → Secrets**: `DATABASE_URL`, `SECRET_KEY`,
   plus `GEMINI_API_KEY` and any notification credentials you use.
3. Click **Deploy**. The dashboard reads the same Supabase database.

The dashboard is not required for automation to run, and the worker is not
required for the dashboard to work.

---

## D. Telegram Notifications (Optional)

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Message the bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat.id`.
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in both Streamlit secrets
   and GitHub Actions secrets.
4. Enable the channel in the user's automation settings.

If Telegram is unreachable the cycle continues; the failure is logged and
surfaced in the dashboard's source/health panel rather than crashing the run.

---

## E. Local Development

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r ..\requirements.txt      # Streamlit dashboard

Copy-Item ..\.env.example ..\.env
python -m app.seed                       # demo user + sample jobs
python -m app.workers.hourly_runner      # dry-run cycle
streamlit run ..\app.py
```

Demo credentials: `demo@jobagent.ai` / `demo1234` (development only).

Run the tests with:

```powershell
cd backend
python -m pytest tests -q
```

---

## F. Safety Model

The system is designed to fail closed:

- `AUTO_SUBMIT_ENABLED=false` (default) blocks every real submission. The
  worker also refuses to start with `--live` while it is false.
- `DRY_RUN=true` (default) means cycles only prepare applications and request
  human review.
- `REQUIRE_HUMAN_APPROVAL=true` keeps the human in the loop.
- An unsupported source never fabricates a submission; it transitions the
  application to `NEEDS_ACTION` with instructions.
- Email and API executors write an `OutboundEmail` audit record even in dry
  run (`status=DRY_RUN_NOT_SENT`, `sent_at` NULL) so you can review exactly
  what would have gone out.
- No source or model can bypass CAPTCHA, authentication walls, or anti-bot
  protections. LinkedIn, Indeed, Glassdoor and Wellfound are registered as
  discoverable adapters but are **not** auto-submission capable.
- Cycle results are reported truthfully: a cycle with partial failure is
  `PARTIAL_SUCCESS`, not `success`, and unknown signals score `0.0` rather
  than a flattering default.

### Turning on live submissions

Do not flip this casually. Only after you have reviewed dry-run output, set
`AUTO_SUBMIT_ENABLED=true` **and** `DRY_RUN=false`, and keep
`REQUIRE_HUMAN_APPROVAL=true` so each application is still approved by you
before anything is sent.
