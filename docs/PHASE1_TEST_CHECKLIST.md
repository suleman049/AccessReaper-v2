# AccessReaper v2 — Phase 1 Manual Test Checklist

Use this step-by-step checklist to verify all frontend screens and backend API interactions in the browser.

---

### Prerequisites
1. Start the server by double-clicking `Start-AccessReaper-v2.cmd` (or via `uvicorn app.main:app --host 127.0.0.1 --port 8100` from `backend\`).
2. Open **`http://localhost:8100/#login`** in Chrome, Edge, or Firefox.

---

### Step 1: Sign In & Authentication Gate
- [ ] **Action:** Enter your verified Admin credentials and click **Sign in**.
- [ ] **Expected Visual Result:**  
  - Form transitions through "Signing in…".
  - If the profile is pending, the "Workspace access pending" gate is displayed.
  - If the profile is activated (`role: admin, status: active, organizationId: acme`), the dashboard opens automatically.
- [ ] **Backend Verification:**  
  - Server verifies Firebase ID token signature and fetches `users/{uid}` profile from Firestore REST API.
  - `GET /api/me` returns `200 OK`.

---

### Step 2: Overview (Dashboard) Screen
- [ ] **Action:** Navigate to **Overview** (`#dashboard`).
- [ ] **Expected Visual Result:**
  - Workspace title: **Acme, Inc. / Overview**.
  - Metric cards display:
    - **Total identities:** `12` (12 access assignments)
    - **GitHub repositories:** `6` (9 permissions reviewed)
    - **Firestore applications:** `3` (3 application roles)
    - **High-risk access:** `6` (Open findings)
    - **Pending approvals:** `4` (Awaiting a decision)
  - Risk distribution shows: **Low: 5**, **Medium: 1**, **High: 6**.
  - Recommended actions shows: **Reduce access: 6**, **Revoke access: 1**, **Keep access: 5**.
  - Priority review list shows top open findings (Alex Morgan, Maya Chen, Sam Rivera).
- [ ] **Backend Verification:**  
  - `GET /api/bootstrap` and `GET /api/dashboard/summary` return `200 OK`.

---

### Step 3: Access Audit (Inventory & Filters)
- [ ] **Action:** Click **Access audit** in sidebar (`#audit`).
- [ ] **Expected Visual Result:**
  - Permission inventory header shows: **"12 of 12 assignments"**.
  - Table renders with columns: `IDENTITY`, `RESOURCE / SOURCE`, `ACCESS`, `RISK`, `LAST ACTIVE`, `RECOMMENDED ACTION`.
- [ ] **Action:** Test filters:
  - Select **Risk: High** $\rightarrow$ count updates to **"6 of 12 assignments"**.
  - Select **Source: Firestore** $\rightarrow$ shows only 3 Firestore assignments (Grace Kim, Daniel Brooks, Zoe Taylor).
  - Type `"Alex"` in the search box $\rightarrow$ displays only Alex Morgan.
  - Click **Clear filters** $\rightarrow$ restores full 12 assignments list.
- [ ] **Action:** Test pagination: Click page buttons `1 / 2` $\rightarrow$ transitions smoothly across 6 items per page.

---

### Step 4: Finding Details Screen
- [ ] **Action:** In the Access audit table, click **Review** on **Alex Morgan** (`FND-2841`).
- [ ] **Expected Visual Result:**
  - Route changes to `#risk?FND-2841`.
  - Hero banner shows: **Open**, **Original risk High**, **FND-2841**.
  - Headline: *"Elevated access unused for 94 days"*.
  - Current permission: **Admin**.
  - Preserved evidence snapshot shows role, team, source, recorded last activity (94 days ago).
  - Recommended next step shows: **"Reduce Admin to Read"** with outcome explanation.
  - Action buttons visible: **Dismiss finding** and **Reduce Admin to Read**.

---

### Step 5: Remediate Finding Flow
- [ ] **Action:** On Alex Morgan's detail page, click **Reduce Admin to Read**.
- [ ] **Expected Visual Result:**
  - Decision modal appears with title: *"Reduce Admin to Read"*.
  - Summary box states: *"Alex Morgan · acme/api-gateway · Admin → Read"*.
  - Decision comment field is required.
- [ ] **Action:** Leave comment blank and click **Confirm permission change** $\rightarrow$ validation error *"Add a decision comment before continuing."* is displayed.
- [ ] **Action:** Enter comment: `"Confirmed admin role no longer required."` and click **Confirm permission change**.
- [ ] **Expected Visual Result:**
  - Modal closes, toast appears: *"DRY_RUN: sample permission updated; comment saved."*.
  - Finding hero banner status updates to **Remediated**.
  - Current permission updates from **Admin** to **Read**.
  - Next step updates to **Reviewed**.
  - Timeline displays the new event with green checkmark, author, and decision note.
- [ ] **Backend Verification:**  
  - `POST /api/assignments/FND-2841/remediate` returns `200 OK`.
  - Database updates assignment access to `Read`, marks finding `Remediated`, appends `AuditLog` row.
  - Double-clicking or repeating returns `409 Conflict`.

---

### Step 6: Dismiss Finding Flow
- [ ] **Action:** Navigate back to `#audit`, click **Review** on **Sam Rivera** (`FND-2843`, Medium risk).
- [ ] **Action:** Click **Dismiss finding**.
- [ ] **Action:** Enter note: `"Design team requires write access for portal mockup review."` and confirm.
- [ ] **Expected Visual Result:**
  - Toast: *"DRY_RUN: finding dismissed; comment saved."*.
  - Finding status updates to **Dismissed**.
  - Access remains **Write** (permission unchanged).
  - Next step displays **Reviewed**.
- [ ] **Backend Verification:**  
  - `POST /api/assignments/FND-2843/dismiss` returns `200 OK`.

---

### Step 7: Approvals Queue & Approve Decision
- [ ] **Action:** Click **Approvals** in sidebar (`#approvals`).
- [ ] **Expected Visual Result:**
  - Request totals show: **Awaiting review: 4**, **Approved: 2**, **Rejected: 0**, **High-risk pending: 1**.
  - Pending cards list: `REQ-1042` (Maya Chen), `REQ-1041` (Alex Morgan), `REQ-1038` (Noah Williams), `REQ-1035` (Sam Rivera).
- [ ] **Action:** On `REQ-1042` (Maya Chen), click **Approve request**.
- [ ] **Action:** Enter comment: `"Approved repository write access for rotation."` and confirm.
- [ ] **Expected Visual Result:**
  - Toast: *"DRY_RUN: request approved; comment saved."*.
  - `REQ-1042` status badge updates to **Approved**.
  - Approve/Reject buttons disappear on that card.
  - Awaiting review counter decrements from `4` to `3`.
  - In `#audit`, Maya Chen's assignment (`FND-2842`) updates to `Write` and status `Approved change`.
- [ ] **Backend Verification:**  
  - `POST /api/approvals/REQ-1042/decision` returns `200 OK`.
  - Attempting to submit decision again returns `409 Conflict`.

---

### Step 8: Reject Approval Request
- [ ] **Action:** On `REQ-1038` (Noah Williams, Contractor), click **Reject**.
- [ ] **Action:** Enter comment: `"Contractor access must remain read-only."` and confirm.
- [ ] **Expected Visual Result:**
  - Toast: *"DRY_RUN: request rejected; comment saved."*.
  - Card status updates to **Rejected** (red/gray badge).
  - Awaiting review counter decrements to `2`.
  - Noah Williams' assignment remains unchanged.

---

### Step 9: Audit History Ledger
- [ ] **Action:** Click **Audit history** in sidebar (`#history`).
- [ ] **Expected Visual Result:**
  - Decision and activity log shows chronological timeline.
  - The newly created events (`Permission changed`, `Risk finding dismissed`, `Access request approved`, `Access request rejected`) appear at the top with timestamp, author, and delta pills (`Admin → Read`).
- [ ] **Action:** Click on an event card to expand details.
- [ ] **Expected Visual Result:**
  - Event ID, Action, Target, Actor, Karachi timestamp, Permission before, Permission after, and Decision comment are rendered.

---

### Step 10: Run Access Audit
- [ ] **Action:** In topbar or on Access audit screen, click **Run audit**.
- [ ] **Expected Visual Result:**
  - Button state changes to "Auditing…".
  - Audit completed modal dialog pops up:
    - Kicker: `ACCESS AUDIT / REPORT · DRY_RUN`
    - Title: **Audit completed** with report ID (e.g. `AUD-20261021-001`).
    - Summary cards: Assignments checked (12), Identities covered (12), Sources checked (2: GitHub + Firestore).
    - Risk bar visualizes risk breakdown.
    - Source coverage breakdown lists GitHub (6 repos, 9 assignments) and Firestore (3 apps, 3 assignments).
- [ ] **Backend Verification:**  
  - `POST /api/audits/run` executed. New `AuditRun` saved to database.

---

### Step 11: Trend Chart
- [ ] **Action:** Return to **Overview** (`#dashboard`).
- [ ] **Expected Visual Result:**
  - Trend SVG chart renders grid lines, data line and dot markers for recorded days.
- [ ] **Action:** Click between **7 days**, **30 days**, and **90 days** buttons.
- [ ] **Expected Visual Result:**
  - Chart re-renders smoothly for each selected duration without errors.

---

### Step 12: Workspace Global Search
- [ ] **Action:** Press `/` key on keyboard (or click magnifying glass in topbar).
- [ ] **Expected Visual Result:**
  - Command palette modal appears.
  - Type `"api-gateway"`.
  - Suggestions show grouped results:
    - **People:** Alex Morgan, Priya Patel
    - **Resources:** `acme/api-gateway`
    - **Requests:** `REQ-1041` · Alex Morgan
    - **Activity:** Admin access flagged for review
- [ ] **Action:** Press `Down Arrow` and `Enter` $\rightarrow$ navigates directly to the selected resource / finding.

---

### Step 13: CSV Export
- [ ] **Action:** Click **Export CSV** on Access audit page (`#audit`).
- [ ] **Expected Visual Result:**
  - Browser downloads file `accessreaper-audit-sample.csv`.
  - Toast: *"12 sample records exported."*.
  - Open file: contains CSV headers and formatted data rows.

---

### Step 14: Settings & Dev Reset
- [ ] **Action:** Click **Settings** in sidebar (`#settings`).
- [ ] **Expected Visual Result:**
  - Organization banner: **Acme, Inc.**
  - Execution mode: **DRY_RUN · Local simulation**.
  - Current session: Logged-in admin name and email.
- [ ] **Action:** Click **Reset sample data**.
- [ ] **Action:** Click **Reset sample data** in the confirmation modal.
- [ ] **Expected Visual Result:**
  - Toast: *"Sample assignments, audits and decisions restored."*.
  - Assignments and approvals return to baseline sample state.
  - In Audit history (`#history`), a `"Sample workspace reset"` event is recorded at the top, and all previous audit events are safely preserved (the audit log is append-only).
- [ ] **Backend Verification:**  
  - `POST /api/admin/reset-sample` returns `200 OK`.

---

### Step 15: Sign Out
- [ ] **Action:** Click **Sign out** in topbar or Settings.
- [ ] **Expected Visual Result:**
  - Session terminates, route returns to `#login`.
  - Entering protected routes redirects back to login screen.
