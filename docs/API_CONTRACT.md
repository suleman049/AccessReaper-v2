# AccessReaper v2 — API Contract (Phase 1)

**Product:** AccessReaper v2  
**Base URL:** `http://127.0.0.1:8100/api`  
**Data Format:** JSON (camelCase properties matching frontend expectations)  
**Authentication:** HTTP Bearer token (`Authorization: Bearer <Firebase_ID_Token>`) on all endpoints except `/api/health`.

---

## 1. Authentication & Security Headers

### Request Headers
- `Authorization`: `Bearer <token>` (Firebase ID token)
- `X-Dev-User`: (Optional, only when `AUTH_MODE=dev` bound to `127.0.0.1`) e.g. `jordan.davis@acme.io`
- `Content-Type`: `application/json` (for mutating requests)

### Response Headers
- `X-Request-ID`: Unique UUID for request tracing
- `X-Content-Type-Options`: `nosniff`
- `X-Frame-Options`: `DENY`
- `Referrer-Policy`: `strict-origin-when-cross-origin`
- `Content-Security-Policy`: Restricts scripts, styles, fonts, and connects to self, CDN and Firebase endpoints.

---

## 2. Standard Error Format

All error responses return a standardized error object:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation of error."
  }
}
```

### Common HTTP Status Codes
- `200 OK`: Request succeeded.
- `401 Unauthorized`: Missing, invalid, or expired Firebase authentication token (`MISSING_TOKEN`, `INVALID_TOKEN`).
- `403 Forbidden`: User profile is not active, lacks admin role, or belongs to another organization (`FORBIDDEN`, `ACCOUNT_INACTIVE`, `ORGANIZATION_MISMATCH`).
- `404 Not Found`: Resource or finding does not exist (`NOT_FOUND`).
- `409 Conflict`: Double-submit or action already decided (`ALREADY_DECIDED`).
- `422 Unprocessable Content`: Validation failure on request parameters or body (`VALIDATION_ERROR`).
- `429 Too Many Requests`: Rate limit exceeded on mutating endpoints (`RATE_LIMIT_EXCEEDED`).
- `500 Internal Server Error`: Unexpected server exception.

---

## 3. Endpoints

### 3.1 Health Check
- **Route:** `GET /health`
- **Auth:** None (Public)
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "product": "AccessReaper v2",
  "version": "2.0.0",
  "mode": "DRY_RUN",
  "env": "dev"
}
```

---

### 3.2 Current Authenticated User
- **Route:** `GET /me`
- **Auth:** Bearer Token
- **Response `200 OK`:**
```json
{
  "uid": "1X48k29aL...",
  "email": "jordan.davis@acme.io",
  "name": "Jordan Davis",
  "role": "admin",
  "status": "active",
  "organizationId": "acme"
}
```

---

### 3.3 Bootstrap Workspace
Returns all dataset collections in a single call to populate frontend state at boot.
- **Route:** `GET /bootstrap`
- **Auth:** Bearer Token (`admin` role required)
- **Response `200 OK`:**
```json
{
  "people": [
    {
      "id": "FND-2841",
      "name": "Alex Morgan",
      "email": "alex.morgan@acme.io",
      "initials": "AM",
      "role": "Senior Engineer",
      "team": "Platform",
      "repo": "acme/api-gateway",
      "source": "GitHub",
      "access": "Admin",
      "risk": "High",
      "last": "94 days ago",
      "lastActiveAt": "2026-07-12T10:30:00+05:00",
      "reason": "Elevated access unused for 94 days",
      "resolved": false,
      "reviewedAt": null,
      "finding": {
        "id": "FND-2841",
        "originalReason": "Elevated access unused for 94 days",
        "originalSeverity": "High",
        "originalAccess": "Admin",
        "detectedAt": "2026-10-14T09:42:00+05:00",
        "status": "Open",
        "snapshot": {
          "role": "Senior Engineer",
          "team": "Platform",
          "source": "GitHub",
          "lastActiveAt": "2026-07-12T10:30:00+05:00",
          "lastActivity": "94 days ago"
        },
        "evidence": [
          "Assignment: Admin on acme/api-gateway (GitHub).",
          "Identity: Senior Engineer, Platform; active employee.",
          "Last recorded resource activity: 94 days ago."
        ]
      }
    }
  ],
  "approvals": [
    {
      "id": "REQ-1042",
      "person": "Maya Chen",
      "email": "maya.chen@acme.io",
      "initials": "MC",
      "repo": "acme/terraform-cloud",
      "access": "Write",
      "reason": "Replace direct administrator access with repository write access for on-call coverage",
      "requested": "12 min ago",
      "requestedAt": "2026-10-14T10:18:00+05:00",
      "type": "Role change",
      "risk": "Medium",
      "status": "Pending"
    }
  ],
  "history": [
    {
      "id": "EVT-SEED-0",
      "day": "Today, October 14",
      "date": "2026-10-14",
      "time": "9:42 AM",
      "occurredAt": "2026-10-14T09:42:00+05:00",
      "icon": "−",
      "tone": "orange",
      "title": "Admin access flagged for review",
      "actor": "AccessReaper risk engine",
      "detail": "acme/api-gateway · Alex Morgan",
      "tag": "Risk detected",
      "note": "",
      "source": "GitHub",
      "assignmentId": "FND-2841",
      "requestId": null,
      "auditId": null,
      "before": null,
      "after": null,
      "mode": "DRY_RUN",
      "changes": []
    }
  ],
  "auditRuns": [
    {
      "id": "AUD-20261014-001",
      "completedAt": "2026-10-14T09:56:00+05:00",
      "status": "Completed",
      "actor": "Jordan Davis",
      "scope": ["GitHub", "Firestore"],
      "assignments": 12,
      "identities": 12,
      "high": 6,
      "medium": 1,
      "healthy": 5,
      "resolved": 0,
      "sources": [
        {"source": "GitHub", "assignments": 9, "resources": 6},
        {"source": "Firestore", "assignments": 3, "resources": 3}
      ],
      "sample": true,
      "mode": "DRY_RUN"
    }
  ],
  "auditSnapshots": [
    {
      "at": "2026-10-14T09:56:00+05:00",
      "label": "Initial sample baseline",
      "high": 6,
      "medium": 1,
      "healthy": 5,
      "resolved": 0,
      "assignments": 12,
      "remediated": 1
    }
  ],
  "lastAudit": "Oct 14, 2026, 9:56 AM"
}
```

---

### 3.4 Dashboard Summary & Trend
- **Route:** `GET /dashboard/summary`
- **Response `200 OK`:**
```json
{
  "identities": 12,
  "assignments": 12,
  "github": 9,
  "firestore": 3,
  "high": 6,
  "medium": 1,
  "healthy": 5,
  "resolved": 0,
  "pending": 4
}
```

- **Route:** `GET /dashboard/trend?days=7`
- **Query Params:** `days` (default 7, options: 7, 30, 90)
- **Response `200 OK`:**
```json
[
  {"date": "2026-10-08", "high": null, "remediated": null},
  {"date": "2026-10-09", "high": null, "remediated": null},
  {"date": "2026-10-10", "high": null, "remediated": null},
  {"date": "2026-10-11", "high": null, "remediated": null},
  {"date": "2026-10-12", "high": null, "remediated": null},
  {"date": "2026-10-13", "high": null, "remediated": null},
  {"date": "2026-10-14", "high": 6, "remediated": 1}
]
```

---

### 3.5 Assignments Inventory & Finding Review
- **Route:** `GET /assignments`
- **Query Params:**
  - `risk`: `All risks` | `High` | `Medium` | `Low`
  - `access`: `All access levels` | `Admin` | `Write` | `Read` | `Editor` | `Viewer` | `None`
  - `source`: `All sources` | `GitHub` | `Firestore`
  - `user`: email filter
  - `resource`: resource name filter
  - `action`: `All actions` | `Reduce access` | `Revoke access` | `Keep access` | `Reviewed`
  - `q`: search string
  - `page`: 1-based page number (default: 1)
  - `pageSize`: items per page (default: 6)
- **Response `200 OK`:**
```json
{
  "items": [ /* array of PersonSchema */ ],
  "total": 12,
  "page": 1,
  "pageSize": 6
}
```

- **Route:** `GET /assignments/{id}`
- **Response `200 OK`:**
```json
{
  "assignment": { /* PersonSchema */ },
  "recommendation": {
    "title": "Reduce Admin to Read",
    "body": "The recorded inactivity indicates elevated access may no longer be needed. Confirm the business need with the resource owner before proceeding.",
    "target": "Read",
    "outcome": "Retain read visibility and remove elevated privileges; the finding will be marked Remediated."
  },
  "timeline": [ /* array of HistoryEventSchema */ ],
  "relatedRequests": [ /* array of ApprovalSchema */ ]
}
```

- **Route:** `POST /assignments/{id}/remediate`
- **Body:**
```json
{
  "note": "Confirmed with resource owner that admin privileges are no longer needed."
}
```
- **Response `200 OK`:** Returns updated `PersonSchema` with `resolved: true`, `finding.status: "Remediated"`, and updated access level.

- **Route:** `POST /assignments/{id}/dismiss`
- **Body:**
```json
{
  "note": "Temporary grant approved for active migration."
}
```
- **Response `200 OK`:** Returns updated `PersonSchema` with `resolved: true`, `finding.status: "Dismissed"`, and original access level preserved.

---

### 3.6 Approvals Queue & Decisions
- **Route:** `GET /approvals?status=Pending&q=`
- **Response `200 OK`:** Array of `ApprovalSchema` objects.

- **Route:** `POST /approvals/{id}/decision`
- **Body:**
```json
{
  "action": "Approved",
  "note": "Approved write access for incident rotation."
}
```
- **Response `200 OK`:** Returns updated `ApprovalSchema`.
- **Response `409 Conflict`:** If request is not in `Pending` state.

---

### 3.7 Audits Execution
- **Route:** `POST /audits/run`
- **Response `200 OK`:**
```json
{
  "id": "AUD-20261021-001",
  "completedAt": "2026-10-21T17:45:00+05:00",
  "status": "Completed",
  "actor": "Jordan Davis",
  "scope": ["GitHub", "Firestore"],
  "assignments": 12,
  "identities": 12,
  "high": 6,
  "medium": 1,
  "healthy": 5,
  "resolved": 0,
  "sources": [
    {"source": "GitHub", "assignments": 9, "resources": 6},
    {"source": "Firestore", "assignments": 3, "resources": 3}
  ],
  "sample": true,
  "mode": "DRY_RUN"
}
```

- **Route:** `GET /audits`
- **Response `200 OK`:** Array of `AuditRunSchema` objects.

- **Route:** `GET /audits/{id}`
- **Response `200 OK`:** Specific `AuditRunSchema` object.

---

### 3.8 Audit History Ledger
- **Route:** `GET /history?range=Last 30 days&action=All actions&q=&page=1&pageSize=6`
- **Response `200 OK`:**
```json
{
  "items": [ /* array of HistoryEventSchema */ ],
  "total": 9,
  "page": 1,
  "pageSize": 6
}
```

---

### 3.9 Workspace Global Search
- **Route:** `GET /search?q=api-gateway`
- **Response `200 OK`:**
```json
{
  "identities": [
    {
      "id": "FND-2841",
      "name": "Alex Morgan",
      "email": "alex.morgan@acme.io",
      "role": "Senior Engineer",
      "team": "Platform",
      "assignmentId": "FND-2841"
    }
  ],
  "resources": [
    {
      "name": "acme/api-gateway",
      "source": "GitHub"
    }
  ],
  "requests": [
    {
      "id": "REQ-1041",
      "person": "Alex Morgan",
      "repo": "acme/api-gateway",
      "status": "Pending",
      "access": "Write"
    }
  ],
  "events": [
    {
      "id": "EVT-SEED-0",
      "title": "Admin access flagged for review",
      "detail": "acme/api-gateway · Alex Morgan",
      "actor": "AccessReaper risk engine",
      "tag": "Risk detected"
    }
  ]
}
```

---

### 3.10 Admin Sample Data Reset (Development Only)
- **Route:** `POST /admin/reset-sample`
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "message": "Sample assignments, audits and decisions restored."
}
```
*Note: Restores baseline sample entities while keeping the append-only `audit_log` intact.*

---

## 4. Phase 2 Endpoints

### 4.1 Workspace User Management (`/api/users`)
All user management endpoints require administrator authorization (`role: admin`, `status: active`, `organizationId: acme`).

#### `GET /api/users`
Lists user profiles from Firestore for organization `acme`. If the service account key is unconfigured, returns `configured: false` with friendly setup instructions.
- **Query Parameters:**
  - `status`: Filter by profile status: `all` (default), `pending`, `active`, `disabled`.
  - `q`: Search substring across name and email (case-insensitive).
- **Response `200 OK`:**
```json
{
  "configured": true,
  "message": "Service account configured and connected.",
  "users": [
    {
      "uid": "user-uid-123",
      "name": "Jordan Davis",
      "email": "jordan.davis@acme.io",
      "role": "admin",
      "status": "active",
      "organizationId": "acme",
      "createdAt": "2026-10-14T09:00:00Z"
    }
  ]
}
```

#### `POST /api/users/{uid}/activate`
Activates a user account, setting `role: admin`, `status: active` in Firestore. Writes an append-only audit log entry and clears the profile cache.
- **Request Body:**
```json
{
  "note": "Verified by security lead for admin onboarding."
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "User jordan.davis@acme.io activated successfully.",
  "uid": "user-uid-123",
  "role": "admin",
  "newStatus": "active"
}
```

#### `POST /api/users/{uid}/deactivate`
Deactivates a user account, setting `status: disabled` in Firestore. Role stays recorded. Revokes all Firebase refresh tokens for the user and invalidates backend profile cache.
- **Safety Guards:**
  - Admin cannot deactivate themselves (returns `400 Bad Request`, `SELF_DEACTIVATION_FORBIDDEN`).
  - Cannot deactivate the last active administrator for organization `acme` (returns `409 Conflict`, `LAST_ADMIN_PROTECTION`).
- **Request Body:**
```json
{
  "note": "Departing contractor privileges revoked."
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "User jordan.davis@acme.io deactivated successfully.",
  "uid": "user-uid-123",
  "newStatus": "disabled"
}
```

#### `POST /api/users/{uid}/reject`
Rejects a pending signup request, setting `status: rejected` in Firestore. Writes an audit log entry.
- **Request Body:**
```json
{
  "note": "Applicant not recognized."
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "User request rejected.",
  "uid": "user-uid-123",
  "newStatus": "rejected"
}
```

---

### 4.2 Editable Risk Rules (`/api/rules`)

#### `GET /api/rules`
Returns the active rule configuration and the version history list.
- **Response `200 OK`:**
```json
{
  "active": {
    "version": 1,
    "config": {
      "dormantDays": 90,
      "points": {
        "dormant": 40,
        "projectMismatch": 30,
        "elevatedAccess": 20,
        "sensitiveResource": 10
      },
      "rulesEnabled": {
        "formerEmployee": true,
        "externalAdmin": true,
        "firestoreAdmin": true,
        "directAdminBypass": true,
        "privilegedInactive": true
      },
      "thresholds": {
        "highMin": 70,
        "mediumMin": 40
      }
    },
    "note": "Initial baseline weights (Phase 1 calibration)",
    "createdBy": "System Seeder",
    "createdAt": "2026-10-14T09:00:00Z",
    "isActive": true
  },
  "versions": [ ... ]
}
```

#### `POST /api/rules`
Saves a new active rule configuration version. Automatically deactivates the previously active version and writes an audit log entry with actor, before/after version, and note.
- **Request Body:**
```json
{
  "config": { ... },
  "note": "Shorten dormancy threshold from 90 to 60 days."
}
```
- **Response `201 Created`:** returns the created `RuleConfigItem`.

#### `POST /api/rules/{version}/activate`
Restores/rolls back to an earlier rule configuration version.
- **Safety Guards:**
  - Cannot activate an already active version (returns `409 Conflict`).
  - Returns `404 Not Found` if the version does not exist.
- **Response `200 OK`:** returns the activated `RuleConfigItem`.

#### `POST /api/rules/preview`
Dry preview calculation that scores all current assignments against candidate rule configuration in memory. **Does not write to the database or modify assignments.**
- **Request Body:**
```json
{
  "config": { ... }
}
```
- **Response `200 OK`:**
```json
{
  "summary": {
    "high": 6,
    "medium": 2,
    "low": 4,
    "currentHigh": 6,
    "currentMedium": 1,
    "currentLow": 5,
    "deltaHigh": 0,
    "deltaMedium": 1,
    "deltaLow": -1
  },
  "changes": [
    {
      "assignmentId": "ASN-101",
      "person": "Sam Rivera",
      "repo": "acme/customer-portal",
      "currentRisk": "Medium",
      "previewRisk": "High",
      "currentReason": "Team mismatch for repository access",
      "previewReason": "Team mismatch for repository access",
      "currentTarget": "Read",
      "previewTarget": "Read"
    }
  ]
}
```

---

### 4.3 Scheduled Audits (`/api/schedule`)

#### `GET /api/schedule`
Returns the current audit schedule configuration.
- **Response `200 OK`:**
```json
{
  "frequency": "weekly",
  "hour": 2,
  "minute": 0,
  "dayOfWeek": 0,
  "timezone": "Asia/Karachi",
  "enabled": true,
  "updatedAt": "2026-10-21T18:00:00Z",
  "updatedBy": "Jordan Davis"
}
```

#### `PUT /api/schedule`
Updates the audit schedule, reconfigures the in-process APScheduler background job, and logs the change to `audit_log`.
- **Request Body:**
```json
{
  "frequency": "daily",
  "hour": 3,
  "minute": 30,
  "dayOfWeek": 0,
  "enabled": true,
  "note": "Enable daily 03:30 PKT access scans"
}
```
- **Response `200 OK`:** returns updated `ScheduleResponse`.

#### `GET /api/schedule/next-run`
Returns the next scheduled execution timestamp in ISO 8601 PKT, or `null` if disabled/off.
- **Response `200 OK`:**
```json
{
  "enabled": true,
  "frequency": "daily",
  "nextRunAt": "2026-10-22T03:30:00+05:00",
  "nextRunAtFormatted": "Thu, Oct 22, 2026, 03:30 PKT",
  "timezone": "Asia/Karachi"
}
```

---

### 4.4 Server-Side Reports & Exports

#### `GET /api/audits/{id}/report.pdf`
Generates a multi-page PDF report for the frozen audit snapshot using ReportLab.
- **Headers:** `Content-Type: application/pdf`, `Content-Disposition: inline; filename="audit-{id}-report.pdf"`
- **Content:** Acme header branding, execution metadata, rule version tag, trigger type, KPI summary box, and complete table of frozen findings with Risk pills, Reasons, Targets, and Evidence. Dynamic page numbering (`Page X of Y`).

#### `GET /api/audits/{id}/findings.csv`
Exports the frozen findings snapshot to RFC 4180 compliant CSV.
- **Headers:** `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="audit-{id}-findings.csv"`
- **Features:** Prepended UTF-8 BOM (`\xef\xbb\xbf`) for Microsoft Excel compatibility, strict formula injection protection escaping leading `=`, `+`, `-`, `@`, `\t`, `\r` with `'`.

#### `GET /api/history.csv`
Exports the append-only `audit_log` events to RFC 4180 CSV with UTF-8 BOM, timestamps in PKT, actor, tag, before/after state, note, and formula injection sanitization.
- **Headers:** `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="accessreaper-audit-history.csv"`

---

## 8. Phase 3: GitHub IAM Integration & Workspace Data Mode

All Phase 3 endpoints require administrator privileges (`require_role('admin')`).

### `GET /api/integrations/github/status`
Returns integration status, configured organization, token mask, latest sync metadata, and active data mode.
- **Response 200:**
  ```json
  {
    "connected": true,
    "org_name": "acme",
    "token_last4": "1234",
    "scopes": ["read:org", "repo"],
    "last_sync": {
      "id": "SYNC-20261021-001",
      "started_at": "2026-10-21T15:20:00Z",
      "finished_at": "2026-10-21T15:20:02Z",
      "status": "ok",
      "request_count": 8,
      "repos_count": 3,
      "members_count": 4,
      "collaborators_count": 2,
      "assignments_created": 7,
      "assignments_updated": 0,
      "assignments_revoked": 0,
      "error_summary": null
    },
    "sync_before_audit": true,
    "data_mode": "live"
  }
  ```

### `PUT /api/integrations/github/config`
Tests and verifies the token against GitHub, stores it encrypted at rest (AES-128-CBC + HMAC-SHA256 via Fernet), and appends an audit event.
- **Request Body:**
  ```json
  {
    "org": "acme",
    "token": "ghp_...",
    "sync_before_audit": true
  }
  ```
- **Response 200:** Returns updated `GitHubStatusResponse`. Never echoes plain token.

### `DELETE /api/integrations/github/config`
Disconnects the GitHub integration by wiping the stored encrypted token. Existing imported data is preserved.
- **Response 200:** Returns updated `GitHubStatusResponse` (`connected: false`).

### `POST /api/integrations/github/test`
Performs an active connectivity and permission test against the GitHub API.
- **Request Body (optional):** `{"org": "acme", "token": "ghp_..."}`
- **Response 200:**
  ```json
  {
    "ok": true,
    "message": "Successfully connected to organization 'acme' as @audit-admin.",
    "user": "audit-admin",
    "org": "acme",
    "scopes": ["read:org", "repo"]
  }
  ```

### `POST /api/integrations/github/sync`
Triggers synchronization of organization members, outside collaborators, repositories, and collaborator permissions.
- **Idempotency:** Re-running sync updates existing records in place. Disappeared collaborators are marked `revoked_externally`.
- **Response 200:** Returns `GitHubSyncRunSummary`.

### `GET /api/integrations/github/unmatched`
Returns all GitHub logins discovered during sync that are not yet linked to an employee email.
- **Response 200:**
  ```json
  [
    {
      "login": "ghost-contractor",
      "name": "Ghost Contractor",
      "assignments_count": 1,
      "highest_risk": "High",
      "assignments": [
        {
          "id": "FND-2853",
          "resource": "acme/api-gateway",
          "access_level": "Admin",
          "risk": "High"
        }
      ]
    }
  ]
  ```

### `PUT /api/integrations/github/map/{login}`
Maps an unlinked GitHub login to an employee email, updates assignments, re-evaluates risk, and writes an audit event.
- **Request Body:** `{"email": "alex.morgan@acme.io"}`
- **Response 200:** `{"ok": true, "login": "ghost-contractor", "email": "alex.morgan@acme.io", "updated_assignments": 1}`

### `GET /api/integrations/github/mode`
Returns active data mode (`{"data_mode": "sample" | "live"}`).

### `PUT /api/integrations/github/mode`
Switches workspace data mode between `sample` and `live`. Writes an audit event.
- **Request Body:** `{"data_mode": "live"}`
- **Response 200:** `{"data_mode": "live"}`

### `PUT /api/identities/{email}`
Updates an employee's employment status (`active`, `former`, `contractor`). Re-evaluates risk on all assignments belonging to that identity and appends an audit event.
- **Request Body:**
  ```json
  {
    "employment_status": "former",
    "note": "Alex Morgan departed Acme, Inc. on Oct 20"
  }
  ```
- **Response 200:**
  ```json
  {
    "ok": true,
    "email": "alex.morgan@acme.io",
    "employment_status": "former",
    "updated_assignments": 2
  }
  ```
