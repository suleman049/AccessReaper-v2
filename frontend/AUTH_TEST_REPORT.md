# Authentication test results

Date: October 15, 2026

## Changes

- Removed the normal Firebase/session implementation paragraph from login/signup.
- Replaced the technical footer with organization-access and administrator-approval wording.
- Enabled Email/Password authentication in the existing accessreaper project.
- Provisioned accessreaper-profiles in Mumbai (asia-south1), Enterprise native mode, and deployed own-profile Security Rules.
- Added bounded profile requests so an unavailable service produces a retry state instead of indefinite loading.
- Fixed password-reset confirmation visibility after the form leaves its busy state.

## Passed

- Empty login and invalid-email validation.
- Required signup fields, minimum password length and password confirmation.
- Password show/hide behavior.
- Live signup with a temporary account.
- Live creation of that account's pending Firestore profile.
- Rejection of client self-promotion to Admin.
- Rejection of another user's profile read.
- Dashboard remains inaccessible to pending and signed-out accounts.
- Live login with correct credentials; incorrect credentials rejected.
- Duplicate signup handled.
- Sign out and same-tab session restoration after reload.
- Login/signup layouts in light and dark themes at 1440, 935, 615, 390 and 320 pixels.
- No captured JavaScript runtime errors.

## Limits

Password-reset validation and confirmation were checked with a stub; no external email was sent and actual email delivery was not verified. The user subsequently requested an Admin account; its fresh live login to the overview and Settings sign out were verified. The client route gate is not a substitute for backend token verification. Audit records and permission changes remain local DRY_RUN fixtures.

Temporary Auth test accounts were removed. One generated pending test profile remains in accessreaper-profiles because the combined cleanup/deployment permission request was rejected. Its UID is U8R1TQ2eJfMj6OvUai5aOt6kHbv2. No real user profile needs removal.

## Release status

The updated frontend is now published on https://accessreaper.web.app. A requested Admin account has been activated and its fresh login to the dashboard and sign out verified against the live website. Credentials are not stored in this report. The earlier test-profile cleanup status above remains unchanged.
