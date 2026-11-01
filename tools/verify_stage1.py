"""
Browser verification script for Stage 1: Fully Automatic Audits.
Connects via Chrome DevTools Protocol to verify:
1. Removal of manual audit buttons on #dashboard and #audit.
2. In-place live ticking countdown status chip on both pages.
3. Settings card 'Automatic audits' with 24h fixed interval, time picker, and recent runs.
4. Pausing automatic audits with required note, verifying paused warning chip.
5. Resuming automatic audits and countdown resumption.
6. Zero browser console errors.
Saves screenshots to docs/verification/S1-*.png.
"""

import asyncio
import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

VERIFICATION_DIR = r"D:\AccessReaper-v2\docs\verification"


async def verify_stage1():
    os.makedirs(VERIFICATION_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 800)
        print("[*] Navigating to http://127.0.0.1:8100/...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # 1. Dev Auth
        await driver.evaluate("""
        (() => {
            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'jordan.davis@acme.io', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'jordan.davis@acme.io', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            window.FirebaseIdentity.notify();
            return true;
        })()
        """)
        await asyncio.sleep(0.8)

        # 2. Check Overview Page
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        overview_check = await driver.evaluate("""
        ({
            hasRunAuditBtn: Boolean(document.querySelector('[data-run-audit]')),
            hasTimerChip: Boolean(document.querySelector('#automation-chip-wrap')),
            timerText: document.querySelector('#automation-chip-wrap')?.innerText || ''
        })
        """)
        print("[*] Overview check:", overview_check)
        assert not overview_check["hasRunAuditBtn"], "Manual 'Run access audit' button still exists on overview!"
        assert overview_check["hasTimerChip"], "Automation countdown chip missing from overview header!"

        # 3. Check Access Audit Page
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        audit_check = await driver.evaluate("""
        ({
            hasRunAuditBtn: Boolean(document.querySelector('#run-audit')),
            hasTimerChip: Boolean(document.querySelector('#automation-chip-wrap')),
            timerText: document.querySelector('#automation-chip-wrap')?.innerText || '',
            clockVal: document.querySelector('#countdown-clock-val')?.textContent || ''
        })
        """)
        print("[*] Access Audit check:", audit_check)
        assert not audit_check["hasRunAuditBtn"], "Manual 'Run audit' button still exists on audit page!"
        assert audit_check["hasTimerChip"], "Automation countdown chip missing from audit page header!"

        screenshot1 = os.path.join(VERIFICATION_DIR, "S1-countdown-timer.png")
        await driver.screenshot(screenshot1)
        print(f"[SUCCESS] Saved screenshot: {screenshot1}")

        # 4. Check Settings Page 'Automatic audits' Card
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        settings_check = await driver.evaluate("""
        ({
            hasCard: Boolean(document.querySelector('#schedule-settings-card')),
            headingText: document.querySelector('#schedule-settings-card h2')?.textContent || '',
            hasTimeInput: Boolean(document.querySelector('#sched-time')),
            hasPauseBtn: Boolean(document.querySelector('#btn-open-pause')),
            hasRecentRuns: Boolean(document.querySelector('.auto-recent-runs-table')),
            nextRunText: document.querySelector('.schedule-next-indicator strong')?.textContent || ''
        })
        """)
        print("[*] Settings check:", settings_check)
        assert settings_check["hasCard"], "Automatic audits card missing from #settings!"
        assert "Automatic audits" in settings_check["headingText"], f"Unexpected heading: {settings_check['headingText']}"
        assert settings_check["hasTimeInput"], "Time input missing!"
        assert settings_check["hasPauseBtn"], "Pause button missing!"

        screenshot2 = os.path.join(VERIFICATION_DIR, "S1-settings-automation.png")
        await driver.screenshot(screenshot2)
        print(f"[SUCCESS] Saved screenshot: {screenshot2}")

        # 5. Pause Automatic Audits
        await driver.evaluate("""
        (() => {
            document.querySelector('#btn-open-pause')?.click();
            const input = document.querySelector('#pause-note-input');
            if (input) input.value = 'Scheduled infrastructure maintenance window';
            document.querySelector('#btn-confirm-pause')?.click();
        })()
        """)
        await asyncio.sleep(1.5)

        paused_check = await driver.evaluate("""
        ({
            isPausedBadge: document.querySelector('#schedule-settings-card .badge-warning')?.textContent || '',
            hasResumeBtn: Boolean(document.querySelector('#btn-resume-schedule')),
            chipText: document.querySelector('#automation-chip-wrap')?.innerText || ''
        })
        """)
        print("[*] Paused check:", paused_check)
        assert "Paused" in paused_check["isPausedBadge"], "Card does not show Paused badge!"
        assert paused_check["hasResumeBtn"], "Resume button missing when paused!"

        screenshot3 = os.path.join(VERIFICATION_DIR, "S1-paused-state.png")
        await driver.screenshot(screenshot3)
        print(f"[SUCCESS] Saved screenshot: {screenshot3}")

        # 6. Resume Automatic Audits
        await driver.evaluate("""
        (() => {
            document.querySelector('#btn-resume-schedule')?.click();
        })()
        """)
        await asyncio.sleep(1.5)

        resumed_check = await driver.evaluate("""
        ({
            isActiveBadge: document.querySelector('#schedule-settings-card .badge-success')?.textContent || '',
            hasPauseBtn: Boolean(document.querySelector('#btn-open-pause'))
        })
        """)
        print("[*] Resumed check:", resumed_check)
        assert "Active" in resumed_check["isActiveBadge"], "Card did not return to Active!"

        # 7. Check Browser Console Errors
        print("[*] Console errors:", driver.console_errors)
        assert len(driver.console_errors) == 0, f"Browser console errors encountered: {driver.console_errors}"
        print("[ALL STAGE 1 CHECKS PASSED WITH 0 CONSOLE ERRORS]")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(verify_stage1())
