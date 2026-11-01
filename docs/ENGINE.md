# AccessReaper v2 — Risk Scoring Engine (`backend/app/engine/scoring.py`)

## 1. Architectural Principles

1. **Pure & Deterministic:** The risk engine is completely isolated from database operations, network calls, and framework dependencies. Given the same `IdentityContext`, `ResourceContext`, and permission access parameters, it will always return the identical score, fired rules, risk rating, reasons, and evidence.
2. **Modular & Extensible:** Rules are implemented as independent evaluation stages that emit structured `FiredRule` records, allowing rules and weights to be calibrated or extended without altering database models.
3. **Execution Guarded:** Operates in `DRY_RUN` mode. The engine scores and recommends; it modifies nothing in third-party IAM systems.

---

## 2. Rule Points & Weights

### Base Scoring Rules

| Rule Code | Description | Points | Rationale |
|---|---|:---:|---|
| `UNUSED_90_DAYS` | Permission unused for 90+ days | **+40** | Stale accounts and unexercised privileges represent dormant vulnerability attack surfaces. |
| `PROJECT_MISMATCH` | Permission's project differs from user's team | **+30** | Privilege creep: employees retaining permissions after switching teams or projects. |
| `ELEVATED_ACCESS` | Access level is `Admin` or `Write` | **+20** | Higher impact blast radius if compromised. |
| `SENSITIVE_RESOURCE` | Resource marked as sensitive | **+10** | Mission-critical infrastructure or confidential data stores. |

### Named Frontend-Visible Rules

| Rule Code | Description | Points | Risk Override | Primary Reason |
|---|---|:---:|:---:|---|
| `FORMER_EMPLOYEE_ACTIVE` | Former employee still holding access | **+80** | **High** | *"Former employee account is still active"* |
| `CONTRACTOR_ADMIN` | External contractor holding `Admin` | **+50** | **High** | *"External account has administrator access"* |
| `FIRESTORE_ADMIN_EXCESS` | Firestore app admin exceeding duties | **+50** | **High** | *"Application admin role exceeds support duties"* |
| `DIRECT_ADMIN_POLICY_BYPASS` | Direct admin grant outside team policy | **+40** | **High** | *"Direct admin grant bypasses team policy"* |
| `PRIVILEGED_INACTIVE_30_DAYS` | Privileged access with no recent activity | **+40** | **High** | *"Privileged access with no recent activity"* |

---

## 3. Risk Level Boundaries

$$\text{Risk Level} = \begin{cases} 
\text{High} & \text{if Score} \ge 70 \\
\text{Medium} & \text{if } 40 \le \text{Score} < 70 \\
\text{Low} & \text{if Score} < 40 
\end{cases}$$

- **Score 39:** Evaluates to **Low**
- **Score 40:** Evaluates to **Medium** (lower boundary)
- **Score 69:** Evaluates to **Medium** (upper boundary)
- **Score 70:** Evaluates to **High** (lower boundary)

Unit boundary tests verify these transition edges in `tests/test_scoring.py`.

---

## 4. Recommendation Logic

Matches the frontend governance recommendation engine:

1. **Target Access:**
   - **Former Employee:** $\rightarrow$ `None` (Revoke access entirely)
   - **Firestore Source (Elevated):** $\rightarrow$ `Viewer` (Reduce access to read-only app role)
   - **GitHub Source (Elevated):** $\rightarrow$ `Read` (Reduce access to read-only repo visibility)
   - **Low Risk / Healthy:** $\rightarrow$ Retain current access

2. **Action Label:**
   - If `resolved == True` $\rightarrow$ **"Reviewed"**
   - If `risk == "Low"` $\rightarrow$ **"Keep access"**
   - If `target == "None"` $\rightarrow$ **"Revoke access"**
   - Otherwise $\rightarrow$ **"Reduce access"**

3. **Preserved Evidence Snapshot:**
   Each finding records:
   - Line 1: `Assignment: {access} on {resource} ({source}).`
   - Line 2: `Identity: {role}, {team}; {employment_status_description}.`
   - Line 3: `Last recorded resource activity: {last_activity_text}.`

---

## 5. Seed Calibration Table (All 12 Baseline Assignments)

Every seed record in AccessReaper v2 is calibrated so the backend engine produces the exact risk rating, primary reason, and recommended target present in the teammate frontend demo:

| ID | Identity | Resource (Source) | Access | Inactive | Rules Fired | Score | Risk | Recommended Target | Primary Reason |
|---|---|---|---|---|---|:---:|:---:|:---:|---|
| **FND-2841** | Alex Morgan | `acme/api-gateway` (GitHub) | Admin | 94 days | `ELEVATED` (+20), `SENSITIVE` (+10), `UNUSED_90_DAYS` (+40) | **70** | **High** | `Read` | *Elevated access unused for 94 days* |
| **FND-2842** | Maya Chen | `acme/terraform-cloud` (GitHub) | Admin | 5 days | `ELEVATED` (+20), `SENSITIVE` (+10), `DIRECT_ADMIN_POLICY` (+40) | **70** | **High** | `Read` | *Direct admin grant bypasses team policy* |
| **FND-2843** | Sam Rivera | `acme/customer-portal` (GitHub) | Write | 18 days | `ELEVATED` (+20), `PROJECT_MISMATCH` (+30) | **50** | **Medium** | `Read` | *Team mismatch for repository access* |
| **FND-2844** | Priya Patel | `acme/api-gateway` (GitHub) | Write | 1 day | `ELEVATED` (+20) | **20** | **Low** | `Write` | *Access matches current role* |
| **FND-2845** | Ethan Wright | `acme/data-pipeline` (GitHub) | Admin | 31 days | `ELEVATED` (+20), `SENSITIVE` (+10), `PRIVILEGED_INACTIVE` (+40) | **70** | **High** | `Read` | *Privileged access with no recent activity* |
| **FND-2846** | Olivia Park | `acme/customer-portal` (GitHub) | Write | 3 hours | `ELEVATED` (+20) | **20** | **Low** | `Write` | *Access matches current role* |
| **FND-2847** | Noah Williams | `acme/mobile-app` (GitHub) | Admin | 45 days | `ELEVATED` (+20), `CONTRACTOR_ADMIN` (+50) | **70** | **High** | `Read` | *External account has administrator access* |
| **FND-2848** | Isabella Brown | `acme/release-tools` (GitHub) | Read | 0 days | *(None)* | **0** | **Low** | `Read` | *Read access matches current role* |
| **FND-2849** | Liam Foster | `acme/legacy-service` (GitHub) | Write | 76 days | `ELEVATED` (+20), `FORMER_EMPLOYEE` (+80) | **100** | **High** | `None` | *Former employee account is still active* |
| **FND-2850** | Grace Kim | `Customer support console` (Firestore) | Admin | 12 days | `ELEVATED` (+20), `FIRESTORE_ADMIN_EXCESS` (+50) | **70** | **High** | `Viewer` | *Application admin role exceeds support duties* |
| **FND-2851** | Daniel Brooks | `Content management app` (Firestore) | Editor | 0 days | *(None - standard role)* | **0** | **Low** | `Editor` | *Application role matches current responsibilities* |
| **FND-2852** | Zoe Taylor | `Finance reporting app` (Firestore) | Viewer | 1 day | *(None - viewer role)* | **0** | **Low** | `Viewer` | *Read-only application role matches current responsibilities* |

---

## 6. Audit Run Idempotency

When `POST /api/audits/run` is executed:
- Open findings are re-evaluated.
- Reviewed and remediated findings (`resolved == True`) maintain their historical evidence snapshot and review status without corruption.
- Frozen summary counts and source distributions are generated into a new `AuditRun` record.
- A daily snapshot point is added to the trend ledger.

---

## 7. Dynamic Risk Rule Configuration & Versioning (Phase 2)

In Phase 2, rule weights, dormancy thresholds, and risk boundary cut-offs are fully administrator-configurable while maintaining strict determinism:

### Configuration Schema
```json
{
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
}
```

### Safety Constraints & Validation
- Points: Integers between 0 and 100.
- `dormantDays`: Integer between 1 and 3,650 days.
- Cut-offs: `1 <= mediumMin < highMin <= 200`.
- Immutability: Configurations are saved as versioned records in `rule_configs` table (`version` auto-incrementing, `is_active` boolean). Past versions are never mutated or deleted.
- Rollback: Re-activating an earlier version sets that version as `is_active = True` and writes an audit log entry.
- Dry Preview: `POST /api/rules/preview` evaluates the candidate config against all assignments entirely in memory. It modifies zero database rows and returns a summary comparison and a diff of affected findings.

---

## 8. Scheduled Audits Engine (`backend/app/core/scheduler.py`)

AccessReaper v2 runs an in-process audit scheduler powered by **APScheduler 3.x** (`BackgroundScheduler`).

### Key Specifications:
1. **Timezone:** Fixed to `Asia/Karachi` (PKT, UTC+5).
2. **Frequencies Supported:**
   - `off`: Job paused/removed.
   - `daily`: Fires every day at designated `hour:minute` PKT.
   - `weekly`: Fires every designated `dayOfWeek` (0 = Monday, 6 = Sunday) at `hour:minute` PKT.
   - `monthly`: Fires on the 1st of each month at `hour:minute` PKT.
3. **Overlap Guard:** `threading.Lock` protects the audit runner (`execute_audit_run`). If a manual audit or another scheduled audit is already in flight, the job gracefully aborts without double-running.
4. **Misfire Grace Time:** Configured with `misfire_grace_time = 21600` (6 hours) so that if the server was temporarily sleeping or restarting around the trigger window, the audit will run upon wakeup.
5. **Audit Run Metadata:** Automatically sets `trigger = "scheduled"` and records `actor = "System Scheduler"`.

---

## 9. Server-Side Report & Export Engines

### 9.1 ReportLab PDF Engine (`backend/app/engine/pdf_report.py`)
- Reads the frozen `findings_snapshot` JSON from the `AuditRun` record, ensuring historical reports never change even if subsequent audits remediate access.
- Two-pass canvas (`NumberedCanvas`) dynamically prints `Page X of Y` in the footer.
- Visual elements: Acme header branding, run metadata (Rule version, Trigger, Duration, Actor), KPI summary card, color-coded risk pills, and tabular layout.

### 9.2 RFC 4180 CSV Engine (`backend/app/engine/csv_export.py`)
- **UTF-8 BOM:** Emits `\xef\xbb\xbf` prefix ensuring Microsoft Excel automatically detects UTF-8 characters without encoding corruption.
- **Formula Injection Sanitization:** Any cell value starting with spreadsheet execution triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) is safely prepended with a single quote (`'`), neutralizing DDE and macro injection attacks while keeping the text visible to users.

---

## 7. Phase 3: Real GitHub IAM Scoring Rules & Inactivity Handling

Phase 3 introduces real identity auditing with GitHub accounts, supporting both matched employee profiles and external unmatched accounts.

### A. Unmatched GitHub Accounts Rule
- **Condition**: Account login has no matching employee email in the organization (`is_unmatched == True`).
- **Scoring**:
  - If holding elevated privileges (`Admin` or `Write`): **High** severity (+70 points).
  - If holding standard access (`Read`): **Medium** severity (+40 points).
- **Primary Reason**: `"GitHub account not linked to a known employee"`.
- **Evidence**: `"Identity: GitHub login @{login} is not linked to a known employee."`
- **Recommended Action**: `"Revoke access or link GitHub account"`.

### B. Inactivity & Null Activity Handling
- **Recorded Activity**: When commit activity exists, inactive days are measured against `dormantDays` (default 90). Inactivity $\ge$ 90 days triggers `UNUSED_90_DAYS` (+40 points).
- **Unknown / Null Activity**: When a user holds elevated privileges but no commit history exists in the repository:
  - `last_active_at = None`, `last_active_text = "no recorded activity found"`.
  - Evidence explicitly states: `"Last recorded resource activity: no recorded activity found."`
  - **Rule Option `unknownActivityCountsAsDormant`** (default `False`):
    - By default, null activity is **not** penalized as dormant.
    - If `unknownActivityCountsAsDormant` is toggled `True` in RuleConfig, the engine treats null activity as inactive and fires the dormancy penalty.

### C. Live Data Mode Separation
- When `dataMode == "live"`, the engine exclusively scores and aggregates active GitHub assignments (`origin == "github"` and `external_status != "revoked_externally"`).
- Sample demonstration records remain untouched in the database for instant zero-loss toggling.



---

## 10. Stage 3: Separation of Duties (SoD) & Orphan Account Rules

Stage 3 adds advanced governance rules for cross-repository role conflicts, self-approval integrity enforcement, and orphan account detection across the organization.

### 10.1 Separation of Duties (SoD) Conflicting Access Pairs
- **Database Table (`sod_conflicts`)**: Stores configured cross-resource conflict definitions (`pattern_a`, `access_a`, `pattern_b`, `access_b`, `description`, `points`, `enabled`).
- **Default Seed Rule**:
  - Pair A: `*terraform*` (or `*infra*`) with `Admin` access.
  - Pair B: `*payment*` (or `*billing*`) with `Admin` access.
  - Description: *"Separation of Duties: Infrastructure Admin and Payment/Billing Admin conflict"* (+50 points).
- **Engine Matching**: Checks whether an employee holding an assignment matching Pair A concurrently holds another active assignment matching Pair B (using case-insensitive wildcard matching via `fnmatch`).
- **Scoring & Evidence**:
  - Rule Code: `SOD_CONFLICT` (+50 points default).
  - Primary Reason: `"Separation of duties conflict"`.
  - Evidence: `"Separation of Duties conflict: holds Admin on 'acme/terraform-cloud' and Admin on 'acme/payment-service'."`
  - Recommended Target: `"Read"` (or reduced role).
  - Action Label: `"Reduce access"`.

### 10.2 SoD Approval Integrity Enforcement
- **Enforced Self-Approval Block**: When an administrator calls `POST /api/approvals/{id}/decision`, the engine strictly compares the approver's email (`user.email`) against the requester's email (`req.identity.email`).
- **Violation Action**:
  - Rejects request with **HTTP 409 Conflict** (`code: "SOD_SELF_APPROVAL_FORBIDDEN"`).
  - Appends an immutable security record to `audit_log`:
    - `tag: "Request"`, `title: "Self-approval attempt blocked"`.
    - `detail`: `"Admin {email} attempted to {action} own request {id} for {resource}"`.
    - `tone: "orange"`, `icon: "−"`.

### 10.3 Orphan Account & Bus-Factor Rules

| Rule Code | Description | Points | Recommended Action | Target | Rationale |
|---|---|:---:|:---:|:---:|---|
| `UNMATCHED_GITHUB_ACCOUNT_ELEVATED` | Unmatched account holding Admin/Write | **+70** | `"Revoke access or link GitHub account"` | `None` | Unlinked GitHub accounts holding write/admin privileges expose repos to unverified actors. |
| `UNMATCHED_GITHUB_ACCOUNT` | Unmatched account holding Read | **+40** | `"Link GitHub account"` | `Read` | Unlinked GitHub accounts with read access require employee attribution. |
| `DORMANT_ACTIVE_IDENTITY` | Active employee with zero assignments | **+30** | `"Keep access"` / investigate | `None` | Active directory employees holding zero active resources indicate incomplete onboarding or forgotten accounts. |
| `BUS_FACTOR_SINGLE_ADMIN` | Repository has $\le$ 1 administrator | **+30** | `"Assign owner"` | `Admin` | Single point of failure: repo has no admin redundancy for operational continuity. |
| `ARCHIVED_REPO_ACTIVE_ACCESS` | Archived repository granting Write/Admin | **+40** | `"Revoke access"` | `None` | Archived repos are read-only; retaining active write/admin grants creates dormant risk. |
| `INACTIVE_OUTSIDE_COLLABORATOR` | Outside collaborator inactive > 30 days | **+50** | `"Revoke access"` | `None` | Contractors or outside collaborators holding elevated access without recent activity should be deprovisioned. |

### 10.4 Baseline Calibration Guarantee
All 12 baseline demonstration records (`SEED_PEOPLE`) retain 100% identical risk levels, primary reasons, and action targets under default Stage 3 configuration. Unit and regression tests in `tests/test_stage3.py` verify that no sample record undergoes regression.
