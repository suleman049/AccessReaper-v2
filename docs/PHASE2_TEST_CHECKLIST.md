# AccessReaper v2 — Phase 2 Manual Test Checklist

Use this interactive step-by-step checklist to test and verify all **Phase 2** features in **AccessReaper v2**.

---

### Prerequisites
1. Start AccessReaper v2 by double-clicking `Start-AccessReaper-v2.cmd` (or via `uvicorn app.main:app --host 127.0.0.1 --port 8100` from `backend\`).
2. Open **`http://localhost:8100/#login`** in your browser and log in with your Admin credentials.

---

## Feature 1 — Workspace User Management (`#users`)

### 1.1 Unconfigured State (Graceful Degradation)
- [ ] **Action:** Ensure `backend/secrets/firebase-service-account.json` is not present (or renamed).
- [ ] **Action:** Click **Users** under MANAGE in the left sidebar (or navigate to `http://localhost:8100/#users`).
- [ ] **Expected Result:**
  - A friendly setup card is displayed: *"Service account not configured"*.
  - Displays the 4 clear steps to generate and place `firebase-service-account.json` in `backend/secrets/`.
  - All other app pages (Dashboard, Access audit, Approvals, History, Settings) function normally without error.

### 1.2 User Inventory & Filtering
- [ ] **Action:** Place your valid service account JSON key at `backend\secrets\firebase-service-account.json` (or use test mode).
- [ ] **Action:** Refresh the Users page (`#users`).
- [ ] **Expected Result:**
  - Sidebar nav item **Users** displays a pill badge with the pending signups count.
  - Table renders user profiles: `NAME`, `EMAIL`, `ROLE`, `STATUS`, `REQUESTED DATE`, `ACTIONS`.
  - Status badges appear color-coded (Green for `active`, Yellow for `pending`, Gray for `disabled`).
- [ ] **Action:** Test status filters:
  - Select **Status: Pending** $\rightarrow$ table lists only pending account requests.
  - Select **Status: Active** $\rightarrow$ table lists active administrators.
  - Select **Status: Disabled** $\rightarrow$ table lists deactivated accounts.
- [ ] **Action:** Search box:
  - Type a user's name or email fragment $\rightarrow$ table filters in real-time.

### 1.3 User Activation Flow
- [ ] **Action:** Locate a user with `pending` status and click **Activate**.
- [ ] **Expected Result:**
  - The existing decision modal (`openDecision`) opens with Title *"Activate Admin Access"*.
  - Explanatory copy notes that administrator privileges for organization `acme` will be granted.
  - Mandatory audit note field is displayed.
- [ ] **Action:** Enter note *"Verified by security team"* and click **Confirm**.
- [ ] **Expected Result:**
  - Success toast appears: *"User [email] activated successfully"*.
  - User status badge updates to `active` and role displays `admin`.
  - Pending badge count in the sidebar decrements.
  - In Firestore, document `users/{uid}` updates to `role: "admin", status: "active"`.
  - In **History** (`#history`), an event with tag `User access` and green checkmark is appended.

### 1.4 User Rejection Flow
- [ ] **Action:** Locate a pending signup and click **Reject**.
- [ ] **Expected Result:** Decision modal opens; enter rejection note and confirm.
- [ ] **Action:** Confirm rejection.
- [ ] **Expected Result:**
  - Status updates to `rejected`.
  - Event recorded in audit log.

### 1.5 User Deactivation Flow & Session Invalidation
- [ ] **Action:** Locate an active secondary administrator and click **Deactivate**.
- [ ] **Action:** Enter required justification note and confirm.
- [ ] **Expected Result:**
  - Status updates to `disabled`.
  - User's Firebase refresh tokens are revoked via Admin SDK.
  - Event recorded in audit log.

### 1.6 Safety Guards (Self-Deactivation & Last Admin)
- [ ] **Action:** Attempt to click **Deactivate** on your own logged-in account.
- [ ] **Expected Result:**
  - Error toast appears: *"Admins cannot deactivate their own account"*. Request is blocked with HTTP 400.
- [ ] **Action:** If only 1 active admin remains in the organization, attempt to deactivate that admin.
- [ ] **Expected Result:**
  - Error toast appears: *"Cannot deactivate the last active administrator for organization 'acme'"*. Request is blocked with HTTP 409.

---

## Feature 2 — Editable Risk Rules (`#settings`)

### 2.1 Viewing Active Rule Weights
- [ ] **Action:** Navigate to **Settings** (`#settings`).
- [ ] **Expected Result:**
  - **Risk rules** card is visible alongside General settings.
  - Displays the active version badge (e.g. `v1 Active`).
  - Input controls are populated with default weights:
    - Dormancy threshold: `90` days
    - Dormant permission: `40` pts
    - Project mismatch: `30` pts
    - Elevated access: `20` pts
    - Sensitive resource: `10` pts
    - Cut-offs: High $\ge$ `70`, Medium $\ge$ `40`
    - Named rule checkboxes are enabled.

### 2.2 Dry Preview Impact (Zero DB Mutations)
- [ ] **Action:** Change dormancy threshold from `90` to `30` days and dormant points from `40` to `50`.
- [ ] **Action:** Click **Preview impact**.
- [ ] **Expected Result:**
  - A preview impact box expands below the inputs.
  - Shows summary delta cards: e.g. High (`6 → 7`), Medium (`1 → 2`), Low (`5 → 3`).
  - Table displays list of specific findings whose risk level or reason would change.
- [ ] **Verification:** Check backend database; zero rows in `assignments`, `findings`, or `rule_configs` have been changed.

### 2.3 Saving a New Rule Version
- [ ] **Action:** Click **Save as new version**.
- [ ] **Action:** In the prompt modal, enter reason note: *"Shorten dormancy to 30 days"*.
- [ ] **Action:** Confirm.
- [ ] **Expected Result:**
  - Version indicator updates to `v2 Active`.
  - In **Version History**, a new row appears with Version `2`, your note, creator, and timestamp.
  - In **History** (`#history`), an event with tag `Rules` is recorded.

### 2.4 Version History & Rollback
- [ ] **Action:** In the Version History table on the Risk rules card, find version `1` and click **Restore**.
- [ ] **Expected Result:**
  - Active version reverts to `v1 Active`.
  - Form inputs restore to `90` days and `40` points.
  - Audit event with tag `Rules` and note *"Restored version 1"* is appended.

### 2.5 Validation Boundaries
- [ ] **Action:** Try setting a point value to `150` (> 100) or setting Medium cut-off to `80` while High is `70`.
- [ ] **Expected Result:** Form blocks submission with clear client validation error, or backend rejects with `422 Unprocessable Content`.

---

## Feature 3 — Scheduled Audits (`#settings`)

### 3.1 Configuring the Schedule
- [ ] **Action:** On the **Settings** page, locate the **Scheduled audits** card.
- [ ] **Action:** Select frequency: **Daily**.
- [ ] **Action:** Select time: **03:00** (PKT, Asia/Karachi).
- [ ] **Action:** Click **Save schedule**.
- [ ] **Expected Result:**
  - Success toast appears: *"Audit schedule updated"*.
  - **Next scheduled run** indicator updates with formatted date and time in `Asia/Karachi` timezone (e.g. *"Tomorrow at 03:00 PKT"*).
  - In **History**, an audit log entry with tag `Schedule` is appended.

### 3.2 Schedule Frequency Options
- [ ] **Action:** Test switching frequency to:
  - **Off:** Schedule is disabled; Next Run displays *"Disabled"*.
  - **Weekly:** Day of week selector becomes visible (Monday – Sunday).
  - **Monthly:** Runs on the 1st of every month.

---

## Feature 4 — Server-Side Reports & Exports

### 4.1 Audit PDF Report Download
- [ ] **Action:** Navigate to **Access audit** (`#audit`).
- [ ] **Action:** Click on the latest audit run to open the Audit Report Dialog.
- [ ] **Expected Result:**
  - Report header displays audit metadata and **Rule version** badge (e.g. `Rules v1`).
  - Next to "Export findings (.csv)", a new button **Download PDF** is present.
- [ ] **Action:** Click **Download PDF**.
- [ ] **Expected Result:**
  - File downloads as `audit-AUD-20261014-001-report.pdf`.
  - Open the PDF:
    - Acme Inc. header branding is displayed.
    - KPI summary card matches the audit run counts.
    - Full table of frozen findings with Risk pills, Reasons, Targets, and Evidence.
    - Footer displays two-pass page numbering: `Page 1 of 2`, `Page 2 of 2`.

### 4.2 Audit Findings CSV Export
- [ ] **Action:** In the Audit Report dialog, click **Export findings (.csv)**.
- [ ] **Expected Result:**
  - File downloads as `audit-AUD-20261014-001-findings.csv`.
  - Open in Microsoft Excel or text editor:
    - Opens cleanly with proper column headers.
    - Encoded with UTF-8 BOM (`\xef\xbb\xbf`), no garbled characters.
    - Cell values starting with formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`) are safely escaped with `'`.

### 4.3 Audit Log History CSV Export
- [ ] **Action:** Navigate to **History** (`#history`).
- [ ] **Action:** Click **Export CSV** in the history header.
- [ ] **Expected Result:**
  - File downloads as `accessreaper-audit-history.csv`.
  - Contains complete event trail including `User access`, `Rules`, `Schedule`, and remediation events.

---

## Visual & Theme Verification (Zero UI Regressions)
- [ ] **Light Theme:** Toggle to Light mode $\rightarrow$ Users table, rules sliders, preview cards look native and legible.
- [ ] **Soft Light Theme:** Toggle to Soft Light $\rightarrow$ Card backgrounds and text contrast are preserved.
- [ ] **Dark Theme:** Toggle to Dark mode $\rightarrow$ Backgrounds dark, badges bright, no unstyled white containers.
- [ ] **Mobile Width (< 560px):** Narrow the browser window $\rightarrow$ Users table scrolls or stacks; risk rule sliders wrap cleanly; sidebar drawer collapses.
- [ ] **Phase 1 Baseline Screens:** Verify Dashboard, Access audit, Approvals, and History show zero visual layout shifts or functional regressions.
