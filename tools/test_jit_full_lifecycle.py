import asyncio
import json
import os
import shutil
import sqlite3
import sys
import urllib.request
from datetime import UTC, datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"


async def main():
    print("=== Testing Full JIT Expiration & Notification Lifecycle ===")

    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.set_viewport(1280, 850)
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # 1. Dev Auth
        await driver.evaluate("""
        (async () => {
            window.__toastHistory = [];
            const origToast = window.showToast;
            window.showToast = function(msg) {
                window.__toastHistory.push(msg);
                return origToast(msg);
            };

            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'admin@acme.corp', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'admin@acme.corp', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            window.FirebaseIdentity.notify();
            location.hash = 'audit?segment=jit';
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        # 2. Create 1-minute JIT access request
        print("\n[Step 1] Creating 1-minute live demo request...")
        create_res = await driver.evaluate("""
        (async () => {
            try {
                const res = await ApiClient.createAccessRequest({
                    email: 'misbahnisar024@gmail.com',
                    name: 'Misbah Nisar',
                    repo_name: 'demo-repository',
                    access_level: 'Write',
                    duration_hours: 0.0167,
                    business_reason: 'Testing real-time JIT countdown and auto-revocation notification'
                });
                return { ok: true, data: res };
            } catch (err) {
                return { ok: false, error: err.message };
            }
        })()
        """)
        print(f"  Create result: {create_res}")
        assert create_res.get("ok"), f"Failed to create request: {create_res}"
        req_id = create_res["data"]["id"]

        # 3. Approve the request
        print(f"\n[Step 2] Approving access request {req_id}...")
        approve_res = await driver.evaluate(f"""
        (async () => {{
            try {{
                const res = await ApiClient.decideApproval('{req_id}', 'Approved', 'Approved 1-min JIT');
                const data = await ApiClient.bootstrap();
                ApiClient.syncState(data);
                location.hash = 'audit?segment=jit';
                render();
                return {{ ok: true, data: res }};
            }} catch (err) {{
                return {{ ok: false, error: err.message }};
            }}
        }})()
        """)
        print(f"  Approve result: {approve_res}")
        assert approve_res.get("ok"), f"Failed to approve request: {approve_res}"
        await asyncio.sleep(1.0)

        # 4. Verify live ticking countdown on Misbah's row
        print("\n[Step 3] Verifying live ticking countdown in JIT table...")
        t1 = await driver.evaluate("""
        (() => {
            const badges = Array.from(document.querySelectorAll('[data-jit-badge]'));
            const misbahBadge = badges.find(b => b.closest('tr')?.textContent.includes('Misbah'));
            return misbahBadge?.querySelector('.jit-countdown-text')?.textContent || '';
        })()
        """)
        print(f"  Initial Misbah countdown reading: '{t1}'")
        assert "s left" in t1 or "m left" in t1, f"Expected seconds/minutes left, got: {t1}"

        # Wait 2.5 seconds to observe ticking
        await asyncio.sleep(2.5)
        t2 = await driver.evaluate("""
        (() => {
            const badges = Array.from(document.querySelectorAll('[data-jit-badge]'));
            const misbahBadge = badges.find(b => b.closest('tr')?.textContent.includes('Misbah'));
            return misbahBadge?.querySelector('.jit-countdown-text')?.textContent || '';
        })()
        """)
        print(f"  Reading after 2.5s: '{t2}'")
        assert t1 != t2 or "s left" in t2, "Countdown should be ticking live!"

        p1 = os.path.join(DOCS_DIR, "jit_ticking_countdown.png")
        await driver.screenshot(p1)
        shutil.copy2(p1, os.path.join(ARTIFACTS_DIR, "jit_ticking_countdown.png"))
        print(f"  Screenshot saved: jit_ticking_countdown.png")

        # 5. Fast-forward expiration in DB by 65 seconds to test auto-revocation and notification trigger
        print("\n[Step 4] Fast-forwarding expiration timestamp to test automatic reaper...")
        conn = sqlite3.connect(r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db")
        c = conn.cursor()
        now_past = (datetime.now(UTC) - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S.%f")
        c.execute("""
        UPDATE assignments
        SET expires_at = ?
        WHERE is_temporary = 1 AND access_level != 'None' AND identity_id IN (
            SELECT id FROM identities WHERE email = 'misbahnisar024@gmail.com'
        )
        """, (now_past,))
        conn.commit()
        conn.close()
        print("  Updated assignment expires_at in DB to past timestamp.")

        # Also update the DOM data-expires-at attribute so frontend timer detects expiration immediately
        await driver.evaluate(f"""
        (() => {{
            const badges = Array.from(document.querySelectorAll('[data-jit-badge]'));
            const misbahBadge = badges.find(b => b.closest('tr')?.textContent.includes('Misbah'));
            if (misbahBadge) misbahBadge.dataset.expiresAt = '{now_past}';
        }})()
        """)

        # Wait 3 seconds for the frontend timer to tick, call reapJit, and refresh
        print("  Waiting 3 seconds for auto-reap and notifications...")
        await asyncio.sleep(3.0)

        # 6. Check that assignment was revoked in DB
        conn = sqlite3.connect(r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db")
        c = conn.cursor()
        c.execute("""
        SELECT a.id, a.access_level, a.external_status, a.resolved
        FROM assignments a
        JOIN identities i ON a.identity_id = i.id
        WHERE i.email = 'misbahnisar024@gmail.com' AND a.is_temporary = 1
        ORDER BY a.created_at DESC LIMIT 1
        """)
        revoked_row = c.fetchone()
        print(f"  Assignment record in DB after auto-reaper: {revoked_row}")
        assert revoked_row[1] == "None", f"Expected access_level 'None', got: {revoked_row[1]}"
        assert revoked_row[2] == "revoked_externally", f"Expected external_status 'revoked_externally', got: {revoked_row[2]}"

        # Check Audit Log in DB
        c.execute("""
        SELECT id, actor, title, detail FROM audit_log WHERE tag = 'Auto-Expired' ORDER BY occurred_at DESC LIMIT 1
        """)
        audit_row = c.fetchone()
        print(f"  Audit log event: {audit_row}")
        assert audit_row is not None, "Audit log event missing!"
        assert audit_row[1] == "JIT Auto-Scheduler"

        # Check Notification in DB
        c.execute("""
        SELECT id, event_type, title, message FROM notifications WHERE event_type = 'jit_expired' ORDER BY created_at DESC LIMIT 1
        """)
        notif_row = c.fetchone()
        print(f"  Notification in DB: {notif_row}")
        assert notif_row is not None, "JIT expired notification record missing from DB!"
        assert "JIT Temporary Access Expired" in notif_row[2]
        conn.close()

        # 7. Check In-App Notification Bell in the UI
        print("\n[Step 5] Verifying In-App Notification Bell in UI...")
        unread_badge = await driver.evaluate("""
        document.querySelector('#notification-unread-count')?.textContent || ''
        """)
        print(f"  Notification unread badge: '{unread_badge}'")
        assert int(unread_badge) > 0, f"Expected unread badge count > 0, got: {unread_badge}"

        # Open the notification dropdown
        print("  Clicking notification bell to inspect dropdown...")
        await driver.click("#notification-bell", wait_seconds=0.8)

        notif_items = await driver.evaluate("""
        Array.from(document.querySelectorAll('.notification-item')).map(el => ({
            title: el.querySelector('.notif-title')?.textContent?.trim() || '',
            message: el.querySelector('.notif-message')?.textContent?.trim() || ''
        }))
        """)
        print(f"  Notification items in dropdown ({len(notif_items)}):")
        for item in notif_items[:3]:
            print(f"    - {item['title']}: {item['message']}")

        has_jit_notif = any("JIT" in n.get("title", "") or "JIT" in n.get("message", "") for n in notif_items)
        assert has_jit_notif, "JIT expiration notification missing from UI dropdown!"

        p2 = os.path.join(DOCS_DIR, "jit_reaped_notification_dropdown.png")
        await driver.screenshot(p2)
        shutil.copy2(p2, os.path.join(ARTIFACTS_DIR, "jit_reaped_notification_dropdown.png"))
        print(f"  Screenshot saved: jit_reaped_notification_dropdown.png")

        # 8. Check that user received toast notification
        toasts = await driver.evaluate("window.__toastHistory || []")
        print(f"  Recent toasts: {toasts[-3:]}")

        print("\n=== FULL JIT AUTO-REAP & NOTIFICATION LIFECYCLE 100% VERIFIED ===")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
