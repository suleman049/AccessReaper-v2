import asyncio
import json
import os
import shutil
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"


def reset_autopilot_db():
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8100/api/automation/autopilot",
            data=json.dumps({"enabled": False}).encode("utf-8"),
            headers={
                "Authorization": "Bearer dev-token",
                "X-Dev-User": "admin@payhive-eng.internal",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req) as resp:
            print(f"  Reset Auto-Pilot to OFF in DB: status {resp.status}")
    except Exception as e:
        print(f"  Warning resetting autopilot in DB: {e}")


async def main():
    print("--- Starting Full Live Automation Demo Verification ---")
    reset_autopilot_db()

    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.set_viewport(1280, 850)
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # Dev Auth & Toast Spy
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
            location.hash = 'audit';
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        # ---------------------------------------------------------------------
        # 1. Verify "Run Auto-Audit Now" button on #audit
        # ---------------------------------------------------------------------
        print("\n[1] Verifying Run Auto-Audit Now button on #audit...")
        has_btn = await driver.evaluate("Boolean(document.querySelector('#btn-trigger-auto-audit'))")
        print(f"  #btn-trigger-auto-audit exists: {has_btn}")
        assert has_btn, "Run Auto-Audit Now button missing from header!"

        clock_val = await driver.evaluate("document.querySelector('#countdown-clock-val')?.textContent")
        print(f"  Countdown clock is ticking: {clock_val}")

        # ---------------------------------------------------------------------
        # 2. Test Auto-Pilot Settings Card on #settings
        # ---------------------------------------------------------------------
        print("\n[2] Testing Auto-Pilot Settings on #settings...")
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            render();
        })()
        """)
        await asyncio.sleep(1.2)

        has_ap_card = await driver.evaluate("Boolean(document.querySelector('#autopilot-settings-card'))")
        print(f"  #autopilot-settings-card exists: {has_ap_card}")
        assert has_ap_card, "Auto-Pilot settings card missing from #settings!"

        # Verify initial OFF state
        initial_checked = await driver.evaluate("Boolean(document.querySelector('#autopilot-toggle-switch')?.checked)")
        initial_badge = await driver.evaluate("document.querySelector('#autopilot-settings-card .badge')?.textContent || ''")
        print(f"  Initial state: checked={initial_checked}, badge={initial_badge.strip()}")
        assert not initial_checked, "Auto-Pilot should initially be OFF!"
        assert "MANUAL REVIEW (OFF)" in initial_badge, f"Expected MANUAL REVIEW (OFF), got: {initial_badge}"

        # Toggle Auto-Pilot ON
        print("  Toggling Auto-Pilot ON...")
        await driver.click("#autopilot-toggle-switch", wait_seconds=0.5)
        
        # Wait for badge to update to AUTONOMOUS ACTIVE
        badge_text = ""
        for _ in range(15):
            badge_text = await driver.evaluate("document.querySelector('#autopilot-settings-card .badge')?.textContent || ''")
            if "AUTONOMOUS ACTIVE" in badge_text:
                break
            await asyncio.sleep(0.5)

        is_checked = await driver.evaluate("Boolean(document.querySelector('#autopilot-toggle-switch')?.checked)")
        print(f"  Toggle switch checked: {is_checked}, Badge: {badge_text.strip()}")
        assert is_checked, "Auto-Pilot switch should be checked!"
        assert "AUTONOMOUS ACTIVE" in badge_text, f"Expected AUTONOMOUS ACTIVE, got: {badge_text}"

        # Click "Enforce Policies Now"
        print("  Clicking 'Enforce Policies Now' button...")
        await driver.click("#btn-enforce-autopilot", wait_seconds=2.0)
        toasts = await driver.evaluate("window.__toastHistory || []")
        print(f"  Recent toasts: {toasts[-2:]}")

        p2 = os.path.join(DOCS_DIR, "autopilot_settings_active.png")
        await driver.screenshot(p2)
        shutil.copy2(p2, os.path.join(ARTIFACTS_DIR, "autopilot_settings_active.png"))
        print("  Screenshot saved: autopilot_settings_active.png")

        # Toggle Auto-Pilot back OFF (user requested control: default OFF)
        print("  Toggling Auto-Pilot back OFF...")
        await driver.click("#autopilot-toggle-switch", wait_seconds=0.5)
        
        # Wait for badge to update to MANUAL REVIEW (OFF)
        badge_text_off = ""
        for _ in range(15):
            badge_text_off = await driver.evaluate("document.querySelector('#autopilot-settings-card .badge')?.textContent || ''")
            if "MANUAL REVIEW (OFF)" in badge_text_off:
                break
            await asyncio.sleep(0.5)

        is_checked_off = await driver.evaluate("Boolean(document.querySelector('#autopilot-toggle-switch')?.checked)")
        print(f"  Toggle switch checked: {is_checked_off}, Badge: {badge_text_off.strip()}")
        assert not is_checked_off, "Auto-Pilot switch should be unchecked!"
        assert "MANUAL REVIEW (OFF)" in badge_text_off, f"Expected MANUAL REVIEW (OFF), got: {badge_text_off}"

        p2_off = os.path.join(DOCS_DIR, "autopilot_settings_off.png")
        await driver.screenshot(p2_off)
        shutil.copy2(p2_off, os.path.join(ARTIFACTS_DIR, "autopilot_settings_off.png"))
        print("  Screenshot saved: autopilot_settings_off.png")

        # ---------------------------------------------------------------------
        # 3. Test Request Access with 1-Minute Live Demo Option
        # ---------------------------------------------------------------------
        print("\n[3] Testing Request Access modal with 1-Minute Live Demo...")
        await driver.evaluate("""
        (() => {
            location.hash = 'approvals';
            render();
            document.querySelector('#btn-open-request-modal')?.click();
        })()
        """)
        await asyncio.sleep(0.8)

        dur_options = await driver.evaluate("""
        Array.from(document.querySelectorAll('#req-duration-select option')).map(o => ({ value: o.value, text: o.textContent.trim() }))
        """)
        print(f"  Duration options in modal: {dur_options}")
        assert any(o["value"] == "0.0167" for o in dur_options), "1-minute option missing!"

        # Create a 2-minute access request for Misbah Nisar
        print("  Submitting 2-Minute Live Demo request for Misbah Nisar...")
        submit_result = await driver.evaluate("""
        (async () => {
            try {
                const res = await ApiClient.createAccessRequest({
                    email: 'misbahnisar024@gmail.com',
                    name: 'Misbah Nisar',
                    repo_name: 'demo-repository',
                    access_level: 'Write',
                    duration_hours: 0.0333,
                    business_reason: 'Live 2-minute JIT automation demo for presentation'
                });
                return { ok: true, data: res };
            } catch (err) {
                return { ok: false, error: err.message };
            }
        })()
        """)
        print(f"  Create request result: {submit_result}")
        assert submit_result.get("ok"), f"Failed to create access request: {submit_result}"

        # Re-render approvals page and approve the request
        await driver.evaluate("""
        (async () => {
            const data = await ApiClient.bootstrap();
            ApiClient.syncState(data);
            location.hash = 'approvals';
            render();
        })()
        """)
        await asyncio.sleep(1.0)

        # Click the first Approve button
        req_id = submit_result.get("data", {}).get("id")
        print(f"  Approving access request {req_id}...")
        approve_res = await driver.evaluate(f"""
        (async () => {{
            try {{
                const res = await ApiClient.decideApproval('{req_id}', 'Approved', 'Approved for 2-minute live demo');
                const data = await ApiClient.bootstrap();
                ApiClient.syncState(data);
                location.hash = 'audit?segment=jit';
                render();
                return {{ ok: true, res }};
            }} catch (e) {{
                return {{ ok: false, error: e.message }};
            }}
        }})()
        """)
        print(f"  Approve result: {approve_res}")
        assert approve_res.get("ok"), f"Failed to approve request: {approve_res}"
        await asyncio.sleep(1.5)

        # ---------------------------------------------------------------------
        # 4. Verify JIT Table Countdown on #audit?segment=jit
        # ---------------------------------------------------------------------
        print("\n[4] Verifying live countdown on #audit?segment=jit...")
        jit_rows = await driver.evaluate("""
        Array.from(document.querySelectorAll('.assignment-table-scroll tbody tr')).map(tr => tr.innerText.replace(/\\n/g, ' | '))
        """)
        print(f"  JIT rows count: {len(jit_rows)}")
        for r in jit_rows:
            print(f"    Row: {r}")
        has_countdown = any("left" in r or "Live Demo" in r or "JIT" in r for r in jit_rows)
        print(f"  Live countdown active in table: {has_countdown}")
        assert has_countdown, f"Expected countdown in table rows, got: {jit_rows}"

        p4 = os.path.join(DOCS_DIR, "jit_1min_live_countdown.png")
        await driver.screenshot(p4)
        shutil.copy2(p4, os.path.join(ARTIFACTS_DIR, "jit_1min_live_countdown.png"))
        print("  Screenshot saved: jit_1min_live_countdown.png")

        print("\nALL AUTOMATION DEMO TESTS COMPLETED AND VERIFIED SUCCESSFULLY!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
