# AccessReaper v2 — Run Guide (Windows)

This guide walks through starting and testing **AccessReaper v2** on Windows.

---

## 1. Quick Start (One-Click Launcher)

1. Navigate to `D:\AccessReaper-v2\`.
2. Double-click **`Start-AccessReaper-v2.cmd`**.
3. The launcher will automatically:
   - Verify Python 3.11+ is installed.
   - Create the Python virtual environment in `backend\.venv` (if not already created).
   - Install all pinned dependencies from `backend\requirements.txt`.
   - Run database migrations (`alembic upgrade head`).
   - Seed the SQLite database (`backend\data\accessreaper_v2.db`) if empty.
   - Start Uvicorn server on **`127.0.0.1:8100`**.
   - Open your browser to `http://localhost:8100/#login`.

---

## 2. Manual Terminal Commands

If you prefer running from PowerShell or Command Prompt:

```powershell
# 1. Change to backend directory
cd D:\AccessReaper-v2\backend

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Set PYTHONPATH
$env:PYTHONPATH = "D:\AccessReaper-v2\backend"

# 4. Run database migrations
alembic upgrade head

# 5. Seed initial baseline data (if empty)
python -m app.db.seed

# 6. Launch Uvicorn server on port 8100
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Once running:
- **Application URL:** [http://localhost:8100/#login](http://localhost:8100/#login)
- **Interactive OpenAPI Docs:** [http://localhost:8100/api/docs](http://localhost:8100/api/docs)
- **Health Check:** [http://localhost:8100/api/health](http://localhost:8100/api/health)

---

## 3. Configuration via `.env`

The configuration file is located at `D:\AccessReaper-v2\backend\.env`:

```ini
PROJECT_NAME="AccessReaper v2"
VERSION="2.0.0"
ENV="dev"
HOST="127.0.0.1"
PORT=8100

# Authentication mode:
# - "firebase": Production mode (validates Firebase ID tokens & Firestore profile)
# - "dev": Local dev mode (bypasses remote certs, uses X-Dev-User, only allowed on 127.0.0.1)
AUTH_MODE="firebase"
FIREBASE_PROJECT_ID="accessreaper"
FIRESTORE_DATABASE_ID="accessreaper-profiles"
ORGANIZATION_ID="acme"

# SQLite database file path
DATABASE_URL="sqlite:///D:/AccessReaper-v2/backend/data/accessreaper_v2.db"

# DRY_RUN guard: changes are local to DB; no external IAM writes
DRY_RUN=true
```

---

## 4. Setting Up Firebase Admin Service Account (Phase 2 Feature 1)

In Phase 1, activating a user required manually editing their Firestore document in the Firebase Console. In Phase 2, administrators can activate, deactivate, or reject accounts directly from the new **Users** screen (`http://localhost:8100/#users`).

To enable this feature via the Firebase Admin SDK:
1. Open the [Firebase Console](https://console.firebase.google.com/).
2. Select project **`accessreaper`**.
3. Go to **Project Settings** (gear icon) $\rightarrow$ **Service accounts**.
4. Click **Generate new private key** and confirm.
5. Save or copy the downloaded JSON file to:
   ```text
   D:\AccessReaper-v2\backend\secrets\firebase-service-account.json
   ```
6. Ensure the file path matches `FIREBASE_SERVICE_ACCOUNT_PATH` in `.env`.
7. Restart the backend server.

> **Note on Missing Key:** If the service account file is not present, the backend starts normally and all audit, review, risk rules, scheduler, and reporting functions work without limitation. The Users page will gracefully display a friendly *"Service account not configured"* card with the step-by-step setup instructions.

---

## 5. Phase 2 Features Guide

### 5.1 Workspace User Management (`#users`)
- Located on the sidebar under **MANAGE $\rightarrow$ Users**.
- Displays a pill badge with the count of pending signups.
- Filter by status (`All`, `Pending`, `Active`, `Disabled`) or search by name / email.
- **Activate:** Opens the decision modal requiring an audit note; grants `role: admin`, sets `status: active`.
- **Reject:** Rejects pending signups with a mandatory note.
- **Deactivate:** Revokes access, invalidates Firebase refresh tokens, and disables login.
- *Protected:* Cannot deactivate yourself; cannot deactivate the last active administrator.

### 5.2 Editable Risk Rules (`#settings`)
- Located in **Settings $\rightarrow$ Risk rules**.
- Adjust points for dormancy (90-day default), project mismatch, elevated access, sensitive resources, and toggle named risk rules.
- **Preview Impact:** Calculates risk score deltas across all current assignments in memory without writing to the database. Displays exact before/after counts and affected items.
- **Save as New Version:** Saves versioned config, activates it, and creates an append-only audit event.
- **Version History & Rollback:** View past versions and restore previous weights with one click.

### 5.3 Scheduled Audits (`#settings`)
- Located in **Settings $\rightarrow$ Scheduled audits**.
- Configure scan frequency (`Off`, `Daily`, `Weekly`, `Monthly`), time of day, and day of week.
- Operates in `Asia/Karachi` (PKT) timezone with in-process overlap locking.
- Displays live countdown/timestamp for the **Next scheduled run**.

### 5.4 PDF & CSV Exports
- **Audit PDF Report:** Open any completed audit report in **Access audit**, then click **Download PDF**. Generates a branded, multi-page ReportLab PDF of the frozen snapshot.
- **Audit Findings CSV:** In the audit report dialog, click **Export findings (.csv)** to download an RFC 4180 CSV with UTF-8 BOM and spreadsheet injection protection.
- **Audit Log CSV:** In **History**, click **Export CSV** to download the complete append-only event log.

### 5.5 AI Audit Explanations (Groq primary, Gemini fallback)
- Located on **Dashboard** (Executive summary disclosure with `Groq ✦` badge), **Access audit** report modals, and **Finding details** (`#risk?FND-XXXX`).
- **Configuring Groq:**
  1. Obtain a free API key from the [Groq Console](https://console.groq.com/keys).
  2. Add it to `D:\AccessReaper-v2\backend\.env`:
     ```env
     GROQ_API_KEY=gsk_your_api_key_here
     GROQ_MODEL="openai/gpt-oss-120b"
     LLM_PROVIDER_ORDER="groq,gemini"
     LLM_DAILY_TOKEN_BUDGET=200000
     LLM_MAX_FINDINGS_PER_CALL=6
     ```
  3. The model is chosen by checking available chat models via `GET https://api.groq.com/openai/v1/models` in order: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`.
  4. Never hardcode model names in Python code.
  5. **Privacy:** User emails are pseudonymized (e.g. `User A`) unless `LLM_SEND_REAL_NAMES=true`.
  6. **Connected Services Status:** In **Settings $\rightarrow$ Connected services**, view the live read-only status row showing provider order (`Groq → Gemini`), configured status, and today's token usage vs the 200,000 daily budget.

---

## 6. Running Automated Unit Tests

To run the complete test suite:

```powershell
cd D:\AccessReaper-v2\backend
$env:PYTHONPATH = "D:\AccessReaper-v2\backend"
.\.venv\Scripts\pytest.exe -v
```

To run code linting:
```powershell
.\.venv\Scripts\ruff.exe check .
```

---

## 6. Troubleshooting

- **Port 8100 in use:**  
  Check if another process is using port 8100: `netstat -ano | findstr :8100`. Close the existing process before relaunching.
- **API unavailable — demo mode:**  
  If the FastAPI backend is stopped or network is down, the frontend automatically falls back to local storage demo mode so that the UI remains usable for demonstration.
- **Dev mode refusal:**  
  The app will intentionally refuse to start if `AUTH_MODE=dev` and `HOST` is not `127.0.0.1`.
