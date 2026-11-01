"""
Automated browser capture of real live PayHive GitHub organization data in AccessReaper v2.
"""

import asyncio
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

SCREENSHOT_DIR = r"D:\AccessReaper-v2\docs\verification"


async def ensure_authenticated(driver):
    script = """
    (() => {
        window.FirebaseIdentity.phase = 'authorized';
        window.FirebaseIdentity.user = {
            uid: 'dev-admin-uid',
            email: 'jordan.davis@acme.io',
            displayName: 'Jordan Davis',
            getIdToken: async () => 'dev-token'
        };
        window.FirebaseIdentity.profile = {
            uid: 'dev-admin-uid',
            email: 'jordan.davis@acme.io',
            name: 'Jordan Davis',
            role: 'admin',
            status: 'active',
            organizationId: 'acme'
        };
        window.FirebaseIdentity.notify();
        if (window.ApiClient && !window.ApiClient.loaded) {
            window.ApiClient.loadAndRender();
        }
        return true;
    })()
    """
    await driver.evaluate(script)
    await asyncio.sleep(0.8)


async def navigate_to(driver, page_hash, wait_seconds=1.2):
    await driver.evaluate(f"""
    (() => {{
        location.hash = '{page_hash}';
        if (typeof render === 'function') render();
    }})()
    """)
    await asyncio.sleep(wait_seconds)


async def run_payhive_capture():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    print("\n--- Capturing Real PayHive GitHub Data in AccessReaper v2 ---")
    try:
        await driver.navigate("http://127.0.0.1:8100/")
        await asyncio.sleep(1.2)
        await ensure_authenticated(driver)

        # 1. Overview dashboard with live data
        print("[1/4] Capturing Live Overview dashboard for payhive-eng...")
        await navigate_to(driver, "#overview", wait_seconds=1.5)
        p1 = os.path.join(SCREENSHOT_DIR, "PAYHIVE1-overview.png")
        await driver.screenshot(p1)
        print(f"  -> Captured: {p1}")

        # 2. Access audit table
        print("[2/4] Capturing Live Access audit findings...")
        await navigate_to(driver, "#audit", wait_seconds=1.5)
        p2 = os.path.join(SCREENSHOT_DIR, "PAYHIVE2-audit-findings.png")
        await driver.screenshot(p2)
        print(f"  -> Captured: {p2}")

        # 3. Settings page with Connected services and Unmatched accounts
        print("[3/4] Capturing Settings with payhive-eng connected...")
        await navigate_to(driver, "#settings", wait_seconds=1.5)
        p3 = os.path.join(SCREENSHOT_DIR, "PAYHIVE3-settings-connected.png")
        await driver.screenshot(p3)
        print(f"  -> Captured: {p3}")

        # 4. Run audit dialog
        print("[4/4] Opening Audit Report dialog for payhive-eng...")
        await driver.evaluate("""
        (() => {
            if (window.ReportDialog && window.auditRuns && window.auditRuns.length > 0) {
                window.ReportDialog.open(window.auditRuns[window.auditRuns.length - 1].id);
            }
        })()
        """)
        await asyncio.sleep(1.2)
        p4 = os.path.join(SCREENSHOT_DIR, "PAYHIVE4-audit-report.png")
        await driver.screenshot(p4)
        print(f"  -> Captured: {p4}")

        print(f"\nAll PayHive captures complete! Total console errors: {len(driver.console_errors)}")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_payhive_capture())
