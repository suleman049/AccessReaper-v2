# AccessReaper v2 — Development Log & Deliverable Status

**Date:** October 21, 2026  
**Status:** **PHASE 2 COMPLETE — Ready for Review & Testing**  
**Execution Mode:** `DRY_RUN`  
**Host & Port:** `127.0.0.1:8100`  
**Project Location:** `D:\AccessReaper-v2\`

---

## 1. Deliverables Summary

| Component | Phase | Status | Location | Notes |
|---|:---:|:---:|---|---|
| **Teammate Frontend** | 1 & 2 | Complete | `D:\AccessReaper-v2\frontend\` | Preserved 100% of original visual layouts, copy, icons, and routing. |
| **Untouched Backup** | 1 & 2 | Complete | `D:\AccessReaper-v2\_frontend_original_backup\` | Exact duplicate of extracted zip, never edited, used for diffing. |
| **Thin Data Layer** | 1 & 2 | Complete | `frontend\api-client.js` | Fetch wrapper attaching Firebase ID tokens, handling 401/403/409/422 with toasts. |
| **Database & Schema** | 1 & 2 | Complete | `backend\app\db\models.py` | Models for identities, resources, assignments, findings, requests, audits, audit log, rule configs, schedules. |
| **Immutability Triggers** | 1 | Complete | `backend\app\db\session.py` | SQLite DB-level triggers prohibiting UPDATE/DELETE on `audit_log`. |
| **Deterministic Risk Engine** | 1 & 2 | Complete | `backend\app\engine\scoring.py` | Pure rule-based module supporting dynamic weights and 100% calibration across all 12 baseline seed records. |
| **Authentication & AuthZ** | 1 | Complete | `backend\app\core\security.py` | Google public certs verification + Firestore REST API own-profile authorization with TTL $\le$ 60s cache. |
| **Workspace User Admin** | 2 | Complete | `backend\app\api\api_v1\endpoints\users.py`, `frontend\users-page.js` | Firebase Admin SDK integration, activate/deactivate/reject, self-deactivate and last-admin protection. |
| **Editable Risk Rules** | 2 | Complete | `backend\app\api\api_v1\endpoints\rules.py`, `frontend\rules-settings.js` | Versioned `rule_configs`, dry-preview impact calculation without DB writes, rollback. |
| **Scheduled Audits** | 2 | Complete | `backend\app\api\api_v1\endpoints\schedule.py`, `backend\app\core\scheduler.py`, `frontend\schedule-settings.js` | In-process APScheduler with Asia/Karachi (PKT) timezone, overlap locking, misfire grace. |
| **Server-Side Reports & Exports** | 2 | Complete | `backend\app\engine\pdf_report.py`, `backend\app\engine\csv_export.py` | ReportLab PDF generator (`Page X of Y`), RFC 4180 CSV with UTF-8 BOM and formula injection protection. |
| **One-Click Launcher** | 1 | Complete | `D:\AccessReaper-v2\Start-AccessReaper-v2.cmd` | Windows launcher: auto venv creation, pip install, migrations, seed, Uvicorn on 8100, opens browser. |
| **Alembic Migrations** | 1 & 2 | Complete | `backend\alembic\` | Revisions: `55d8eb8b1a95_initial_schema.py` and `9744288c9940_phase2_rules_schedules_audit_run_fields.py`. |
| **Automated Tests** | 1 & 2 | Complete | `backend\tests\` | 43/43 tests passing (scoring rules, boundaries, auth, immutability, workflows, idempotency, users, rules, scheduler, reports). |
| **Documentation** | 1 & 2 | Complete | `D:\AccessReaper-v2\docs\` | `API_CONTRACT.md`, `ENGINE.md`, `FRONTEND_CHANGES.md`, `RUN_GUIDE.md`, `SECURITY.md`, `PHASE1_TEST_CHECKLIST.md`, `PHASE2_TEST_CHECKLIST.md`. |

---

## 2. Technical Stack Implemented

- **Python:** 3.14 (compatible with 3.11+)
- **Web Framework:** FastAPI 0.156.8 + Uvicorn 0.54.0
- **Validation:** Pydantic v2.14.1 & Pydantic-Settings
- **ORM / Migrations:** SQLAlchemy 2.1.5 + Alembic 1.20.0
- **Database:** SQLite (`backend\data\accessreaper_v2.db`) with native triggers
- **Scheduler:** APScheduler 3.11.3 (`BackgroundScheduler`)
- **PDF Generation:** ReportLab 5.0.1 (Flowables, NumberedCanvas)
- **Admin SDK:** Firebase Admin 7.7.0 (`google-cloud-firestore`)
- **Auth Provider:** Firebase Auth (Email/Password) + Firestore REST profile lookup
- **Testing:** Pytest 9.1.1 + HTTPX TestClient (43 passing tests)
- **Linter:** Ruff 0.17.1 (Zero errors)

---

## 3. Key Design Decisions & Phase 2 Implementations

1. **Pure Scoring Engine with Config Injection:**  
   `backend/app/engine/scoring.py` accepts candidate `RuleConfig` payloads. When no config is supplied, it falls back to Phase 1 default calibration. Evaluates scores, reasons, targets, and fired rules purely in memory.
2. **Non-Fatal Firebase Admin SDK Integration:**  
   If `backend/secrets/firebase-service-account.json` is missing or unconfigured, the app starts and functions normally without crashing. The Users page displays a friendly card with setup steps.
3. **Safety Guards on User Management:**  
   Admins cannot deactivate their own account (verified by UID and email). The system dynamically protects the last active administrator from being deactivated (HTTP 409).
4. **Dry Preview Calculation:**  
   `POST /api/rules/preview` performs an in-memory re-scoring of all assignments without writing to the database, returning summary deltas and finding-level diffs.
5. **ReportLab Frozen Snapshots:**  
   Audit PDF reports read the frozen `findings_snapshot` JSON column in `audit_runs`, ensuring historical reports reflect the exact state at audit completion regardless of future remediations.
6. **Strict CSV Injection Defense:**  
   Any exported cell value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is escaped with a single quote prefix (`'`), and the file is encoded with UTF-8 BOM for Excel compatibility.

---

# Phase 3 Log: Read-Only GitHub IAM Integration & Workspace Data Mode

**Date:** 2026-10-21  
**Status:** COMPLETE & 100% VERIFIED  

### 1. Goals & Architectural Safety
- Enable auditing of real GitHub organization permissions, teams, outside collaborators, and repositories without changing anything in GitHub (`DRY_RUN`).
- Strictly read-only GitHub client (`GitHubClient`): only `GET` requests permitted. Any non-GET request raises `ReadOnlyViolationError`.
- Server-side secret encryption at rest: GitHub PAT tokens encrypted via Fernet (AES-128-CBC + HMAC-SHA256) with key from `APP_ENCRYPTION_KEY`. Tokens are never exposed over API or written to logs.
- Strict permission mapping: `admin` $\rightarrow$ `Admin`, `maintain` $\rightarrow$ `Write` (NOT Admin), `push` $\rightarrow$ `Write`, `triage` $\rightarrow$ `Read`, `pull` $\rightarrow$ `Read`.
- Idempotent sync engine with request cap (default 2000). Disappeared collaborators are marked `revoked_externally` to preserve historical evidence.
- Identity mapping (`github_identity_map`): auto-match by public/commit email, fallback to placeholder unmatched identities with finding `"GitHub account not linked to a known employee"`.
- Admin-editable employee status: `PUT /api/identities/{email}` with required note and append-only audit event.
- Workspace data mode toggle: `dataMode = 'sample' | 'live'` isolates sample and live data across dashboard, audit table, and reports without deleting data.

### 2. Delivered Components
- **Core Engine & Crypto**:
  - `backend/app/core/crypto.py`: Symmetric Fernet encryption and decryption.
  - `backend/app/integrations/github/client.py`: Read-only GitHub client with rate-limit and ETag handling.
  - `backend/app/integrations/github/mapping.py`: Permission level mapper.
  - `backend/app/integrations/github/sync.py`: Idempotent synchronization engine.
  - `backend/app/engine/scoring.py`: Inactivity null activity rule option (`unknownActivityCountsAsDormant`) and unmatched account rules.
- **Database & Migrations**:
  - `backend/alembic/versions/2e3e7f93a111_phase3_github_integration.py`: Tables `github_configs`, `sync_runs`, `github_identity_map`; columns `origin`, `external_status`, `github_login` on `assignments`.
- **API Endpoints**:
  - `GET /api/integrations/github/status`
  - `PUT /api/integrations/github/config`
  - `DELETE /api/integrations/github/config`
  - `POST /api/integrations/github/test`
  - `POST /api/integrations/github/sync`
  - `GET /api/integrations/github/unmatched`
  - `PUT /api/integrations/github/map/{login}`
  - `GET /api/integrations/github/mode` & `PUT /api/integrations/github/mode`
  - `PUT /api/identities/{email}`
- **Mock Demo Server**:
  - `tools/mock_github.py`: Standalone fake GitHub API server running on port 8109 for deterministic testing.
- **Frontend Components**:
  - `frontend/github-settings.js`: `GitHubSettings` component for connection status, sync, disconnect, data mode, and account mapping.
  - `frontend/phase2.css`: Additive styles for buttons, unmatched list, and `LIVE_DATA` badge.
  - Minimal non-breaking hooks in `index.html`, `api-client.js`, and `app.js`.

### 3. Verification & Quality
- **Automated Tests**: All **53 / 53 tests passing** (7.14s) including read-only enforcement, token security, sync idempotency, permission mapping, disappeared accounts, data mode isolation, and employment status updates.
- **Code Linting**: `ruff check app/ tests/` $\rightarrow$ **0 errors (clean)**.
- **Browser Automation Proof**: 8 screenshots captured via Chrome CDP automation (`tools/verify_phase3.py`) in `docs/verification/`:
  - `B1-settings-github-connected.png`
  - `B2-sync-in-progress.png`
  - `B3-unmatched-accounts.png`
  - `B4-live-overview.png`
  - `B5-live-audit.png`
  - `B6-live-pdf-report.png`
  - `B7-settings-github-dark.png`
  - `B8-settings-github-390px.png`
  - **Zero JavaScript console errors** across all pages and flows.


---

## STAGE 1 Checkpoint — Fully Automatic Audits (No Audit Button)

### 1. Architectural Changes & Implementations
- **Automation Service & Scheduler (`backend/app/engine/automation.py`, `backend/app/core/scheduler.py`)**:
  - Implemented 24-hour automatic recurring IAM audit cycle defaulting to 02:00 PKT daily with overlap locking (`_audit_lock`).
  - Added resilience with startup check and 5-minute recurring heartbeat (`automation_heartbeat`): executes exactly one catch-up audit if last automatic audit was > 24 hours + 15 minutes ago.
  - Handled GitHub sync degradation: if sync fails during automatic cycle, audit executes in `Degraded` mode with recorded reason, and a 10-minute retry job is scheduled.
  - Endpoints:
    - `GET /api/automation/status`: returns `enabled`, `intervalHours: 24`, `timeOfDay`, `nextRunAt`, `serverTime`, `secondsUntilNext`, `lastRun`, `catchUpPending`, `isRunning`, and `pauseNote`.
    - `PUT /api/automation/config`: allows setting `timeOfDay` and `enabled` (pause/resume). Pausing strictly requires an explanatory note (422 validation error if missing) and logs an append-only audit log entry. Resuming records an audit event.
  - **Manual Trigger Removal**: Removed manual audit run trigger from product UI; blocked `POST /api/audits/run` with 403 Forbidden unless `ENV=dev` and `ALLOW_MANUAL_AUDIT=true`.
- **Database Evolution**:
  - Alembic migration `37a684375ac9_stage1_automation_fields.py`: added `pause_note` to `schedules` and `degraded_reason` to `audit_runs`. Enabled schedule by default at 02:00 PKT.
- **Frontend Enhancements**:
  - `frontend/automation-timer.js`: `window.AutomationTimer` component with live 1-second countdown clock using server time offset, background polling, and automatic UI refresh on audit completion.
  - Replaced manual "Run audit" / "Run access audit" buttons on `#audit` and `#overview` with the live countdown chip (`Next audit in HH:MM:SS` and `Last audit: ... · Automatic`).
  - Updated empty-state text to `"The first automatic audit runs <time>"`.
  - Transformed Settings card into "Automatic audits" with 24h fixed interval, time picker, pause modal (requiring note), and past 4 runs history.
  - Provided `tools/Install-AutoStart.cmd` and `tools/Remove-AutoStart.cmd` for Windows Task Scheduler logon registration.

### 2. Verification & Quality
- **Automated Tests**: **59 / 59 tests passing** (`pytest -q`), including new regression suite `tests/test_automation.py` covering status metrics, countdown calculations, note requirement, pause/resume audit logs, catch-up execution, and manual audit endpoint blocking.
- **Code Quality**: `ruff check app/ tests/` $\rightarrow$ **clean (0 warnings/errors)**.
- **Real Browser Verification**: Verified via Chrome CDP automation (`tools/verify_stage1.py`) with **zero console errors**:
  - `docs/verification/S1-countdown-timer.png`: Proves removal of manual audit buttons and presence of live countdown timer chip on Overview and Audit pages.
  - `docs/verification/S1-settings-automation.png`: Proves "Automatic audits" card with status "Active (Every 24 hours)", time picker, and next run indicator.
  - `docs/verification/S1-paused-state.png`: Proves pause flow with required note and visible "Automatic audits paused" warning state.


---

## STAGE 2 Checkpoint — Triage Quality for Real Data

### 1. Architectural Changes & Implementations
- **Identity & Classification Enhancements (`backend/app/engine/scoring.py`, `backend/app/api/endpoints/github.py`, `backend/app/api/endpoints/identities.py`)**:
  - Unmatched accounts can be classified as `user`, `bot`, `service`, or `ignored`. Non-user classifications are excluded from unmatched employee alerts while remaining visible and fully audited.
  - Elevated unmatched access (Admin/Write) scores +70 pts (High), standard (Read) scores +40 pts (Medium), fully configurable via risk rules settings.
  - Added `score` and `scoreBreakdown` to `PersonSchema` and `serialize_assignment`, allowing real-time inspection of score modifiers.
  - Added `POST /api/integrations/github/bulk-map`: maps multiple GitHub accounts to employee emails in one atomic transaction, writing distinct audit log events.
  - Added `GET /api/integrations/github/auto-suggest`: suggests mappings based on exact and similarity matches against organization directory.
  - Added `PUT /api/integrations/github/accounts/{login}/classification`: updates account classification with required explanatory note, recalculates risk, and logs audit event.
  - Added `GET /api/identities`: returns full list of organization people with linked GitHub logins.
  - Added `POST /api/identities`: registers new employee identity with required note and audit logging.
  - Added `PUT /api/identities/{email}`: updates employee metadata and employment status, re-evaluating risk findings.
  - Added CSV Import Endpoints: `POST /api/identities/import-csv/preview` (validates headers `github_login,email,name,team,employment_status`, flags unknown logins, and preview rows) and `POST /api/identities/import-csv/confirm` (atomic import and identity linking).
- **Database Evolution**:
  - Alembic migration `edaf100302b6_stage2_identity_and_classification.py`: added `account_type` and `note` columns to `github_identity_map`.
- **Frontend Enhancements**:
  - `frontend/github-settings.js`: Added "Auto-suggest matches", "Import CSV", "Save all links", and per-row classification dropdown (`User`, `Bot`, `Service`, `Ignored`) to Unmatched GitHub Accounts card.
  - `frontend/users-page.js`: Added "People (Identities)" tab to `#users` with full People directory table, search bar, "+ Add Person" modal, "Edit Person" modal, and CSV import modal. Fixed container rendering to return HTML string.
  - `frontend/governance.js`: Added "Why this score?" breakdown panel in finding detail view showing calculated score, risk badge, and a granular table of triggered rules and point increments.
  - `frontend/rules-settings.js`: Added editable weights for unmatched account standard (+40 pts) and elevated (+70 pts).

### 2. Verification & Quality
- **Automated Tests**: **66 / 66 tests passing** (`pytest -q`), including new regression suite `tests/test_stage2.py` covering bulk mapping, auto-suggest, account classification, CSV import preview & confirm, identity CRUD, and score breakdown.
- **Code Quality**: `ruff check .` $\rightarrow$ **clean (0 warnings/errors)**.
- **Real Browser Verification**: Verified via Chrome CDP automation (`tools/verify_stage2.py`) with **zero console errors**:
  - `docs/verification/S2-unmatched-bulk-triage.png`: Proves Unmatched Accounts card with Auto-suggest, CSV import button, bulk action bar, and classification dropdowns.
  - `docs/verification/S2-people-management.png`: Proves People (Identities) tab on `#users` with 12 employee identities, status badges, linked GitHub accounts, and "+ Add Person" modal.
  - `docs/verification/S2-why-this-score.png`: Proves "Why this score?" breakdown card on `#risk` finding detail page, displaying 180 pts total, risk badge, and itemized rule point modifiers.


---

## STAGE 3 Checkpoint — Separation of Duties (SoD) & Orphan Accounts

### 1. Architectural Changes & Implementations
- **Separation of Duties (SoD) Conflicting Access Pairs (`backend/app/engine/scoring.py`, `backend/app/db/models.py`)**:
  - Implemented configurable database table `sod_conflicts` (`id`, `pattern_a`, `access_a`, `pattern_b`, `access_b`, `description`, `points`, `enabled`, `created_at`).
  - Seeded default SoD conflict: `*terraform*` Admin + `*payment*` Admin (+50 pts).
  - Pure scoring engine evaluates identity cross-resource assignments against enabled SoD pairs using case-insensitive wildcard pattern matching (`fnmatch`). Emits `SOD_CONFLICT` (+50 pts) finding with evidence of both conflicting roles.
  - CRUD API Endpoints: `GET /api/rules/sod`, `POST /api/rules/sod`, `PUT /api/rules/sod/{id}`, `DELETE /api/rules/sod/{id}` with mandatory notes and append-only audit logging.
- **SoD Approval Integrity Enforcement (`backend/app/api/api_v1/endpoints/approvals.py`)**:
  - Strictly prevents administrators from approving or rejecting their own access requests (`current_user.email == req.identity.email`).
  - Returns HTTP 409 Conflict with error code `SOD_SELF_APPROVAL_FORBIDDEN`.
  - Appends an immutable security record to `audit_log` (`tag: "Request"`, `title: "Self-approval attempt blocked"`, `mode: DRY_RUN`).
- **Orphan Account & Bus-Factor Rules (`backend/app/engine/scoring.py`)**:
  - **(a) Unmatched Account**: +70 pts (Elevated) / +40 pts (Standard) with reason `"GitHub account not linked to a known employee"`.
  - **(b) Dormant Active Identity (`DORMANT_ACTIVE_IDENTITY`)**: flags active employees holding zero active resource assignments (+30 pts).
  - **(c) Bus-Factor Risk (`BUS_FACTOR_SINGLE_ADMIN`)**: flags repositories with $\le$ 1 administrator (+30 pts), recommending `"Assign owner"` within existing vocabulary.
  - **(d) Archived Repository Access (`ARCHIVED_REPO_ACTIVE_ACCESS`)**: flags active Write/Admin access on archived repositories (+40 pts), recommending `"Revoke access"` (target: `None`).
  - **(e) Inactive Outside Collaborator (`INACTIVE_OUTSIDE_COLLABORATOR`)**: flags external contractors/outside collaborators with elevated access inactive > 30 days (+50 pts), recommending `"Revoke access"` (target: `None`).
- **Baseline Calibration Guarantee**: All 12 baseline demonstration records (`SEED_PEOPLE`) retain 100% identical risk levels, primary reasons, and action targets under default configuration.
- **Frontend & Settings Integration**:
  - `frontend/rules-settings.js`: Added "Separation of Duties & Orphan Rules" section to Risk rules card with toggles and weights for `sodConflict` (50 pts), `busFactor` (30 pts), `archivedRepo` (40 pts), `inactiveOutsideCollaborator` (50 pts), and `dormantIdentity` (30 pts).
  - `frontend/api-client.js`: Added `getSoDConflicts()`, `createSoDConflict()`, `updateSoDConflict()`, and `deleteSoDConflict()`.

### 2. Verification & Quality
- **Automated Tests**: **74 / 74 tests passing** (`pytest -q`), including new regression suite `tests/test_stage3.py` covering SoD engine evaluation, SoD self-approval 409 block and audit log, orphan rules (a)-(e), 12-sample record regression invariance, and SoD CRUD API endpoints.
- **Code Quality**: `ruff check .` $\rightarrow$ **clean (0 warnings/errors)**.
- **Real Browser Verification**: Verified via Chrome CDP automation (`tools/verify_stage3.py`) with **zero console errors**:
  - `docs/verification/S3-sod-rules-config.png`: Proves Risk rules card in Settings displaying configurable SoD conflict points (50 pts), bus-factor points (30 pts), archived repo points (40 pts), inactive outside collaborator points (50 pts), and dormant identity points (30 pts).
  - `docs/verification/S3-self-approval-blocked.png`: Proves SoD self-approval integrity enforcement: attempting to approve one's own request triggers 409 Conflict (`SOD_SELF_APPROVAL_FORBIDDEN`) and writes an append-only blocked event to `audit_log`.
  - `docs/verification/S3-orphan-and-busfactor-findings.png`: Proves Access audit table rendering findings with proper severity and action recommendations ("Assign owner", "Revoke access", "Reduce access").

---

## STAGE 4 Checkpoint — AI Explanations (Gemini) & Notifications Center

### 1. Architectural Changes & Implementations
- **Database Migrations (`backend/alembic/versions/5c18a221f92e_stage4_ai_and_notifications.py`)**:
  - `ai_explanations`: stores frozen executive summaries and finding explanations (`id`, `run_id`, `finding_id`, `summary_text`, `recommendation_text`, `model`, `status`, `generated_at`).
  - `notifications`: in-app alert store per administrator (`id`, `admin_email`, `event_type`, `title`, `message`, `link`, `is_read`, `created_at`).
  - `notification_preferences`: per-admin delivery controls (`admin_email`, `email_digest_enabled`, `in_app_enabled`, `updated_at`).
  - `email_digests_sent`: tracking table preventing duplicate email digest dispatch (`id`, `run_id`, `admin_email`, `sent_at`, `status`).
- **Gemini Service (`backend/app/engine/gemini_service.py`)**:
  - Server-side execution only utilizing official `google-genai` SDK (`from google import genai`). Reads `GEMINI_API_KEY` and `GEMINI_MODEL` (`gemini-2.5-flash`).
  - **Privacy Guarantee**: All user identities pseudonymized ("User A", "User B") unless `GEMINI_SEND_REAL_NAMES=true`. Zero tokens, secrets, or raw credentials ever transmitted.
  - **Prompt Injection Defense**: Fixed system instruction enforcing strict IAM auditor role and ordering complete disregard of directives found inside data fields. Untrusted fields sanitized and isolated inside structured JSON delimiters.
  - **Caching Architecture**: Explanations generated once per audit run at completion; cached in DB. Page loads query database cache and never call AI models.
  - **Advisory Labeling**: All AI outputs labeled with mandatory disclaimer: `"AI-generated — verify before acting"`. AI outputs never alter deterministic scores, permission assignments, or business logic.
  - **Deterministic Fallback**: In the absence of an API key, quota limit, timeout, or network error, falls back seamlessly to deterministic templates displaying `"Gemini · Preview"`; with live Gemini displays `"Gemini ✦"`.
- **In-App Notification Center (`backend/app/engine/notification_service.py`, `frontend/notifications-center.js`)**:
  - Additive topbar bell button with unread counter badge.
  - Flyout dropdown panel listing events: completed audits, high-risk findings, pending approvals overdue (>24h), degraded sync, paused audits, and pending user signups.
  - Interactive "Mark read" per item and "Mark all read" with real-time badge updates and auto-refresh every 30 seconds.
- **Daily Email Digest & Test Email (`backend/app/engine/email_service.py`, `frontend/notifications-settings.js`)**:
  - SMTP service reading settings from `.env` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `PUBLIC_BASE_URL`).
  - Dispatches one consolidated daily digest to active admins after automatic audits complete; de-duplicates to guarantee zero repeated sends.
  - Settings page **Notifications & Alerts** card with status indicator, daily digest opt-in/opt-out toggle, and **Send test email** button with feedback toast.

### 2. Verification & Quality
- **Automated Tests**: **83 / 83 tests passing** (`pytest -q`), including new comprehensive test suite `tests/test_stage4.py` covering:
  - Gemini deterministic fallback and caching.
  - Mocked Google GenAI SDK execution.
  - Privacy pseudonymization and prompt injection sanitization.
  - Notification center lifecycle (list, mark read, mark all read, badge counts, overdue approvals).
  - Daily email digest de-duplication and test email handling.
  - Secret scanning test guaranteeing zero keys, passwords, or tokens in API responses.
- **Code Quality**: `ruff check .` $\rightarrow$ **clean (0 warnings/errors)**.
- **Real Browser Verification**: Verified via Chrome CDP automation (`tools/verify_stage4.py`) with **zero console errors**:
  - `docs/verification/S4-ai-executive-summary.png`: Proves Executive summary card on `#dashboard` with `Gemini · Preview` badge and `"AI-generated — verify before acting"` disclaimer.
  - `docs/verification/S4-notification-center.png`: Proves topbar notification bell with unread badge counter (`3`) and open dropdown panel showing categorized access events.
  - `docs/verification/S4-ai-finding-explanation.png`: Proves Finding detail view (`#risk?FND-2841`) showing plain-language AI explanation, recommended next step, and advisory label.
  - `docs/verification/S4-settings-notifications.png`: Proves Settings page **Notifications & Alerts** card with SMTP status indicator, daily digest toggle, and "Send test email" button.
  - `docs/verification/S4-mobile-notifications.png`: Proves 390px mobile viewport responsiveness with notification center panel comfortably fitting phone screens.

---

## FOLLOW-UP Checkpoint — Groq Primary AI Provider & Unified LLM Subsystem

### 1. Architectural Changes & Implementations
- **One-Time Key Setup**: `GROQ_API_KEY` configured strictly in `backend/.env` (gitignored).
- **Model Discovery & Selection**: Queried Groq's `/openai/v1/models` in preference order (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`). Successfully identified and set `GROQ_MODEL="openai/gpt-oss-120b"` in `.env`. Zero hardcoded model names in Python code.
- **Provider-Agnostic Architecture (`backend/app/services/llm/`)**:
  - `base.py`: Abstract `LLMProvider` interface defining `name`, `model_identifier`, `is_configured()`, and `generate_audit_batch()`.
  - `groq_provider.py`: High-speed OpenAI-compatible client (`https://api.groq.com/openai/v1/chat/completions`) with JSON schema formatting, request timeouts, and exponential backoff on HTTP 429 (`Retry-After` / `x-ratelimit-reset-tokens`).
  - `gemini_provider.py`: Optional fallback provider wrapping `google-genai` SDK.
  - `openai_provider.py`: Generic OpenAI-compatible provider (`LLM_BASE_URL`).
  - `template_provider.py`: Deterministic template fallback text.
  - `budget.py`: Token-bucket limiter spacing outbound requests (2.0s interval) and daily token usage tracker persisting tokens to the `Setting` table against `LLM_DAILY_TOKEN_BUDGET=200000`.
  - `manager.py`: Provider fallback orchestrator honoring `LLM_PROVIDER_ORDER=groq,gemini`. Chunks findings into batches of at most `LLM_MAX_FINDINGS_PER_CALL=6`.
- **Privacy & Prompt Injection Guard**:
  - User emails mapped to anonymous aliases (`User A`, `User B`) via `sanitizer.py` unless `LLM_SEND_REAL_NAMES=true`.
  - Untrusted text stripped of prompt injection triggers and delimited inside structured JSON facts with strict system prompt instruction.
- **Frontend & Settings Integration**:
  - `frontend/audit-summary.js`: Dynamically renders `Groq ✦` badge on Executive summary card.
  - `frontend/governance.js`: Dynamically renders `Groq ✦` badge on Finding detail views.
  - `frontend/workspace-design.js` & `frontend/github-settings.js`: Added read-only "AI explanations" row in Connected services card on `#settings`: provider order (`Groq → Gemini`), configured yes/no (`Groq: Yes · Gemini: No`), and daily token usage (`2,497 / 200,000 tokens`).
  - `GET /api/llm/status`: Safe read-only status endpoint returning zero keys.

### 2. Verification & Quality
- **Automated Tests**: **90 / 90 tests passing** (`pytest -q`), including new regression suite `tests/test_groq_and_llm.py` (batching <= 6, token budget exhaustion, 429 backoff & fallback, all-fail fallback, timeout non-blocking, caching, prompt injection defense, and secret scanner).
- **Code Quality**: `ruff check .` $\rightarrow$ **clean (0 warnings/errors)**.
- **Secret Scanner**: Grep across entire repository (excluding `backend/.env`) confirms **ZERO occurrences** of `gsk_` or secret keys.
- **Live Groq Verification**: Executed live call with `GROQ_API_KEY` from `.env` on `AUD-20261014-001` with model `openai/gpt-oss-120b`:
  - Consumed 2,497 tokens (well within 200,000 daily budget).
  - Generated factual executive summary and 7 plain-language finding explanations.
- **Browser Proof (Screenshots in `docs/verification/`)**:
  - `docs/verification/S4-groq-explanation.png`: Dashboard showing `Groq ✦` badge and AI-generated executive summary.
  - `docs/verification/S4-groq-settings.png`: Connected services card showing `AI explanations` row with `Order: Groq → Gemini · Tokens today: 2,497 / 200,000 · Groq: Yes · Gemini: No`.
  - `docs/verification/S4-groq-finding-detail.png`: Finding detail page showing preserved evidence and `Groq ✦` risk explanation.

---

## FIX — Leftover "Gemini" and "Preview" Labels Neutralization

### 1. Changes
- **Dynamic Disclosure Header**: In `frontend/workspace-design.js`, replaced hardcoded `<summary><span>✦ Audit summary <small>Gemini · Preview</small></span>` with `${AuditSummary.disclosureHeader(report)}`. When Groq generated the latest audit run, it renders `✦ Audit summary <small>Groq ✦</small>`; when template fallback is active, it renders `Audit summary <small>Summary</small>` without any AI mark or preview label.
- **Audit Summary Component**: Updated `frontend/audit-summary.js` so `preview(report)` and `disclosureHeader(report)` use the actual generating provider as single source of truth. In template fallback mode, label is `Summary`, disclaimer is `"Generated from report data"`, aria-label is `"Latest audit summary generated from report data"`, and the `✦` badge is omitted entirely.
- **Finding Detail Policy Context**: In `frontend/governance.js`, updated finding detail view:
  - Live Groq: `Groq ✦` badge, `AI risk explanation:`, and `"Generated by Groq — verify before acting"`.
  - Template: `Summary` badge, `Policy check:`, and `"Generated from report data"`.
  - No explanation: `Policy check: <reason>. Generated from report data.`.
- **Cleaned Non-UI Code Comments & Docs**: Neutralized `frontend/firebase-config.js` comment and updated `frontend/README.md`.
- **String Guard Test**: Added `test_no_leftover_gemini_or_preview_labels_in_frontend()` in `backend/tests/test_groq_and_llm.py` asserting `"Gemini · Preview"` and `"Live Gemini"` do not exist in any frontend file.

### 2. Verification
- **Automated Tests**: **92 / 92 tests passing** (`pytest`).
- **Code Quality**: `ruff check .` clean (0 errors).
- **Browser Screenshots (in `docs/verification/`)**:
  - `docs/verification/fix-audit-collapsed.png`: Access audit page with collapsed disclosure header displaying `✦ Audit summary Groq ✦`.
  - `docs/verification/fix-audit-expanded.png`: Access audit page with expanded disclosure displaying full executive summary and `"Generated by Groq — verify before acting"`.
  - `docs/verification/fix-overview.png`: Dashboard overview card with `Groq ✦` badge and disclaimer.
  - `docs/verification/fix-finding-detail.png`: Finding detail view with `Groq ✦` badge and advisory disclaimer.
  - `docs/verification/fix-report-dialog.png`: Audit report dialog modal with `Groq ✦` badge and disclaimer.
  - `docs/verification/fix-pdf-smoke.png` / HTTP endpoint: `/api/audits/AUD-20261014-001/report.pdf` verified returning valid PDF binary `%PDF-1.4`.


