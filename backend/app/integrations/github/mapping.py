"""
GitHub to AccessReaper permission level mapping module.

Mapping Policy (Strictly Enforced):
- 'admin'    -> 'Admin'
- 'maintain' -> 'Write'  (Strict rule: maintain -> Write, NEVER Admin)
- 'push'     -> 'Write'
- 'triage'   -> 'Read'
- 'pull'     -> 'Read'
"""

from typing import Any


def map_github_permission(
    role_name: str | None = None,
    permissions: dict[str, Any] | None = None,
) -> str:
    """
    Translates GitHub collaborator permission metadata into AccessReaper access level.

    Precedence:
    1. If `role_name` is explicitly provided, map standard GitHub roles:
       - 'admin' -> 'Admin'
       - 'maintain' -> 'Write'
       - 'push' / 'write' -> 'Write'
       - 'triage' -> 'Read'
       - 'pull' / 'read' -> 'Read'
    2. If `permissions` dictionary is provided (e.g., {"admin": True, "maintain": True, ...}):
       - If admin: 'Admin'
       - Else if maintain: 'Write'
       - Else if push: 'Write'
       - Else if triage: 'Read'
       - Else if pull: 'Read'
    3. Fallback: 'Read'
    """
    if role_name:
        rn = role_name.strip().lower()
        if rn == "admin":
            return "Admin"
        if rn in ("maintain", "push", "write"):
            return "Write"
        if rn in ("triage", "pull", "read"):
            return "Read"

    if permissions and isinstance(permissions, dict):
        if permissions.get("admin") is True:
            return "Admin"
        if permissions.get("maintain") is True:
            return "Write"
        if permissions.get("push") is True:
            return "Write"
        if permissions.get("triage") is True:
            return "Read"
        if permissions.get("pull") is True:
            return "Read"

    return "Read"
