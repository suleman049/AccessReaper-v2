# AccessReaper v2 — Frontend Changes Log

This document lists every single modification made to the teammate frontend relative to the untouched backup in `_frontend_original_backup\`.

As mandated by the Phase 1 specifications:
- **Zero changes** were made to the visual look, layout, HTML structure, CSS stylesheets, class names, copy text, icons, or client-side routing.
- The modifications are strictly confined to a **thin data layer** connecting the existing UI to the new FastAPI backend.
- Full **demo fallback** is preserved: if `?demo=1` is provided in the URL or the API is unreachable, the application falls back to local storage sample mode with the notification toast `"API unavailable — demo mode"`.

---

## 1. Summary of File Diffs

| File | Status | Nature of Changes |
|---|---|---|
| `frontend/api-client.js` | **NEW** | Added fetch wrapper with Firebase token attachment, error toasts, and API methods. |
| `frontend/index.html` | **MODIFIED** | Added `<script src="api-client.js"></script>` tag in head script loading list. |
| `frontend/governance.js` | **MODIFIED** | Added API delegation hooks to `resolve()`, `approve()`, `runAudit()`, and `reset()`. |
| `frontend/app.js` | **MODIFIED** | Triggered `ApiClient.loadAndRender()` when Firebase authorizes the user. |

---

## 2. Line-by-Line Changes

### A. `frontend/api-client.js` (NEW FILE)
- Provides `window.ApiClient`.
- Automatically calls `FirebaseIdentity.user.getIdToken()` to attach `Authorization: Bearer <token>`.
- Intercepts error responses (401, 403, 409, 422) and surfaces user feedback via `window.showToast()`.
- Implements:
  - `bootstrap()` $\rightarrow$ `GET /api/bootstrap`
  - `remediate(id, note)` $\rightarrow$ `POST /api/assignments/{id}/remediate`
  - `dismiss(id, note)` $\rightarrow$ `POST /api/assignments/{id}/dismiss`
  - `decideApproval(id, action, note)` $\rightarrow$ `POST /api/approvals/{id}/decision`
  - `runAudit()` $\rightarrow$ `POST /api/audits/run`
  - `resetSample()` $\rightarrow$ `POST /api/admin/reset-sample`
  - `syncState(data)` $\rightarrow$ Populates `people`, `approvals`, `history`, `auditRuns`, `auditSnapshots`, and `lastAudit`.
  - `loadAndRender()` $\rightarrow$ Fetches bootstrap data and calls `render()`. Falls back to demo mode if unavailable.

---

### B. `frontend/index.html`
**Line 60:** Added `<script src="api-client.js"></script>` before governance scripts.

```html
<!-- BEFORE -->
<script src="firebase-ui.js"></script><script src="audit-summary.js"></script>

<!-- AFTER -->
<script src="firebase-ui.js"></script><script src="api-client.js"></script><script src="audit-summary.js"></script>
```

---

### C. `frontend/governance.js`

1. **`Governance.resolve(id, dismiss)` (Line 56):**
   - Added check: if `window.ApiClient && !window.ApiClient.isDemoMode`, calls `ApiClient.dismiss(p.id, note)` or `ApiClient.remediate(p.id, note)`, reloads bootstrap data via `ApiClient.bootstrap()`, syncs state, and re-renders. Falls back to local memory if API is unreachable.

2. **`Governance.approve(id, action)` (Line 57):**
   - Added check: if `window.ApiClient && !window.ApiClient.isDemoMode`, calls `ApiClient.decideApproval(a.id, action, note)`, refreshes bootstrap state, and re-renders. Falls back to local memory if API is unreachable.

3. **`Governance.runAudit()` (Line 60):**
   - Added check: if `window.ApiClient && !window.ApiClient.isDemoMode`, calls `ApiClient.runAudit()`, refreshes bootstrap state, re-renders, and opens report dialog with `this.report(rep.id)`.

4. **`Governance.reset()` (Line 62):**
   - Added check: if `window.ApiClient && !window.ApiClient.isDemoMode`, calls `ApiClient.resetSample()`, refreshes bootstrap state, shows feedback, and re-renders.

---

### D. `frontend/app.js`
**Line 144:** Added listener for `identity-changed` event to fetch server data as soon as the user is verified by Firebase Auth:

```javascript
document.addEventListener('identity-changed', () => {
  if (window.FirebaseIdentity?.authorized && window.ApiClient && !ApiClient.loaded) {
    ApiClient.loadAndRender();
  } else if (!window.FirebaseIdentity?.authorized && window.ApiClient) {
    ApiClient.loaded = false;
  }
});
```

---

## 3. Phase 2 Additions (Strictly Additive)

In Phase 2, all original screens remain visually and structurally intact. All new features are additive and reuse the existing design tokens, CSS classes, card components, buttons, and decision modals.

### 3.1 New Files
| File | Purpose |
|---|---|
| `frontend/phase2.css` | Additive CSS for the Users page layout, rule weight grid, preview diff box, and schedule controls. Works seamlessly in light, dark, and mobile viewports. |
| `frontend/users-page.js` | Component implementing `window.UsersPage`. Handles status filtering (`all`, `pending`, `active`, `disabled`), search, user card table, and wires Activate/Reject/Deactivate to the existing `openDecision` modal. |
| `frontend/rules-settings.js` | Component implementing `window.RulesSettings`. Renders editable risk weight sliders/inputs in Settings, triggers live dry-preview impact calculation, and provides version history rollback. |
| `frontend/schedule-settings.js` | Component implementing `window.ScheduleSettings`. Renders scheduled audit controls (Frequency, Hour, Minute, Weekday) and live Next Run indicator. |

### 3.2 Additive Modifications to Existing Files

#### `frontend/index.html`
- Linked `phase2.css`: `<link rel="stylesheet" href="phase2.css">`.
- Added **Users** navigation link under `MANAGE` in the sidebar (`<a href="#users" class="nav-item"...>`).
- Included a `<span id="usersNavPendingBadge" class="nav-badge hidden">0</span>` for pending signups count.
- Added `<div id="usersPageMount"></div>` container.
- Loaded new scripts: `users-page.js`, `rules-settings.js`, `schedule-settings.js`.

#### `frontend/api-client.js`
- Added user management endpoints: `listUsers()`, `activateUser(uid, note)`, `deactivateUser(uid, note)`, `rejectUser(uid, note)`.
- Added risk rules endpoints: `getRules()`, `saveRules(config, note)`, `activateRuleVersion(version)`, `previewRules(config)`.
- Added schedule endpoints: `getSchedule()`, `saveSchedule(payload)`, `getNextRun()`.
- Added blob download helpers: `downloadAuditPdf(auditId)`, `downloadAuditCsv(auditId)`, `downloadHistoryCsv()`.

#### `frontend/app.js`
- Registered the `#users` route in the router.
- Added route dispatching to render `UsersPage.render()` into `#usersPageMount`.
- Added `updateUsersPendingBadge()` to update the sidebar badge on load.

#### `frontend/workspace-design.js`
- Injected `RulesSettings.renderCard()` and `ScheduleSettings.renderCard()` into `SettingsScreen.render()`.

#### `frontend/report-dialog.js`
- Added Rule Version badge display to the audit report metadata header.
- Added **Download PDF** button triggering `ApiClient.downloadAuditPdf()`.
- Added **Export findings (.csv)** button triggering `ApiClient.downloadAuditCsv()`.

#### `frontend/governance.js`
- Added `User access`, `Rules`, and `Schedule` tags to the history view action filter.
- Bound the **Export CSV** button in the History tab to `ApiClient.downloadHistoryCsv()`.

---

## 4. Phase 3: GitHub Integration & Data Mode Additions

### Summary of Rules
1. Existing screens remain visually and structurally identical to original designs.
2. All new components are strictly additive, placed in new files (`frontend/github-settings.js`), reusing existing CSS design system variables, cards, buttons, badges, tables, and modals.
3. Minimal surgical hooks applied to `frontend/index.html`, `frontend/api-client.js`, `frontend/app.js`, and `frontend/phase2.css`.

### Changed & Created Files:

#### 1. `frontend/github-settings.js` (NEW FILE - 310 lines)
- Implements `window.GitHubSettings` component.
- Dynamically enriches the **Connected services** card on the Settings page:
  - Updates GitHub Organization row to reflect connection status: `Connected · <org> · last sync <timestamp>` or `Not connected`.
  - Buttons: **Connect** (modal with org and password-type PAT input), **Sync now** (with spinner and result toast), **Disconnect** (with confirmation), and **Data mode** switch.
- Injects the **Unmatched GitHub accounts** card below Connected services:
  - Lists unlinked logins with risk badges, assignment counts, employee email inputs, and **Link account** action buttons.
- Injects the `LIVE_DATA` badge into topbar headers when in `live` data mode.
- Attaches to `hashchange` and `DOMContentLoaded` events.

#### 2. `frontend/phase2.css` (APPENDED STYLES)
- `.live-data-badge`: Styled badge matching `.dry-run-badge` with blue tone (`#eff6ff`, border `#3b82f6`, text `#1d4ed8`).
- `[data-theme='dark'] .live-data-badge`: Dark theme equivalent (`#172554`, border `#2563eb`, text `#93c5fd`).
- `.gh-service-details`, `.gh-actions-bar`: Flexbox containers for connection actions.
- `.unmatched-list`, `.unmatched-item`, `.unmatched-info`, `.unmatched-action`: Responsive row styling.
- `@media (max-width: 576px)`: Responsive stacking for mobile phone widths (390px).

#### 3. `frontend/index.html` (LINE 61)
- Added `<script src="github-settings.js"></script>` prior to `app.js`.

#### 4. `frontend/api-client.js` (LINES 219–285, 320)
- Added HTTP helper methods: `get(path)`, `post(path, body)`, `put(path, body)`, `delete(path)`.
- Added Phase 3 integration methods:
  - `getGitHubStatus()`
  - `configureGitHub(org, token, syncBeforeAudit)`
  - `disconnectGitHub()`
  - `testGitHub(org, token)`
  - `syncGitHub()`
  - `getUnmatchedGitHub()`
  - `mapGitHubAccount(login, email)`
  - `getDataMode()`
  - `setDataMode(mode)`
  - `updateIdentityStatus(email, status, note)`
- Synced `dataMode` into `window.currentDataMode` during `syncState(data)`.
- Exported `window.ApiClient = ApiClient;`.

#### 5. `frontend/app.js` (LINES 348–353)
- Added post-render initialization hook: `if (typeof GitHubSettings !== 'undefined') GitHubSettings.init();`.
- Added header badge update hook: `if (typeof GitHubSettings !== 'undefined') GitHubSettings.updateHeaderBadge();`.

---

## 5. Preservation of Untouched Backup

The directory `D:\AccessReaper-v2\_frontend_original_backup\` remains 100% untouched and matches the original teammate archive byte-for-byte.


---

## 5. Stage 1 Additions (Fully Automatic Audits)

- `frontend/automation-timer.js` (NEW): Provides `window.AutomationTimer` managing live countdown clock, polling `/api/automation/status`, pause/resume modal handlers, and auto-refreshing UI on audit completion.
- `frontend/index.html`: Added `<script src="automation-timer.js"></script>`.
- `frontend/app.js`: Replaced manual "Run audit" / "Run access audit" buttons with countdown chip rendering via `window.AutomationTimer.renderChip()`.
- `frontend/workspace-design.js`: Replaced manual audit card with "Automatic audits" schedule card in settings.

---

## 6. Stage 2 Additions (Triage Quality for Real Data)

- `frontend/users-page.js`:
  - Added segmented tab control (`#users-tab-bar`) with tabs "Workspace Admins" and "People (Identities)".
  - Added `renderPeopleTab()` with employee search bar, "+ Add Person" modal, "Edit Person" modal, and "Import CSV" modal integration.
  - Return `container.outerHTML` from `render()` to guarantee proper string HTML injection into `#page-content`.
- `frontend/github-settings.js`:
  - Added "Auto-suggest matches", "Import CSV", and "Save all links" bulk actions.
  - Added per-account classification dropdown (`User`, `Bot`, `Service`, `Ignored`) with confirm modal requiring explanatory note.
  - Added CSV import preview and confirmation dialog (`openCsvImportModal()`).
- `frontend/governance.js`:
  - Added "Why this score?" breakdown card (`.why-score-panel`) to finding details (`Governance.detail()`), displaying calculated risk points, risk badge, and triggered rule modifiers with points.
- `frontend/rules-settings.js`:
  - Added editable weights for unmatched account standard (+40 pts) and elevated (+70 pts).
- `frontend/api-client.js`:
  - Added `bulkMapGitHubAccounts(mappings)`, `getGitHubAutoSuggestions()`, `classifyGitHubAccount(login, accountType, note)`.
  - Added `getIdentities()`, `createIdentity(data, note)`, `previewCsvImport(csvText)`, `confirmCsvImport(csvText, note)`.


---

## 7. Stage 3 Additions (Separation of Duties & Orphan Rules)

- `frontend/rules-settings.js`:
  - Added "Separation of Duties & Orphan Rules" section to Risk rules card in Settings.
  - Added editable point weights and enable/disable checkboxes for `sodConflict` (default 50), `busFactor` (default 30), `archivedRepo` (default 40), `inactiveOutsideCollaborator` (default 50), and `dormantIdentity` (default 30).
  - Included the new fields in `getFormPayload()` and `getDefaultConfig()`.
- `frontend/api-client.js`:
  - Added `getSoDConflicts()` $\rightarrow$ `GET /api/rules/sod`
  - Added `createSoDConflict(conflict)` $\rightarrow$ `POST /api/rules/sod`
  - Added `updateSoDConflict(id, conflict)` $\rightarrow$ `PUT /api/rules/sod/{id}`
  - Added `deleteSoDConflict(id, note)` $\rightarrow$ `DELETE /api/rules/sod/{id}`

---

## 8. Stage 4 Additions (AI Explanations & Notifications Center)

- `frontend/notifications-center.js` (NEW):
  - In-app notification center managing topbar bell button, live unread counter badge, and dropdown notification feed.
  - Supports marking notifications as read (`POST /api/notifications/{id}/read`), marking all read (`POST /api/notifications/read-all`), and auto-refreshing every 30 seconds.
  - Event-specific badges and routing for: audit completed, high-risk findings, overdue approvals, sync degradation, audit paused, and user pending activation.
- `frontend/notifications-settings.js` (NEW):
  - Injects the **Notifications & Alerts** card into the `#settings` page.
  - Displays In-App Alerts status, SMTP configuration indicator (`SMTP Configured` / `SMTP Not Configured`), daily email digest toggle (`emailDigestEnabled`), and **Send test email** trigger button with live feedback toasts.
- `frontend/audit-summary.js`:
  - Replaced static preview stub with dynamic AI explanation adapter.
  - Shows `Gemini ✦` badge with advisory disclaimer `"AI-generated — verify before acting"` when generated by live Gemini; falls back cleanly to deterministic template with `Gemini · Preview` badge on fallback/offline.
- `frontend/governance.js`:
  - In finding detail view (`Governance.detail()`), dynamically injects the plain-language AI explanation, recommended next step, and advisory label.
- `frontend/api-client.js`:
  - Added notification methods: `getNotifications()`, `markNotificationRead(id)`, `markAllNotificationsRead()`, `getNotificationPreferences()`, `updateNotificationPreferences(data)`, and `sendTestEmail()`.
- `frontend/index.html`:
  - Added notification bell button with unread count badge to `.topbar-actions`.
  - Added `<script src="notifications-center.js"></script>` and `<script src="notifications-settings.js"></script>`.
- `frontend/phase2.css`:
  - Added responsive styles for `.notification-wrap`, `.notification-bell`, `.notification-badge`, `.notification-panel`, `.notification-item`, `.notif-unread-dot`, dark theme overrides, and mobile stacking for 390px phone widths.

---

## 9. Groq Integration Follow-Up Changes

- `frontend/audit-summary.js`:
  - Updated `AuditSummary.getProvider()`: dynamically inspects `report.aiSummary.model` and `status` to determine the active provider label (`Groq` for Groq models like `openai/gpt-oss-120b`, `Gemini` for Gemini models, `Template` on fallback).
  - Replaced hardcoded `Gemini ✦` / `Gemini · Preview` with dynamic `${provider} ✦` (e.g. `Groq ✦`) and `${provider} · Preview` (e.g. `Template · Preview`) using the existing badge and card styling.
- `frontend/governance.js`:
  - In finding detail view (`Governance.detail()`), updated policy context badge from hardcoded `Gemini ✦` to dynamic provider badge: `${f.aiStatus==='success' ? ((f.aiModel && f.aiModel.includes('gemini')) ? 'Gemini ✦' : 'Groq ✦') : 'Template · Preview'}`.
- `frontend/workspace-design.js`:
  - Added read-only "AI explanations" service row to the **Connected services** card in `#settings`.
  - Displays: Provider order (`Groq → Gemini`), configured status, and daily token usage counter (`0 / 200,000`).
- `frontend/github-settings.js`:
  - Added `renderAIStatus(servicesCard)`: dynamically updates the "AI explanations" row with live provider order, configured flags (`Groq: Yes · Gemini: No`), and today's token usage from `window.llmStatus` / `ApiClient.getLLMStatus()`.
- `frontend/api-client.js`:
  - Added `getLLMStatus()` method calling `GET /api/llm/status`.
  - Updated `syncState(data)` to store `data.llmStatus` on `window.llmStatus` from bootstrap payload.

---

## 10. Leftover "Gemini" and "Preview" Label Fixes

- `frontend/workspace-design.js`:
  - In `auditOverview()`, replaced hardcoded `<summary><span>✦ Audit summary <small>Gemini · Preview</small></span>` with dynamic `<summary><span>${AuditSummary.disclosureHeader(report)}</span>`.
  - The disclosure header dynamically derives from the latest audit run: renders `✦ Audit summary <small>Groq ✦</small>` when live Groq generated it, and `Audit summary <small>Summary</small>` without an AI badge when template fallback is active.
- `frontend/audit-summary.js`:
  - Added `disclosureHeader(report)` and updated `preview(report)`:
    - Live AI: badge is `${provider} ✦`, mark is `✦`, disclaimer is `Generated by ${provider} — verify before acting`, aria-label is `Latest audit summary generated by ${provider}`.
    - Template fallback: badge is `Summary` (no AI badge `✦`, no `Preview` label), mark is omitted, disclaimer is `Generated from report data`, aria-label is `Latest audit summary generated from report data`.
- `frontend/governance.js`:
  - In finding detail view (`Governance.detail()`, line 51):
    - When live AI (`aiStatus === 'success'`): badge is `${provider} ✦`, label is `AI risk explanation:`, disclaimer is `Generated by ${provider} — verify before acting`.
    - When template (`aiStatus !== 'success'`): badge is `Summary`, label is `Policy check:`, disclaimer is `Generated from report data`.
    - When `!f.aiExplanation`: displays `<strong>Policy check:</strong> ${safe(f.originalReason)}. Generated from report data.` without claiming disconnected or preview AI.
- `frontend/firebase-config.js`:
  - Neutralized comment on line 2 from `Never put a service-account key or Gemini secret in this file` to `Never put a service-account key or API secret in this file`.
- `frontend/README.md`:
  - Updated line 93 to `AI-generated explanations for findings (Groq / Gemini)`.
- `backend/tests/test_groq_and_llm.py`:
  - Added `test_no_leftover_gemini_or_preview_labels_in_frontend()` asserting that `Gemini · Preview` and `Live Gemini` do not exist in any frontend file.

