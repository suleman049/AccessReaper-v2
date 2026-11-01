# GitHub Permission & Identity Mapping Policy — AccessReaper v2

This document details how GitHub organization roles, repository permissions, collaborator statuses, and user accounts map to AccessReaper v2's IAM data model and risk engine.

---

## 1. Permission Level Translation

GitHub supports roles and granular permission sets on repositories. AccessReaper normalizes these into the standard access levels: `Admin`, `Write`, `Read`.

| GitHub Role / Permission | AccessReaper Access Level | Classification | Rationale & Policy |
| :--- | :--- | :--- | :--- |
| `admin` (or `permissions.admin: true`) | **Admin** | Elevated Privilege | Full control over repository settings, webhooks, collaborators, and branches. |
| `maintain` (or `permissions.maintain: true`) | **Write** | Elevated Privilege | **Strict Rule:** `maintain` is mapped to **Write**, NOT **Admin**. Maintainers cannot delete repositories, manage billing, or transfer ownership. |
| `push` / `write` (or `permissions.push: true`) | **Write** | Elevated Privilege | Read and write access to repository code and branches. |
| `triage` (or `permissions.triage: true`) | **Read** | Standard Access | Can manage issues and pull requests, but cannot write code or alter settings. |
| `pull` / `read` (or `permissions.pull: true`) | **Read** | Standard Access | Read-only clone and view access. Matches baseline developer role. |

---

## 2. Identity Mapping & Account Matching

GitHub users often do not expose public emails on their user profiles or may use personal emails for commits. AccessReaper resolves identity via `github_identity_map`:

### Auto-Matching Procedure
1. Check if an entry exists in `github_identity_map` for the login.
2. If not mapped, inspect the GitHub user profile (`GET /users/{login}`) for a public email or commit author email.
3. If the email matches an existing employee email in `identities.email`:
   - Auto-map: store in `github_identity_map` with `source = 'auto'`.
   - Link assignments to that employee.
4. If no match is found:
   - Create an entry in `github_identity_map` with `email = None`.
   - Create a placeholder identity record (`<login>@github.unmatched`) flagged with `team = 'Unmatched'`.
   - The engine flags this assignment as:
     **"GitHub account not linked to a known employee"**
     - **High** severity if the account holds `Admin` or `Write`.
     - **Medium** severity if the account holds `Read`.

### Manual Linking Flow
1. An administrator views unlinked accounts in **Settings → Unmatched GitHub accounts**.
2. Entering the employee's corporate email (e.g., `alex.morgan@acme.io`) and clicking **Link account** triggers:
   `PUT /api/integrations/github/map/{login}` with `{ "email": "alex.morgan@acme.io" }`.
3. The account is linked (`source = 'manual'`), all existing assignments for that login are updated to the employee's identity, and the risk engine re-evaluates all findings.
4. An immutable audit log entry is recorded with tag `Integration`.

---

## 3. Activity Tracking & Dormancy Evaluation

For users holding elevated permissions (`Admin` or `Write`), AccessReaper queries their latest repository commit:
`GET /repos/{org}/{repo}/commits?author={login}&per_page=1`

### Rules:
- **Recorded Activity**:
  If a commit is found, calculate days inactive: `(now - commit_date).days`.
  If inactivity $\ge$ `dormantDays` (default 90 days), the `UNUSED_90_DAYS` rule fires.
- **Null / Unknown Activity**:
  If no commit is recorded for this login in the repository:
  - Store `last_active_at = None`, `last_active_text = "Not recorded"`.
  - Evidence displays: `Last recorded resource activity: no recorded activity found.`
  - By default, unknown activity is **not** treated as dormant.
  - If the rule option `unknownActivityCountsAsDormant` is toggled `True` in RuleConfig, null activity triggers the dormancy penalty.

---

## 4. Idempotency & Revocation Handling

Each synchronization run is identified by `SYNC-YYYYMMDD-######`:
- **Idempotent Updates**: Re-running sync updates existing repository assignments in place (`assignments_updated`) rather than creating duplicates.
- **Disappeared Collaborators**: If a collaborator was previously imported from GitHub but is no longer present in the organization or repository during a subsequent sync:
  - AccessReaper marks the assignment `external_status = 'revoked_externally'`.
  - The record is **not deleted**, ensuring that historical audit logs, snapshots, and review decisions remain historically verifiable.
- **Reviewed Finding Preservation**: Any finding previously reviewed and marked as `Remediated`, `Dismissed`, or `Approved change` preserves its original review status and snapshot across subsequent sync runs.
