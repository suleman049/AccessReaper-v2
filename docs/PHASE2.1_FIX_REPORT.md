# AccessReaper v2 — Phase 2.1 Fix & Browser Verification Report

**Date:** October 21, 2026  
**Status:** **PART A COMPLETE & BROWSER VERIFIED**  
**Execution Mode:** `DRY_RUN`  
**Host & Port:** `127.0.0.1:8100`  
**Environment:** `ENV=dev`, `AUTH_MODE=dev` (bound to `127.0.0.1` only for automated test checks)

---

## 1. Root Causes & Fixes Applied

### Bug 1: Settings page shows no "Risk rules" card and no "Scheduled audits" card
- **Root Cause 1 (CRLF Byte Replacement Failure):** In `frontend/workspace-design.js`, Windows CRLF (`\r\n`) line endings caused earlier patch attempts on `settings()` to miss target whitespace, leaving lines 20-21 blank. Consequently, the HTML template string returned by `WorkspaceDesign.settings()` never contained the card markup.
- **Root Cause 2 (Script-Scope Variable Isolation):** In non-module scripts, top-level `const RulesSettings = { ... }`, `const ScheduleSettings = { ... }`, and `const UsersPage = { ... }` do not bind as properties of `window`. Checks such as `window.RulesSettings` evaluated to `undefined`, causing conditional renders in `app.js` to omit the cards and fail to initialize or attach event listeners.
- **Root Cause 3 (Post-Render Injection Missing):** `render()` rebuilds `pageContent.innerHTML` on every navigation. Without a defensive post-render hook, even if injected once, the cards were lost on subsequent route transitions.
- **Fix Applied:**
  1. Updated `frontend/workspace-design.js` to include `${typeof RulesSettings !== 'undefined' ? RulesSettings.renderCard() : ''}` and `${typeof ScheduleSettings !== 'undefined' ? ScheduleSettings.renderCard() : ''}` directly in `.settings-main`.
  2. Assigned components explicitly to `window` (`window.RulesSettings = RulesSettings`, `window.ScheduleSettings = ScheduleSettings`, `window.UsersPage = UsersPage`).
  3. Added a defensive post-render hook in `app.js` that checks for `#risk-rules-settings-card` and `#schedule-settings-card` inside `.settings-main` after every `render()` and dynamically injects them if missing, followed by `init()` and `attachEvents()`.
  4. Configured static asset serving in `backend/app/main.py` with `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` for `.js`, `.css`, and `.html` in dev mode so browser caching never hides changes.

### Bug 2: "Download PDF" button in the Run audit report dialog does not work
- **Root Cause 1 (Event Listener Lost on Dynamic Dialog Re-creation):** Direct event listeners attached via `document.querySelector('#download-report-pdf')?.addEventListener(...)` within `ReportDialog.open()` did not reliably trigger on subsequent modal displays or when opened through different code paths.
- **Root Cause 2 (Filename & Header Mismatch in Dev Mode):** `downloadBlob` in `api-client.js` only attached authorization headers if a Firebase user token was present. In dev mode without an active Firebase session, requests were sent unauthenticated. Furthermore, the file download was named `audit-${runId}-report.pdf` rather than `AccessReaper-v2-audit-${runId}.pdf`.
- **Fix Applied:**
  1. Added global document-level event delegation in `frontend/report-dialog.js`:
     ```javascript
     document.addEventListener('click', (e) => {
       const btn = e.target.closest('#download-report-pdf, [data-download-audit-pdf]');
       if (btn) {
         const runId = btn.dataset.runId;
         if (runId && window.ApiClient) ApiClient.downloadPdf(runId);
       }
     });
     ```
  2. Updated `api-client.js` `downloadBlob` to fall back to dev headers (`Bearer dev-token` and `X-Dev-User: jordan.davis@acme.io`) when no Firebase token is active.
  3. Formatted downloaded filename as `AccessReaper-v2-audit-${runId}.pdf`.
  4. Added graceful error handling that surfaces backend error messages via `window.showToast` instead of failing silently.

---

## 2. Files Modified

| File | Change Description |
|---|---|
| `backend/app/main.py` | Added `Cache-Control: no-store` middleware for static files in `ENV=dev`. |
| `frontend/workspace-design.js` | Injected Risk rules and Scheduled audits cards into `settings()`. |
| `frontend/app.js` | Added defensive card injection in `render()` for `#settings` and initialized `UsersPage` for `#users`. |
| `frontend/rules-settings.js` | Bound `window.RulesSettings = RulesSettings`, updated `init()` to refresh card after fetch. |
| `frontend/schedule-settings.js` | Bound `window.ScheduleSettings = ScheduleSettings`, updated `init()` to refresh card after fetch. |
| `frontend/users-page.js` | Bound `window.UsersPage = UsersPage`, ensuring navigation and render hooks fire reliably. |
| `frontend/firebase-client.js` | Bound `window.FirebaseIdentity = FirebaseIdentity`. |
| `frontend/firebase-ui.js` | Bound `window.FirebaseUI = FirebaseUI`. |
| `frontend/report-dialog.js` | Added global event delegation on `document` for `#download-report-pdf`. |
| `frontend/api-client.js` | Added dev auth fallback headers to `downloadBlob()` and updated PDF filename format. |
| `backend/tests/e2e/test_settings_and_pdf.py` | New browser automated smoke regression test asserting cards and PDF button existence. |

---

## 3. Real Browser Verification & Screenshot Proof

All automated browser checks were executed using headless Google Chrome (`chrome.exe`) driving the live server on `http://127.0.0.1:8100`.

| Screenshot File | Step | What It Proves |
|---|:---:|---|
| `docs/verification/A1-settings-risk-rules-light.png` | A1 | **Bug 1 Fixed:** Both "Risk scoring rules" card and "Scheduled audits" card appear in `#settings` in Light mode; clicking "Preview impact" opens the live simulated impact analysis box. |
| `docs/verification/A1-settings-risk-rules-dark.png` | A1 | **Theme Support:** Settings cards render natively in Dark mode (`html[data-theme="dark"]`) with proper contrast and styling. |
| `docs/verification/A1-settings-mobile-390px.png` | A1 | **Mobile Responsiveness:** Risk rules grid and schedule form stack cleanly at 390px phone width without horizontal overflow. |
| `docs/verification/A2-audit-report-dialog-pdf-button.png` | A2 | **Bug 2 Fixed:** Run audit report modal displays the `Rules v1` badge, execution metadata, and the **Download PDF** button (`#download-report-pdf` with `data-run-id="AUD-20261014-001"`). Clicking it triggers blob download. |
| `docs/verification/A3-users-page-friendly.png` | A3 | **Users Screen:** `#users` loads with active navigation indicator and displays the friendly "Service account not configured" setup card with step-by-step instructions. |
| `docs/verification/A4-history-action-filters.png` | A4 | **Action Filters:** `#history` action filter dropdown includes `User access`, `Rules`, and `Schedule` tags alongside original actions. |
| `docs/verification/A5-overview-desktop.png` | A5 | **Original Screen Integrity:** Overview renders exact 12 identities, DRY_RUN badge, risk distribution, and metric cards matching baseline. |
| `docs/verification/A5-overview-dark.png` | A5 | **Original Screen Integrity:** Overview renders properly in Dark mode. |
| `docs/verification/A5-overview-390px.png` | A5 | **Original Screen Integrity:** Overview adapts cleanly to 390px mobile viewport. |
| `docs/verification/A6-audit-desktop.png` | A6 | **Original Screen Integrity:** Access audit table renders 12 assignments with columns, filters, and pagination. |
| `docs/verification/A7-approvals-desktop.png` | A7 | **Original Screen Integrity:** Approvals workbench renders decision queue and pending request cards. |
| `docs/verification/A8-history-desktop.png` | A8 | **Original Screen Integrity:** Audit history timeline renders events, tags, and detail view disclosures. |
| `docs/verification/A9-global-search.png` | A9 | **Original Screen Integrity:** Global search shortcut modal (`/` / `#search-modal`) opens with shortcuts and search box. |

---

## 4. Console Errors Check

- **Console Log Count:** Captured across all page transitions and actions.
- **Console Error Count:** **0** (Zero JavaScript console errors, zero uncaught exceptions).

---

## 5. Items NOT VERIFIED (Explicit Disclosure)

- **Live Firebase Auth Session:** Automated checks were executed against `AUTH_MODE=dev` on loopback `127.0.0.1` as instructed. Live Firebase Authentication with real Google remote servers was **NOT VERIFIED** in this automated headless run because no active user email/password was supplied during the headless browser session.
- **Real Service Account Key Upload:** Generating a live Google Cloud private key was **NOT VERIFIED**; the graceful unconfigured fallback state was verified and confirmed functional.

---

## 6. Test Suite Status

- **Automated Pytest Suite:** **44 / 44 tests passing** (`test_settings_and_pdf_smoke` + 43 backend unit/integration tests).
- **Linter:** `ruff check` passes with **0 errors**.
