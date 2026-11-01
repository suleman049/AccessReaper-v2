# AccessReaper

## Current implementation

Firebase email/password authentication and Firestore-managed account authorization are wired into the existing frontend. New accounts require administrator activation. Audit findings and permission decisions remain local **DRY_RUN sample data**; no live repository/application permissions are changed.

**Start here:** [Firebase setup guide](FIREBASE_SETUP.md). Publish the provided Firestore rules, enable Email/Password, and launch `Start-AccessReaper.cmd` to open `http://localhost:4173/#login`. Authentication requires internet and a web-server URL; the standalone HTML is no longer an offline authentication bypass.

Password handling is provided by Firebase Authentication. This frontend does not implement custom BCrypt authentication. Firebase Email/Password and Mumbai profile storage are configured. Live signup/login and pending-role protection have been exercised; see AUTH_TEST_REPORT.md.

## Project roadmap and background

The following describes the broader project direction; it is not a statement that all backend features are implemented.

A rule-based **Identity and Access Management (IAM) audit system** that finds unnecessary and risky user access, scores the risk, and removes it after admin approval.

## Problem
When employees change projects or roles, their old permissions often stay active (**privilege creep**). Stale admin access and dormant accounts are a common cause of data breaches, and manual access reviews are slow and error-prone.

## Solution
AccessReaper scans an organization's users, projects, and permissions, flags excess access, explains why it is risky, and recommends an action. Nothing changes until an admin approves it, and every decision is saved in an audit log.

## Features
- Secure admin login (BCrypt hashing, session timeout)
- Overview dashboard: users, projects, risks by level, pending approvals
- **Run Access Audit** button
- Rule-based risk scoring (HIGH / MEDIUM / LOW) with a clear reason for each finding
- Findings table with filters and sorting
- Approve / Reject workflow (revoke or downgrade access)
- Append-only audit log of every admin action

## Risk Scoring Rules
| Rule | Points |
|---|---|
| Permission unused for 90+ days | +40 |
| Permission project differs from user's current project | +30 |
| Access level is Admin or Write | +20 |
| Project is marked sensitive | +10 |

**Levels:** 70+ = HIGH (remove), 40-69 = MEDIUM (downgrade), below 40 = LOW (keep)

## Tech Stack
- **Java** (Servlets/JSP, JDBC): backend and audit engine
- **SQL** (MySQL or SQLite): data storage
- **HTML and CSS**: admin dashboard
- **BCrypt**: password hashing
- **Git and GitHub**: collaboration

## Security Measures
- PreparedStatements for all SQL (SQL injection protection)
- Output encoding (XSS protection)
- CSRF tokens on approve and reject actions
- Authorization checks on every protected page
- Append-only audit log
- No secrets committed to the repository

## InfoSec Concepts Covered
Least privilege, privilege creep, access review (ISO 27001 A.5.18, A.8.2), dormant access, risk assessment, accountability, CIA triad.

## Project Structure
```
/src        Java code (servlets, services, DAO, models)
/webapp     HTML, CSS, JSP pages
/database   Schema and seed SQL
/docs       PRD, report, slides
```

## Getting Started
1. Clone the repository: `git clone <repo-url>`
2. Install JDK, Apache Tomcat, and MySQL (or SQLite)
3. Run the scripts in `/database` (schema first, then seed data)
4. Add your database settings to a local config file (do not commit it)
5. Deploy to Tomcat and open `http://localhost:8080/accessreaper`

## Git Workflow
- `main`: stable, demo-ready
- `dev`: integration branch
- `feature/<name>`: one branch per task
- Changes go in through pull requests with at least one review

## Team
| Role | Member |
|---|---|
| Database and Data Layer | Member 1 |
| Audit Engine and Approval Logic | Member 2 |
| Authentication and Security | Member 3 |
| Dashboard UI and Documentation | Member 4 |

## Limitations
The system manages access inside its own simulated database and is not connected to real GitHub, Active Directory, or cloud IAM. Real integration is future work.

## Future Work
- AI-generated explanations for findings (Groq / Gemini)
- Separation of Duties and orphan account rules
- Scheduled audits and CSV/PDF reports
- Real integrations (GitHub, LDAP)

## Live Hosting

Production site: https://accessreaper.web.app

Deployed to existing project `accessreaper`, using web app ID `1:265796097385:web:c80028b46704a883c099f8`.

`build-hosting.cjs` builds an explicit set of website files into generated `dist/`. Hosting predeploy runs this build automatically. Repository internals, setup documents, rules, server scripts and local files are excluded from the published directory. Generated `dist/` and `.firebase/` are ignored by Git.

To publish future website changes:

```text
npx -y firebase-tools@latest deploy --only hosting --project accessreaper
```

This deployment publishes Hosting only; it does not publish Firestore rules or enable Authentication providers. The production index returned HTTP 200 and matched the local index.html after this release. Live sign-in/account activation has not been exercised.


## Firebase account verification

The live profile database is `accessreaper-profiles` in Mumbai (`asia-south1`), Enterprise native mode with Firestore data access and realtime role updates. New accounts remain pending; no real user was promoted during testing. See [Authentication test results](AUTH_TEST_REPORT.md). The earlier incompatible empty database was removed; the app does not use it.


Current release: updated authentication screens and accessreaper-profiles configuration are published. The requested Admin account was activated through trusted operator access, and a fresh live Admin login to the overview plus sign out succeeded. Credentials are not included in repository or website files.
