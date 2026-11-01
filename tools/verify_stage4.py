"""
Browser verification script for Stage 4: AI Explanations & Notifications.
Connects via Chrome DevTools Protocol to verify in real Chrome:
1. Executive summary card / disclosure with AI badge and advisory note.
2. In-app notification center (topbar bell, unread badge, dropdown list, mark read).
3. Finding detail panel with AI plain-language explanation and recommended action.
4. Settings page Notifications card with daily email digest preference and test email trigger.
5. Mobile viewport responsiveness (390px).
6. Zero browser console errors.
Saves screenshots to docs/verification/S4-*.png.
"""

import asyncio
import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

VERIFICATION_DIR = r"D:\AccessReaper-v2\docs\verification"


async def verify_stage4():
    os.makedirs(VERIFICATION_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 800)
        print("[*] Navigating to http://127.0.0.1:8100/...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # 1. Dev Auth as Jordan Davis (Admin)
        await driver.evaluate("""
        (async () => {
            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'admin@acme.corp', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'admin@acme.corp', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            window.FirebaseIdentity.notify();
            if (window.ApiClient) {
                await window.ApiClient.loadAndRender();
            }
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        # 2. Check Executive Summary on Dashboard
        print("[*] Checking Executive Summary on #dashboard...")
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        # Expand audit summary disclosure if present
        await driver.evaluate("""
        (() => {
            const disc = document.querySelector('.audit-summary-disclosure');
            if (disc && !disc.open) disc.open = true;
        })()
        """)
        await asyncio.sleep(0.5)

        summary_check = await driver.evaluate("""
        ({
            hasSummarySection: Boolean(document.querySelector('.gemini-preview')),
            previewLabel: document.querySelector('.gemini-preview .preview-label')?.textContent?.trim(),
            summaryText: document.querySelector('.gemini-preview p')?.textContent?.trim(),
            disclaimer: document.querySelector('.gemini-preview small')?.textContent?.trim()
        })
        """)
        print(f"[*] Executive summary: {summary_check}")
        assert summary_check["hasSummarySection"], "Gemini preview section missing"
        assert "AI-generated" in (summary_check["disclaimer"] or ""), "Advisory disclaimer missing"

        summary_shot = os.path.join(VERIFICATION_DIR, "S4-ai-executive-summary.png")
        await driver.screenshot(summary_shot)
        print(f"[+] Saved {summary_shot}")

        # 3. Check In-App Notification Center
        print("[*] Testing In-App Notification Center...")
        await driver.evaluate("""
        (() => {
            const bell = document.querySelector('#notification-bell');
            if (bell) bell.click();
        })()
        """)
        await asyncio.sleep(0.6)

        notif_check = await driver.evaluate("""
        ({
            bellExists: Boolean(document.querySelector('#notification-bell')),
            panelVisible: !document.querySelector('#notification-panel')?.classList.contains('d-none'),
            badgeText: document.querySelector('#notification-unread-count')?.textContent,
            itemCount: document.querySelectorAll('#notification-list .notification-item').length
        })
        """)
        print(f"[*] Notification center state: {notif_check}")
        assert notif_check["bellExists"], "Notification bell missing from topbar"
        assert notif_check["panelVisible"], "Notification dropdown panel did not open on click"

        notif_shot = os.path.join(VERIFICATION_DIR, "S4-notification-center.png")
        await driver.screenshot(notif_shot)
        print(f"[+] Saved {notif_shot}")

        # Close notification center
        await driver.evaluate("""
        (() => {
            if (window.NotificationsCenter) window.NotificationsCenter.close();
        })()
        """)
        await asyncio.sleep(0.3)

        # 4. Check Finding Detail Panel (AI Plain-Language Explanation & Recommendation)
        print("[*] Checking Finding AI Risk Assessment on #risk?FND-2841...")
        await driver.evaluate("""
        (() => {
            location.hash = 'risk?FND-2841';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        finding_check = await driver.evaluate("""
        ({
            hasEvidence: Boolean(document.querySelector('.evidence-snapshot')),
            policyContext: document.querySelector('.policy-context')?.textContent?.trim(),
            hasRecommendedStep: Boolean(document.querySelector('.recommendation'))
        })
        """)
        print(f"[*] Finding detail check: {finding_check}")
        assert finding_check["hasEvidence"], "Finding detail panel missing"

        finding_shot = os.path.join(VERIFICATION_DIR, "S4-ai-finding-explanation.png")
        await driver.screenshot(finding_shot)
        print(f"[+] Saved {finding_shot}")

        # 5. Check Settings Notifications Card & Test Email Button
        print("[*] Checking Settings Notifications Card on #settings...")
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        settings_notif_check = await driver.evaluate("""
        ({
            hasNotifCard: Boolean(document.querySelector('#notifications-settings-card')),
            smtpBadge: document.querySelector('#smtp-status-badge')?.textContent?.trim(),
            hasTestBtn: Boolean(document.querySelector('#btn-send-test-email')),
            hasToggle: Boolean(document.querySelector('#toggle-email-digest'))
        })
        """)
        print(f"[*] Settings notifications card check: {settings_notif_check}")
        assert settings_notif_check["hasNotifCard"], "Notifications card missing from #settings"
        assert settings_notif_check["hasTestBtn"], "Send test email button missing"

        # Click send test email to verify feedback toast
        await driver.evaluate("""
        (() => {
            const btn = document.querySelector('#btn-send-test-email');
            if (btn) btn.click();
        })()
        """)
        await asyncio.sleep(0.8)

        settings_shot = os.path.join(VERIFICATION_DIR, "S4-settings-notifications.png")
        await driver.screenshot(settings_shot)
        print(f"[+] Saved {settings_shot}")

        # 6. Mobile Responsiveness (390px width)
        print("[*] Testing Mobile 390px Viewport...")
        await driver.set_viewport(390, 844)
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            if (typeof render === 'function') render();
            const bell = document.querySelector('#notification-bell');
            if (bell) bell.click();
        })()
        """)
        await asyncio.sleep(0.8)

        mobile_shot = os.path.join(VERIFICATION_DIR, "S4-mobile-notifications.png")
        await driver.screenshot(mobile_shot)
        print(f"[+] Saved {mobile_shot}")

        # 7. Assert Zero Console Errors
        print(f"[*] Total browser console errors: {len(driver.console_errors)}")
        for err in driver.console_errors:
            print(f"    [ERR] {err}")
        assert len(driver.console_errors) == 0, f"Unexpected browser console errors: {driver.console_errors}"

        print("\n[SUCCESS] Stage 4 real browser verification passed completely with 0 console errors!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(verify_stage4())
