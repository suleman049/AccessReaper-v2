"""
Standalone Mock GitHub API Server for AccessReaper v2.
Runs on 127.0.0.1:8109 (or port passed via --port / PORT env var).
Provides fake GitHub API responses for deterministic demos, local testing, and browser verification.

Usage:
    python tools/mock_github.py
    python tools/mock_github.py --port 8109
"""

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mock_github")

MOCK_USERS = {
    "alexmorgan": {"login": "alexmorgan", "id": 101, "name": "Alex Morgan", "email": "alex.morgan@acme.io"},
    "mayachen": {"login": "mayachen", "id": 102, "name": "Maya Chen", "email": "maya.chen@acme.io"},
    "marcusvance": {"login": "marcusvance", "id": 103, "name": "Marcus Vance", "email": "marcus.vance@acme.io"},
    "ghost-contractor": {"login": "ghost-contractor", "id": 104, "name": "Ghost Contractor", "email": None},
    "erostova": {"login": "erostova", "id": 201, "name": "Elena Rostova", "email": "elena.rostova@external.io"},
    "intern-dev": {"login": "intern-dev", "id": 202, "name": "Intern Dev", "email": None},
    "audit-admin": {"login": "audit-admin", "id": 999, "name": "Audit Administrator", "email": "jordan.davis@acme.io"},
}

MOCK_REPOS = [
    {
        "id": 401,
        "name": "api-gateway",
        "full_name": "acme/api-gateway",
        "private": True,
        "default_branch": "main",
        "description": "Production edge API gateway",
    },
    {
        "id": 402,
        "name": "auth-service",
        "full_name": "acme/auth-service",
        "private": True,
        "default_branch": "main",
        "description": "OAuth and identity token issuer",
    },
    {
        "id": 403,
        "name": "web-frontend",
        "full_name": "acme/web-frontend",
        "private": False,
        "default_branch": "main",
        "description": "Customer web dashboard",
    },
]

MOCK_REPO_COLLABORATORS = {
    "api-gateway": [
        {
            "login": "alexmorgan",
            "role_name": "admin",
            "permissions": {"admin": True, "maintain": True, "push": True, "triage": True, "pull": True},
        },
        {
            "login": "marcusvance",
            "role_name": "admin",
            "permissions": {"admin": True, "maintain": True, "push": True, "triage": True, "pull": True},
        },
        {
            "login": "ghost-contractor",
            "role_name": "admin",
            "permissions": {"admin": True, "maintain": True, "push": True, "triage": True, "pull": True},
        },
    ],
    "auth-service": [
        {
            "login": "mayachen",
            "role_name": "maintain",
            "permissions": {"admin": False, "maintain": True, "push": True, "triage": True, "pull": True},
        },
        {
            "login": "erostova",
            "role_name": "admin",
            "permissions": {"admin": True, "maintain": True, "push": True, "triage": True, "pull": True},
        },
    ],
    "web-frontend": [
        {
            "login": "alexmorgan",
            "role_name": "push",
            "permissions": {"admin": False, "maintain": False, "push": True, "triage": True, "pull": True},
        },
        {
            "login": "intern-dev",
            "role_name": "pull",
            "permissions": {"admin": False, "maintain": False, "push": False, "triage": False, "pull": True},
        },
    ],
}

MOCK_COMMITS = {
    ("api-gateway", "alexmorgan"): [
        {"sha": "c1a2b3", "commit": {"author": {"date": "2026-10-18T10:15:00Z"}, "message": "feat: rate limiter update"}}
    ],
    ("api-gateway", "marcusvance"): [
        {"sha": "d4e5f6", "commit": {"author": {"date": "2026-06-25T14:30:00Z"}, "message": "chore: legacy routing"}}
    ],
    ("api-gateway", "ghost-contractor"): [],
    ("auth-service", "mayachen"): [
        {"sha": "a7b8c9", "commit": {"author": {"date": "2026-10-19T11:00:00Z"}, "message": "fix: jwt claim validation"}}
    ],
    ("auth-service", "erostova"): [
        {"sha": "e1f2a3", "commit": {"author": {"date": "2026-10-06T09:15:00Z"}, "message": "refactor: token store"}}
    ],
    ("web-frontend", "alexmorgan"): [
        {"sha": "f9e8d7", "commit": {"author": {"date": "2026-10-15T16:00:00Z"}, "message": "style: navigation bar"}}
    ],
    ("web-frontend", "intern-dev"): [],
}


class MockGitHubHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: any, extra_headers: dict | None = None):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("x-ratelimit-remaining", "4999")
        self.send_header("x-ratelimit-reset", "1792600000")
        self.send_header("x-oauth-scopes", "read:org, repo")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = urllib.parse.parse_qs(parsed.query)

        logger.info("Mock GitHub: GET %s", self.path)

        # 1. GET /user
        if path == "/user":
            self._send_json(200, MOCK_USERS["audit-admin"])
            return

        # 2. GET /orgs/{org}
        if path.startswith("/orgs/") and len(path.split("/")) == 3:
            org = path.split("/")[2]
            self._send_json(200, {
                "login": org,
                "id": 5001,
                "name": "Acme, Inc.",
                "description": "Acme IAM Test Organization",
                "total_private_repos": 2,
            })
            return

        # 3. GET /orgs/{org}/members
        if path.startswith("/orgs/") and path.endswith("/members"):
            members = [
                MOCK_USERS["alexmorgan"],
                MOCK_USERS["mayachen"],
                MOCK_USERS["marcusvance"],
                MOCK_USERS["ghost-contractor"],
            ]
            self._send_json(200, members)
            return

        # 4. GET /orgs/{org}/outside_collaborators
        if path.startswith("/orgs/") and path.endswith("/outside_collaborators"):
            outside = [
                MOCK_USERS["erostova"],
                MOCK_USERS["intern-dev"],
            ]
            self._send_json(200, outside)
            return

        # 5. GET /orgs/{org}/teams
        if path.startswith("/orgs/") and path.endswith("/teams"):
            teams = [
                {"id": 301, "slug": "platform", "name": "Platform Team"},
                {"id": 302, "slug": "infrastructure", "name": "Infrastructure Team"},
            ]
            self._send_json(200, teams)
            return

        # 6. GET /orgs/{org}/teams/{slug}/members
        if "/teams/" in path and path.endswith("/members"):
            self._send_json(200, [MOCK_USERS["alexmorgan"], MOCK_USERS["mayachen"]])
            return

        # 7. GET /orgs/{org}/repos
        if path.startswith("/orgs/") and path.endswith("/repos"):
            self._send_json(200, MOCK_REPOS)
            return

        # 8. GET /repos/{org}/{repo}/collaborators
        if path.startswith("/repos/") and path.endswith("/collaborators"):
            parts = path.split("/")
            repo_name = parts[3]
            collabs = MOCK_REPO_COLLABORATORS.get(repo_name, [])
            self._send_json(200, collabs)
            return

        # 9. GET /repos/{org}/{repo}/commits
        if path.startswith("/repos/") and path.endswith("/commits"):
            parts = path.split("/")
            repo_name = parts[3]
            author = query.get("author", [None])[0]
            commits = MOCK_COMMITS.get((repo_name, author), [])
            self._send_json(200, commits)
            return

        # 10. GET /users/{username}
        if path.startswith("/users/"):
            username = path.split("/")[2]
            user = MOCK_USERS.get(username, {"login": username, "email": None})
            self._send_json(200, user)
            return

        # Fallback 404
        self._send_json(404, {"message": "Not Found", "documentation_url": "https://docs.github.com"})

    def log_message(self, format, *args):
        logger.debug("%s - - [%s] %s\n", self.address_string(), self.log_date_time_string(), format % args)


def run_server(port: int = 8109):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, MockGitHubHandler)
    logger.info("Fake GitHub API server running on http://127.0.0.1:%d", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping Fake GitHub API server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock GitHub API Server")
    parser.add_argument("--port", type=int, default=8109, help="Port to listen on (default 8109)")
    args = parser.parse_args()
    run_server(args.port)
