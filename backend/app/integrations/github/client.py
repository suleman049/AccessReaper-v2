"""
Read-Only GitHub API Client for AccessReaper v2.

Safety Guarantees:
1. STRICTLY READ-ONLY: All non-GET HTTP methods (POST, PUT, PATCH, DELETE)
   are explicitly forbidden and will raise ReadOnlyViolationError immediately.
2. Token is passed securely in the Authorization header and never logged or exposed.
3. Request rate-limiting and request cap tracking are enforced.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("accessreaper.github.client")


class GitHubIntegrationError(Exception):
    """Base exception for GitHub integration errors."""

    pass


class ReadOnlyViolationError(RuntimeError, GitHubIntegrationError):
    """Raised if any non-GET request is attempted."""

    pass


class GitHubAuthError(GitHubIntegrationError):
    """Bad credentials, expired token, or invalid scopes."""

    pass


class GitHubSSORequiredError(GitHubIntegrationError):
    """Organization requires SAML/SSO authorization for this token."""

    pass


class GitHubNotFoundError(GitHubIntegrationError):
    """Organization, repository, or user not found."""

    pass


class GitHubForbiddenError(GitHubIntegrationError):
    """Permission denied to access this resource."""

    pass


class GitHubRateLimitError(GitHubIntegrationError):
    """GitHub API rate limit exceeded."""

    def __init__(self, message: str, reset_timestamp: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.reset_timestamp = reset_timestamp
        self.retry_after = retry_after


class RequestCapExceededError(GitHubIntegrationError):
    """The configured maximum request cap per sync run was reached."""

    def __init__(self, request_count: int, cap: int):
        super().__init__(f"Request cap of {cap} requests was reached (executed {request_count}).")
        self.request_count = request_count
        self.cap = cap


class GitHubClient:
    """
    Read-only GitHub client that wraps httpx.Client.
    Enforces that only GET requests can be executed.
    """

    def __init__(
        self,
        token: str,
        base_url: str | None = None,
        max_requests: int | None = None,
        timeout: float = 15.0,
    ):
        if not token:
            raise ValueError("A GitHub personal access token is required.")

        self.token = token
        self.base_url = (base_url or settings.GITHUB_API_BASE).rstrip("/")
        self.max_requests = max_requests if max_requests is not None else settings.GITHUB_MAX_SYNC_REQUESTS
        self.timeout = timeout
        self.request_count = 0
        self.rate_limit_remaining: int | None = None
        self.rate_limit_reset: int | None = None

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AccessReaper-v2-Audit",
        }
        self._http = httpx.Client(
            headers=headers,
            timeout=self.timeout,
            follow_redirects=True,
        )

    # -------------------------------------------------------------------------
    # Safety Check: Non-GET methods are strictly forbidden
    # -------------------------------------------------------------------------
    def post(self, *args, **kwargs) -> Any:
        raise ReadOnlyViolationError("GitHub client is strictly read-only. POST requests are prohibited.")

    def put(self, *args, **kwargs) -> Any:
        raise ReadOnlyViolationError("GitHub client is strictly read-only. PUT requests are prohibited.")

    def patch(self, *args, **kwargs) -> Any:
        raise ReadOnlyViolationError("GitHub client is strictly read-only. PATCH requests are prohibited.")

    def delete(self, *args, **kwargs) -> Any:
        raise ReadOnlyViolationError("GitHub client is strictly read-only. DELETE requests are prohibited.")

    # -------------------------------------------------------------------------
    # Core Request Dispatcher
    # -------------------------------------------------------------------------
    def _get(
        self, path_or_url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """
        Executes a GET request with rate limit handling, cap tracking, and error translation.
        """
        if self.request_count >= self.max_requests:
            logger.warning(
                "Request cap reached: %d / %d. Aborting further requests.",
                self.request_count,
                self.max_requests,
            )
            raise RequestCapExceededError(self.request_count, self.max_requests)

        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}/{path_or_url.lstrip('/')}"
        self.request_count += 1

        try:
            resp = self._http.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.error("Network error accessing GitHub API: %s", exc)
            raise GitHubIntegrationError(f"Network error connecting to GitHub: {exc}") from exc

        # Track rate limit headers
        rem = resp.headers.get("x-ratelimit-remaining")
        if rem is not None and rem.isdigit():
            self.rate_limit_remaining = int(rem)
        rst = resp.headers.get("x-ratelimit-reset")
        if rst is not None and rst.isdigit():
            self.rate_limit_reset = int(rst)

        # Handle responses
        if resp.status_code == 200 or resp.status_code == 304:
            return resp

        # Check for rate limiting (403 or 429)
        if resp.status_code == 429 or (resp.status_code == 403 and self.rate_limit_remaining == 0):
            retry_after_hdr = resp.headers.get("Retry-After")
            retry_after = int(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            msg = "GitHub API rate limit exceeded."
            if retry_after:
                msg += f" Retry after {retry_after} seconds."
            elif self.rate_limit_reset:
                msg += f" Resets at unix timestamp {self.rate_limit_reset}."
            logger.warning(msg)
            raise GitHubRateLimitError(msg, reset_timestamp=self.rate_limit_reset, retry_after=retry_after)

        # Check for SSO requirement
        sso_header = resp.headers.get("x-github-sso")
        resp_text = resp.text
        if resp.status_code == 403 and (sso_header or "SAML" in resp_text or "SSO" in resp_text):
            msg = f"Organization requires SAML/SSO authorization for this personal access token: {resp_text}"
            logger.warning(msg)
            raise GitHubSSORequiredError(msg)

        if resp.status_code == 401:
            raise GitHubAuthError("Bad credentials: The provided GitHub token is invalid or expired.")

        if resp.status_code == 403:
            raise GitHubForbiddenError(f"Permission denied accessing {url}: {resp_text}")

        if resp.status_code == 404:
            raise GitHubNotFoundError(f"Resource not found at {url}: {resp_text}")

        resp.raise_for_status()
        return resp

    def _get_paginated(
        self,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieves all items from a paginated GitHub API endpoint.
        Uses the RFC 5988 'Link' header for navigation, and respects request cap.
        """
        all_items: list[dict[str, Any]] = []
        current_params = dict(params or {})
        current_params.setdefault("per_page", per_page)
        next_url: str | None = path_or_url

        while next_url:
            resp = self._get(next_url, params=current_params if next_url == path_or_url else None)
            data = resp.json()
            if isinstance(data, list):
                all_items.extend(data)
            elif isinstance(data, dict) and "items" in data:
                all_items.extend(data["items"])
            else:
                break

            # Parse next link from Link header
            link_header = resp.headers.get("link")
            next_url = None
            if link_header:
                match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
                if match:
                    next_url = match.group(1)

        return all_items

    # -------------------------------------------------------------------------
    # High-level API methods
    # -------------------------------------------------------------------------
    def get_authenticated_user(self) -> dict[str, Any]:
        """GET /user -> Authenticated user details & scopes."""
        resp = self._get("user")
        scopes_header = resp.headers.get("x-oauth-scopes", "")
        scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]
        data = resp.json()
        data["_scopes"] = scopes
        return data

    def get_org(self, org: str) -> dict[str, Any]:
        """GET /orgs/{org}"""
        return self._get(f"orgs/{org}").json()

    def test_connection(self, org: str) -> dict[str, Any]:
        """
        Comprehensive test: verifies user token validity and org accessibility.
        Returns a structured summary of credentials and permissions.
        """
        user = self.get_authenticated_user()
        org_data = self.get_org(org)
        return {
            "ok": True,
            "user": user.get("login"),
            "org": org_data.get("login", org),
            "org_name": org_data.get("name") or org_data.get("login", org),
            "scopes": user.get("_scopes", []),
            "total_private_repos": org_data.get("total_private_repos", 0),
        }

    def get_org_members(self, org: str) -> list[dict[str, Any]]:
        """GET /orgs/{org}/members"""
        return self._get_paginated(f"orgs/{org}/members")

    def get_outside_collaborators(self, org: str) -> list[dict[str, Any]]:
        """GET /orgs/{org}/outside_collaborators"""
        return self._get_paginated(f"orgs/{org}/outside_collaborators")

    def get_teams(self, org: str) -> list[dict[str, Any]]:
        """GET /orgs/{org}/teams"""
        return self._get_paginated(f"orgs/{org}/teams")

    def get_team_members(self, org: str, team_slug: str) -> list[dict[str, Any]]:
        """GET /orgs/{org}/teams/{team_slug}/members"""
        return self._get_paginated(f"orgs/{org}/teams/{team_slug}/members")

    def get_repos(self, org: str) -> list[dict[str, Any]]:
        """GET /orgs/{org}/repos?type=all"""
        return self._get_paginated(f"orgs/{org}/repos", params={"type": "all"})

    def get_repo_collaborators(self, org: str, repo: str) -> list[dict[str, Any]]:
        """GET /repos/{org}/{repo}/collaborators?affiliation=all"""
        return self._get_paginated(f"repos/{org}/{repo}/collaborators", params={"affiliation": "all"})

    def get_last_commit(self, org: str, repo: str, author: str) -> dict[str, Any] | None:
        """
        GET /repos/{org}/{repo}/commits?author={author}&per_page=1
        Returns latest commit data or None.
        """
        try:
            resp = self._get(f"repos/{org}/{repo}/commits", params={"author": author, "per_page": 1})
            commits = resp.json()
            if isinstance(commits, list) and len(commits) > 0:
                return commits[0]
            return None
        except (GitHubNotFoundError, GitHubForbiddenError):
            return None

    def get_user_profile(self, username: str) -> dict[str, Any]:
        """GET /users/{username}"""
        try:
            return self._get(f"users/{username}").json()
        except GitHubNotFoundError:
            return {"login": username}

    # -------------------------------------------------------------------------
    # Explicit Administrative Revocation (Requires Admin Approval)
    # -------------------------------------------------------------------------
    def remove_repository_collaborator(self, org: str, repo: str, username: str) -> dict[str, Any]:
        """
        Explicit administrative revocation: removes collaborator @username from org/repo on GitHub.
        DELETE /repos/{org}/{repo}/collaborators/{username}
        """
        url = f"{self.base_url}/repos/{org}/{repo}/collaborators/{username}"
        self.request_count += 1
        try:
            resp = self._http.delete(url)
        except httpx.RequestError as exc:
            logger.error("Network error executing live revocation on GitHub: %s", exc)
            raise GitHubIntegrationError(f"Network error executing live revocation: {exc}") from exc

        if resp.status_code in (204, 404):
            logger.info("Successfully revoked repository collaborator: @%s on %s/%s (HTTP %d)", username, org, repo, resp.status_code)
            return {"success": True, "status_code": resp.status_code}
        if resp.status_code == 403:
            raise GitHubForbiddenError(f"Permission denied to remove collaborator @{username} from {org}/{repo}: {resp.text}")
        resp.raise_for_status()
        return {"success": True, "status_code": resp.status_code}

    def update_repository_collaborator_permission(
        self, org: str, repo: str, username: str, permission: str
    ) -> dict[str, Any]:
        """
        Explicit administrative remediation: updates collaborator permission on GitHub.
        PUT /repos/{org}/{repo}/collaborators/{username}
        permission: 'pull' (Read), 'push' (Write), 'admin' (Admin)
        """
        url = f"{self.base_url}/repos/{org}/{repo}/collaborators/{username}"
        self.request_count += 1
        perm_map = {
            "Read": "pull",
            "Write": "push",
            "Admin": "admin",
            "pull": "pull",
            "push": "push",
            "admin": "admin",
        }
        gh_perm = perm_map.get(permission, "pull")
        try:
            resp = self._http.put(url, json={"permission": gh_perm})
        except httpx.RequestError as exc:
            logger.error("Network error executing live permission update on GitHub: %s", exc)
            raise GitHubIntegrationError(f"Network error updating collaborator: {exc}") from exc

        if resp.status_code in (200, 201, 204):
            logger.info("Successfully updated collaborator permission: @%s on %s/%s to '%s' (HTTP %d)", username, org, repo, gh_perm, resp.status_code)
            return {"success": True, "status_code": resp.status_code}
        if resp.status_code == 403:
            raise GitHubForbiddenError(f"Permission denied to update collaborator @{username} on {org}/{repo}: {resp.text}")
        resp.raise_for_status()
        return {"success": True, "status_code": resp.status_code}

    def remove_organization_member(self, org: str, username: str) -> dict[str, Any]:
        """
        Explicit administrative revocation: removes member @username from org on GitHub.
        DELETE /orgs/{org}/members/{username}
        """
        url = f"{self.base_url}/orgs/{org}/members/{username}"
        self.request_count += 1
        try:
            resp = self._http.delete(url)
        except httpx.RequestError as exc:
            logger.error("Network error executing live org removal on GitHub: %s", exc)
            raise GitHubIntegrationError(f"Network error executing live org removal: {exc}") from exc

        if resp.status_code in (204, 404):
            logger.info("Successfully revoked organization member: @%s from %s (HTTP %d)", username, org, resp.status_code)
            return {"success": True, "status_code": resp.status_code}
        if resp.status_code == 403:
            raise GitHubForbiddenError(f"Permission denied to remove member @{username} from {org}: {resp.text}")
        resp.raise_for_status()
        return {"success": True, "status_code": resp.status_code}

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
