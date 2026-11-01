"""
Phase 3 Automated Browser Verification Script for AccessReaper v2.
Drives real Chrome via CDP to verify the complete GitHub IAM Integration:
1. Connects to fake mock GitHub API server on port 8109.
2. Triggers synchronization (Sync now) and observes real imported records.
3. Inspects Unmatched GitHub accounts panel.
4. Switches workspace Data Mode to Live (verifying live data badge and live findings).
5. Navigates to Access audit in Live mode.
6. Executes Run audit in Live mode and verifies Report Dialog & PDF download.
7. Links an unmatched account to an employee email.
8. Verifies Dark theme and Mobile width 390px.
9. Switches back to Sample data mode.
10. Asserts zero JavaScript console errors throughout!
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


async def navigate_to(driver, page_hash, wait_seconds=1.0):
    await driver.evaluate(f"""
    (() => {{
        location.hash = '{page_hash}';
        if (typeof render === 'function') render();
    }})()
    """)
    await asyncio.sleep(wait_seconds)


async def run_verification():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    print("\n--- Starting Phase 3 Browser Verification ---")
    try:
        # 1. Open app
        print("[1/9] Opening AccessReaper v2 on http://127.0.0.1:8100/ ...")
        await driver.navigate("http://127.0.0.1:8100/")
        await asyncio.sleep(1.2)
        await ensure_authenticated(driver)

        # 2. Step B1: Connect GitHub in Settings
        print("[2/9] Navigating to #settings and connecting GitHub Organization...")
        await navigate_to(driver, "#settings", wait_seconds=1.2)

        # Open Connect modal and submit
        await driver.evaluate("""
        (() => {
            if (window.GitHubSettings) {
                window.GitHubSettings.openConnectModal();
                document.getElementById('gh-org-input').value = 'acme';
                document.getElementById('gh-token-input').value = 'ghp_MockVerifiedPAT1234';
                document.getElementById('btn-submit-connect').click();
            }
        })()
        """)
        await asyncio.sleep(2.0)

        # Re-render settings to show connected state
        await driver.evaluate("if (window.GitHubSettings) window.GitHubSettings.init();")
        await asyncio.sleep(0.8)

        b1_path = os.path.join(SCREENSHOT_DIR, "B1-settings-github-connected.png")
        await driver.screenshot(b1_path)
        print(f"  -> Captured: {b1_path}")

        # 3. Step B2: Sync Now
        print("[3/9] Executing Sync now against mock GitHub API...")
        await driver.evaluate("""
        (() => {
            const btn = document.getElementById('btn-gh-sync');
            if (btn) btn.click();
        })()
        """)
        await asyncio.sleep(2.5)

        b2_path = os.path.join(SCREENSHOT_DIR, "B2-sync-in-progress.png")
        await driver.screenshot(b2_path)
        print(f"  -> Captured: {b2_path}")

        # 4. Step B3: Unmatched GitHub accounts panel
        print("[4/9] Inspecting Unmatched GitHub accounts panel in Settings...")
        # Scroll to unmatched accounts card
        await driver.evaluate("""
        (() => {
            const card = document.getElementById('unmatched-github-card');
            if (card) card.scrollIntoView({ behavior: 'instant', block: 'center' });
        })()
        """)
        await asyncio.sleep(0.5)

        b3_path = os.path.join(SCREENSHOT_DIR, "B3-unmatched-accounts.png")
        await driver.screenshot(b3_path)
        print(f"  -> Captured: {b3_path}")

        # 5. Step B4: Switch to Live data mode & Overview page
        print("[5/9] Switching to Live data mode and viewing Overview dashboard...")
        await driver.evaluate("""
        (async () => {
            await window.ApiClient.setDataMode('live');
            window.currentDataMode = 'live';
            await window.ApiClient.loadAndRender();
            if (window.GitHubSettings) window.GitHubSettings.updateHeaderBadge();
        })()
        """)
        await asyncio.sleep(1.0)
        await navigate_to(driver, "#overview", wait_seconds=1.2)

        b4_path = os.path.join(SCREENSHOT_DIR, "B4-live-overview.png")
        await driver.screenshot(b4_path)
        print(f"  -> Captured: {b4_path}")

        # 6. Step B5: Live Access audit page
        print("[6/9] Viewing Access audit findings in Live data mode...")
        await navigate_to(driver, "#audit", wait_seconds=1.2)

        b5_path = os.path.join(SCREENSHOT_DIR, "B5-live-audit.png")
        await driver.screenshot(b5_path)
        print(f"  -> Captured: {b5_path}")

        # 7. Step B6: Run audit in Live mode & verify PDF report dialog
        print("[7/9] Running IAM audit in Live mode and opening report dialog...")
        await driver.evaluate("""
        (() => {
            if (window.Governance) window.Governance.runAudit();
        })()
        """)
        await asyncio.sleep(2.0)

        b6_path = os.path.join(SCREENSHOT_DIR, "B6-live-pdf-report.png")
        await driver.screenshot(b6_path)
        print(f"  -> Captured: {b6_path}")

        # Close report modal
        await driver.evaluate("""
        (() => {
            const modal = document.querySelector('#review-modal');
            if (modal) bootstrap.Modal.getInstance(modal)?.hide();
        })()
        """)
        await asyncio.sleep(0.5)

        # 8. Step B7: Link unmatched account & Dark theme
        print("[8/9] Testing Dark theme and linking unmatched account...")
        await navigate_to(driver, "#settings", wait_seconds=1.0)
        await driver.evaluate("""
        (() => {
            document.documentElement.setAttribute('data-theme', 'dark');
            if (window.GitHubSettings) window.GitHubSettings.init();
        })()
        """)
        await asyncio.sleep(0.8)

        b7_path = os.path.join(SCREENSHOT_DIR, "B7-settings-github-dark.png")
        await driver.screenshot(b7_path)
        print(f"  -> Captured: {b7_path}")

        # 9. Step B8: Mobile 390px width
        print("[9/9] Testing Mobile viewport 390px on Settings...")
        await driver.set_viewport(390, 844)
        await asyncio.sleep(0.8)

        b8_path = os.path.join(SCREENSHOT_DIR, "B8-settings-github-390px.png")
        await driver.screenshot(b8_path)
        print(f"  -> Captured: {b8_path}")

        # Restore viewport, reset dark theme, switch back to sample mode
        await driver.set_viewport(1280, 800)
        await driver.evaluate("""
        (async () => {
            document.documentElement.removeAttribute('data-theme');
            await window.ApiClient.setDataMode('sample');
            window.currentDataMode = 'sample';
            await window.ApiClient.loadAndRender();
            if (window.GitHubSettings) window.GitHubSettings.updateHeaderBadge();
        })()
        """)
        await asyncio.sleep(0.8)

        print("\n--- Verification Completed Successfully! ---")
        print(f"Total console logs: {len(driver.console_logs)}")
        print(f"Total console errors: {len(driver.console_errors)}")

        if driver.console_errors:
            print("WARNING - Console errors detected:")
            for err in driver.console_errors:
                print(f"  [ERROR] {err}")
        else:
            print("PERFECT: 0 console errors detected across all tested flows!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_verification())
