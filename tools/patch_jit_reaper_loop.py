import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

automation_path = r"D:\AccessReaper-v2\backend\app\engine\automation.py"
with open(automation_path, "r", encoding="utf-8") as f:
    text = f.read()

target1 = """        a.access_level = "None"
        a.resolved = True
        a.current_risk = "Low"
        a.reason = "Temporary JIT access expired automatically"
"""

replacement1 = """        a.access_level = "None"
        a.is_temporary = False
        a.expires_at = None
        a.resolved = True
        a.current_risk = "Low"
        a.reason = "Temporary JIT access expired automatically"
"""

if target1 in text:
    text = text.replace(target1, replacement1, 1)
    with open(automation_path, "w", encoding="utf-8") as f:
        f.write(text)
    print("✓ Successfully patched automation.py: JIT lease reset is_temporary=False and expires_at=None on expiration.")
else:
    # Try CRLF
    target1_crlf = target1.replace("\n", "\r\n")
    replacement1_crlf = replacement1.replace("\n", "\r\n")
    if target1_crlf in text:
        text = text.replace(target1_crlf, replacement1_crlf, 1)
        with open(automation_path, "w", encoding="utf-8") as f:
            f.write(text)
        print("✓ Successfully patched automation.py (CRLF): JIT lease reset is_temporary=False and expires_at=None.")
    else:
        print("✗ Target1 not found in automation.py")

# Now patch sync.py
sync_path = r"D:\AccessReaper-v2\backend\app\integrations\github\sync.py"
with open(sync_path, "r", encoding="utf-8") as f:
    stext = f.read()

target2 = """                        existing.external_status = "active"
                        sync_run.assignments_updated += 1"""

replacement2 = """                        existing.external_status = "active"
                        # If an old temporary lease already reached its expiration timestamp, clear is_temporary
                        if getattr(existing, "is_temporary", False) and getattr(existing, "expires_at", None):
                            if existing.expires_at <= now:
                                existing.is_temporary = False
                                existing.expires_at = None
                        sync_run.assignments_updated += 1"""

if target2 in stext:
    stext = stext.replace(target2, replacement2, 1)
    with open(sync_path, "w", encoding="utf-8") as f:
        f.write(stext)
    print("✓ Successfully patched sync.py: Prevents resurrection of expired JIT leases during sync.")
else:
    target2_crlf = target2.replace("\n", "\r\n")
    replacement2_crlf = replacement2.replace("\n", "\r\n")
    if target2_crlf in stext:
        stext = stext.replace(target2_crlf, replacement2_crlf, 1)
        with open(sync_path, "w", encoding="utf-8") as f:
            f.write(stext)
        print("✓ Successfully patched sync.py (CRLF): Prevents resurrection of expired JIT leases.")
    else:
        print("✗ Target2 not found in sync.py")
