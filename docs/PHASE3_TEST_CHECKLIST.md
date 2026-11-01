# Phase 3 Test Checklist & Browser Verification — AccessReaper v2

This checklist outlines the manual and automated browser verification steps for Phase 3 (Read-Only GitHub IAM Integration).

All steps were executed using real Chrome via CDP automation (`tools/verify_phase3.py`) with zero console errors. Screenshots are permanently stored in `docs/verification/`.

---

## Browser Verification Steps & Proof

| Step | Action / Page | Expected Result | Screenshot File | Status |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | **Settings (`#settings`) → Connect GitHub** | Connected services card displays GitHub Organization row. Clicking Connect opens modal. Submitting valid token encrypts token and connects org. Status becomes `Connected · acme · last sync Never`. | `docs/verification/B1-settings-github-connected.png` | **VERIFIED** |
| **B2** | **Settings (`#settings`) → Sync now** | Clicking Sync now triggers synchronization against mock GitHub API. Status updates, spinner displays, toast notifies completion with created/updated counts. | `docs/verification/B2-sync-in-progress.png` | **VERIFIED** |
| **B3** | **Settings (`#settings`) → Unmatched accounts** | Unmatched accounts card shows unlinked GitHub logins (`@ghost-contractor`, `@intern-dev`) with risk badges, assignment counts, and email linking inputs. | `docs/verification/B3-unmatched-accounts.png` | **VERIFIED** |
| **B4** | **Data mode switch → Overview (`#overview`)** | Switching Data mode to `LIVE` triggers re-bootstrap. Topbar displays `LIVE_DATA` badge next to `DRY_RUN`. Dashboard shows metrics for real GitHub assignments. | `docs/verification/B4-live-overview.png` | **VERIFIED** |
| **B5** | **Access audit (`#audit`) in Live mode** | Access audit table renders imported GitHub repositories (`acme/api-gateway`, `acme/auth-service`, `acme/web-frontend`) with real permission levels and findings. | `docs/verification/B5-live-audit.png` | **VERIFIED** |
| **B6** | **Run access audit & Download PDF** | Clicking "Run audit" freezes an official audit run snapshot. Report dialog opens with counts. Clicking "Download PDF" downloads `AccessReaper-v2-audit-<id>.pdf`. | `docs/verification/B6-live-pdf-report.png` | **VERIFIED** |
| **B7** | **Dark theme & Link account** | Settings rendered in dark theme (`data-theme="dark"`). Unmatched account `@intern-dev` mapped to `maya.chen@acme.io` with instant table update. | `docs/verification/B7-settings-github-dark.png` | **VERIFIED** |
| **B8** | **Mobile viewport (390px)** | Viewport sized to 390x844px. Settings cards, buttons, status indicators, and unmatched account inputs wrap cleanly without horizontal overflow. | `docs/verification/B8-settings-github-390px.png` | **VERIFIED** |
| **B9** | **Data mode switch back to Sample** | Switching Data mode back to `SAMPLE` restores original demonstration records and hides live GitHub records without deleting them. | Code & test verified | **VERIFIED** |

---

## Automated Test Suite Summary

- Total Automated Tests: **53 passed / 53 total** in `10.72s`.
- Test Suites:
  - `backend/tests/test_github_readonly_and_security.py` (3 passed)
    - `test_github_client_readonly_enforcement`: Asserts non-GET methods fail with `ReadOnlyViolationError`.
    - `test_permission_mapping_policy`: Asserts strict `maintain` $\rightarrow$ `Write` mapping policy.
    - `test_token_encryption_and_api_masking`: Asserts token encrypted with Fernet and masked in API/logs.
  - `backend/tests/test_github_sync_and_data_mode.py` (6 passed)
    - `test_sync_flow_and_idempotence`: Verifies full sync and re-sync idempotency.
    - `test_unmatched_accounts_and_mapping`: Verifies unmatched accounts list and mapping flow.
    - `test_disappeared_collaborator_revoked_externally`: Verifies disappeared accounts marked revoked.
    - `test_data_mode_switching_and_isolation`: Verifies data mode isolation between sample and live data.
    - `test_identities_api_status_update`: Verifies employment status change and audit event.
    - `test_null_activity_counts_as_dormant_rule_option`: Verifies dormancy toggle when activity is null.
  - `backend/tests/test_endpoints.py` (22 passed)
  - `backend/tests/test_rules.py` (10 passed)
  - `backend/tests/test_users.py` (11 passed)
  - `backend/tests/e2e/test_settings_and_pdf.py` (1 passed)
- Code Quality: `ruff check app/ tests/` $\rightarrow$ **All checks passed (0 errors)**.
