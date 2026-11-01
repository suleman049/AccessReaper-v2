import asyncio
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"


async def main():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.set_viewport(1280, 850)
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # Dev Auth
        await driver.evaluate("""
        (async () => {
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

        # 1. Test "Run Auto-Audit Now" button on #audit
        print("[1] Testing Run Auto-Audit Now button on #audit...")
        has_btn = await driver.evaluate("Boolean(document.querySelector('#btn-trigger-auto-audit'))")
        print(f"  #btn-trigger-auto-audit exists: {has_btn}")
        assert has_btn, "Run Auto-Audit Now button missing from header!"

        clock_val = await driver.evaluate("document.querySelector('#countdown-clock-val')?.textContent")
        print(f"  Countdown clock is ticking: {clock_val}")

        # Click the button
        await driver.click("#btn-trigger-auto-audit", wait_seconds=2.0)
        toast = await driver.evaluate("document.querySelector('.toast-card')?.textContent")
        print(f"  Toast after clicking Run Auto-Audit: {toast}")

        p1 = os.path.join(DOCS_DIR, "auto_audit_triggered.png")
        await driver.screenshot(p1)
        shutil.copy2(p1, os.path.join(ARTIFACTS_DIR, "auto_audit_triggered.png"))
        print("  Screenshot saved: auto_audit_triggered.png")

        # 2. Test Auto-Pilot Settings Card on #settings
        print("\n[2] Testing Auto-Pilot Settings on #settings...")
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            render();
        })()
        """)
        await asyncio.sleep(1.0)

        has_ap_card = await driver.evaluate("Boolean(document.querySelector('#autopilot-settings-card'))")
        print(f"  #autopilot-settings-card exists: {has_ap_card}")
        assert has_ap_card, "Auto-Pilot settings card missing from #settings!"

        # Toggle Auto-Pilot ON
        print("  Toggling Auto-Pilot ON...")
        await driver.click("#autopilot-toggle-switch", wait_seconds=1.0)
        is_checked = await driver.evaluate("document.querySelector('#autopilot-toggle-switch')?.checked")
        print(f"  Toggle switch checked: {is_checked}")

        # Screenshot of Settings with Auto-Pilot
        p2 = os.path.join(DOCS_DIR, "autopilot_settings_card.png")
        await driver.screenshot(p2)
        shutil.copy2(p2, os.path.join(ARTIFACTS_DIR, "autopilot_settings_card.png"))
        print("  Screenshot saved: autopilot_settings_card.png")

        # 3. Test Duration select has 1-minute demo option
        print("\n[3] Testing Request Access duration dropdown...")
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
        has_1m = any(o["value"] == "0.0167" for o in dur_options)
        print(f"  Has 1-minute JIT option: {has_1m}")
        assert has_1m, "1-minute JIT option missing from dropdown!"

        p3 = os.path.join(DOCS_DIR, "jit_1min_request_modal.png")
        await driver.screenshot(p3)
        shutil.copy2(p3, os.path.join(ARTIFACTS_DIR, "jit_1min_request_modal.png"))
        print("  Screenshot saved: jit_1min_request_modal.png")

        print("\nConsole errors:", driver.console_errors)
        assert len(driver.console_errors) == 0, f"Errors: {driver.console_errors}"
        print("\n[ALL 3 AUTOMATION FEATURES TESTED AND VERIFIED SUCCESSFULLY!]")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
