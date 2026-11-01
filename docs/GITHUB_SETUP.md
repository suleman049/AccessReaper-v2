# GitHub Integration Setup Guide — AccessReaper v2

This document describes how to configure and use the read-only GitHub IAM integration in AccessReaper v2.

---

## 1. Absolute Safety Guarantees

AccessReaper v2's GitHub integration is **strictly read-only**:
1. **Zero Write Operations**: The `GitHubClient` implements only `GET` requests. Any attempt to issue `POST`, `PUT`, `PATCH`, or `DELETE` requests to GitHub raises a `ReadOnlyViolationError` and aborts.
2. **Local DRY_RUN Execution**: Remediating or dismissing findings in the UI modifies only AccessReaper's local database. No changes are ever pushed to GitHub.
3. **Token Privacy**: The personal access token is encrypted at rest using AES-128-CBC + HMAC-SHA256 (Fernet) with a key stored in `.env`. It is never transmitted back to the browser (only the last 4 characters are shown), never logged, and never included in error messages.

---

## 2. Generating a Fine-Grained Personal Access Token (PAT)

To connect AccessReaper v2 to a live GitHub organization, create a GitHub Personal Access Token with minimal read-only permissions.

### Recommended: Fine-Grained Token
1. Go to **GitHub → Settings → Developer Settings → Personal access tokens → Fine-grained tokens**.
2. Click **Generate new token**.
3. Set **Token name**: `AccessReaper-v2-Audit-ReadOnly`.
4. Set **Expiration**: e.g., 90 days.
5. Under **Resource owner**, select your target organization (e.g. `acme`).
6. Under **Repository access**, select **All repositories** (or select specific repositories).
7. Configure the following **strictly Read-only** permissions:
   - **Organization permissions**:
     - `Members`: **Read-only** (allows listing organization members and roles).
   - **Repository permissions**:
     - `Metadata`: **Read-only** (mandatory base permission).
     - `Administration`: **Read-only** (required to list collaborators and their permission levels).
     - `Contents`: **Read-only** (required to inspect commit timestamps for activity dormancy evaluation).
8. Click **Generate token** and copy the generated token string (`github_pat_...`).

### Organization SSO Authorization
If your organization enforces SAML Single Sign-On (SSO):
1. Locate your newly generated token in the tokens list.
2. Click **Configure SSO** next to the token.
3. Click **Authorize** next to your organization.

---

## 3. Connecting via AccessReaper UI

1. Open AccessReaper v2 at `http://localhost:8100/`.
2. Navigate to **Settings** (`#settings`).
3. Locate the **Connected services** card.
4. Click the **Connect** button next to **GitHub Organization**.
5. Enter:
   - **GitHub Organization**: Your organization slug (e.g., `acme`).
   - **Personal Access Token**: Paste the fine-grained PAT.
   - **Sync before scheduled audits**: Optional checkbox to pull fresh data automatically before each scheduled audit run.
6. Click **Connect & Verify**.
   - AccessReaper validates the token against `GET /user` and `GET /orgs/{org}`.
   - Upon verification, the token is encrypted and saved, and the status updates to:
     `Connected · <org> · last sync Never`

---

## 4. Running a Sync and Viewing Data

1. Click **Sync now** on the Connected services card.
2. The engine pulls members, outside collaborators, repositories, permissions, and recent commit activity.
3. Review any unlinked logins in the **Unmatched GitHub accounts** card below and map them to employee emails.
4. Click **Data mode: LIVE** to switch your active workspace view to Live data.
5. Navigate to **Overview** or **Access audit** to review live findings, risk scores, and recommendations.
6. Click **Run audit** to freeze an official audit report snapshot and download the server-side PDF.

---

## 5. Offline Demo & Testing via Mock GitHub Server

AccessReaper v2 includes a built-in lightweight mock GitHub server that simulates the Acme organization without needing a real GitHub account.

### Running the Mock Server
In a separate terminal or background task:
```powershell
python tools/mock_github.py --port 8109
```

### Configuring AccessReaper to use the Mock Server
In `backend/.env`:
```env
GITHUB_API_BASE="http://127.0.0.1:8109"
```

Restart the backend server:
```powershell
Start-AccessReaper-v2.cmd
```

In the Settings Connect dialog:
- Organization: `acme`
- Token: any string (e.g., `ghp_mock_pat_1234`)
- Click **Connect & Verify** $\rightarrow$ connects instantly and deterministically!
