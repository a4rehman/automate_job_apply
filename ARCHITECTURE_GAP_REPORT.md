# ARCHITECTURE GAP REPORT: Existing vs Target State

**Project:** `automate_job_apply`  
**Audit Date:** September 2026

---

## 1. System Component Comparison

| Component / Layer | Existing Status | Target State Requirements | Gap & Action Required |
| :--- | :--- | :--- | :--- |
| **Database Engine** | SQLite default with aiosqlite | TiDB Cloud (MySQL wire protocol) + SQLite fallback | Add SSL config, aiomysql/pymysql support, pool recycling, ensure reconnect resilience. |
| **Database Schema Entities** | 8 tables: users, user_profiles, resumes, resume_versions, skills, jobs, job_matches, applications, application_answers, audit_logs, notifications, automation_settings, scheduler_runs | Complete set of 18 logical entities including `job_requirements`, `application_packages`, `application_reviews`, `application_events`, `execution_attempts`, `outbound_emails`, `automation_rules` | Add and map missing entities with explicit relationships and indexed query patterns. |
| **AI Decision Engine** | Legacy OpenAI/HuggingFace with basic JSON prompt | Modular Gemini Decision Engine with official Google GenAI SDK | Implement `backend/app/ai/decision_engine/` (`schemas.py`, `prompts.py`, `validators.py`, `confidence.py`, `gemini_provider.py`, `decision_engine.py`). |
| **Structured Output Schema** | Unstructured or basic dictionary parsing | Strongly typed `JobDecision` & `EmailApplicationExtraction` Pydantic models | Validate 0.0–1.0 bounded float scores, strict literal enums, and required reasoning fields. |
| **Matching Engine** | Basic 6-factor arithmetic + heuristic scoring | Explainable 7-factor matching (overall, role, skills, experience, seniority, semantic, location, salary, confidence, matched/missing skills, concerns) | Enhance `MatchingEngineService` to include Gemini/local semantic embeddings and explainable breakdown. |
| **Email Application Flow** | Generic notifications only | Dedicated Email Application extraction and dispatch engine | Detect email application instructions in JDs, extract email/subject, generate grounded email, track outbound status and message ID. |
| **Application State Machine** | 10 states (SAVED, PREPARING, PENDING_APPROVAL, etc.) | Complete 14-state machine with event logging | Support: `DISCOVERED`, `NORMALIZED`, `MATCHED`, `PREPARED`, `REVIEW_REQUESTED`, `APPROVED`, `REJECTED`, `SUBMISSION_STARTED`, `EMAIL_SENT`, `SUBMITTED`, `VERIFIED`, `FAILED`, `NEEDS_ACTION`, `DUPLICATE_SKIPPED`. |
| **Streamlit Authentication Gate** | Simple form query against `users` table | High-security gate using Streamlit secrets (`APP_PASSWORD_HASH` with bcrypt/argon2) | First screen blocks all dashboard rendering until valid password provided. Zero dashboard exposure. |
| **Streamlit UI/UX** | 4 basic tabs | 10 dedicated sections: Overview Metrics, Job Board, High Matches, Human Review (Approve/Reject/Edit), Applications, Email Apps, Automation Controller, Analytics, Settings, Audit Logs | Modern, rich UI with real-time progress steps, persistent run locking, and zero fake data. |
| **Background Automation** | Streamlit button / basic script | Unified `AutomationService` shared by Streamlit UI and CLI worker (`python -m backend.app.workers.run_automation`) | Ensure single source of business logic with persistent TiDB locking. |
| **Security & Secrets** | Hardcoded dev secrets in `.env` | Streamlit Secrets + `.env` with strict zero-secret exposure | Provide `.streamlit/secrets.toml.example` and sanitize all logs/traces. |

---

## 2. Risk Mitigation & Implementation Strategy

1. **No Destructive Overwrite:** Existing database tables and working services (`resume_parser.py`, `source_config_service.py`, `job_sources/`) will be retained and extended.
2. **Offline Testing Fallback:** If live Gemini or TiDB Cloud credentials are not configured in a testing environment, the system gracefully falls back to local SQLite and deterministic offline mock inference, ensuring 100% test suite reliability.
3. **Strict Truth & Non-Hallucination:** System prompts strictly forbid inventing candidate skills, experience years, or certifications.
4. **Idempotency & Race Condition Defense:** Double-checking execution attempts, run locks, and email deduplication hashes before any outbound action.
