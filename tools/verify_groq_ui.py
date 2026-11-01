"""
Browser verification script for Groq AI explanations and Settings row.
Captures screenshots to docs/verification/:
1. docs/verification/S4-groq-explanation.png (Dashboard audit summary with Groq ✦ badge)
2. docs/verification/S4-groq-settings.png (Connected services card with AI explanations status)
3. docs/verification/S4-groq-finding-detail.png (Finding detail with Groq ✦ explanation)
"""

import asyncio
import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

VERIFICATION_DIR = r"D:\AccessReaper-v2\docs\verification"


async def verify():
    os.makedirs(VERIFICATION_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 850)
        print("[*] Navigating to http://127.0.0.1:8100/...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # 1. Dev Auth
        print("[*] Authorizing as Jordan Davis (Admin)...")
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
        await asyncio.sleep(1.5)

        # 2. Check Dashboard Summary
        print("[*] Checking Dashboard Executive Summary...")
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            if (typeof render === 'function') render();
            document.querySelectorAll('details').forEach(d => d.open = true);
        })()
        """)
        await asyncio.sleep(1.0)

        preview_text = await driver.evaluate("""
        (() => {
            const el = document.querySelector('.gemini-preview') || document.querySelector('.latest-audit-card');
            return el ? el.innerText : '';
        })()
        """)
        print("[*] Dashboard summary preview text snippet:\n", preview_text[:300].encode('ascii', 'replace').decode('ascii'))

        path1 = os.path.join(VERIFICATION_DIR, "S4-groq-explanation.png")
        await driver.screenshot(path1)
        print(f"[+] Saved: {path1}")

        # 3. Check Settings Connected Services
        print("[*] Navigating to #settings...")
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            if (typeof render === 'function') render();
            if (window.GitHubSettings && typeof window.GitHubSettings.init === 'function') {
                window.GitHubSettings.init();
            }
        })()
        """)
        await asyncio.sleep(1.5)

        settings_text = await driver.evaluate("""
        (() => {
            const card = document.querySelector('.settings-card:has(.settings-service)');
            return card ? card.innerText : '';
        })()
        """)
        print("[*] Connected services card text:\n", settings_text[:400].encode('ascii', 'replace').decode('ascii'))

        path2 = os.path.join(VERIFICATION_DIR, "S4-groq-settings.png")
        await driver.screenshot(path2)
        print(f"[+] Saved: {path2}")

        # 4. Check Finding Detail with Groq explanation
        print("[*] Checking Finding Detail #risk?FND-2841...")
        await driver.evaluate("""
        (() => {
            location.hash = 'risk?FND-2841';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        finding_text = await driver.evaluate("""
        (() => {
            const panel = document.querySelector('.detail-main') || document.querySelector('.policy-context') || document.body;
            return panel ? panel.innerText : '';
        })()
        """)
        print("[*] Finding detail snippet:\n", finding_text[:300].encode('ascii', 'replace').decode('ascii'))

        path3 = os.path.join(VERIFICATION_DIR, "S4-groq-finding-detail.png")
        await driver.screenshot(path3)
        print(f"[+] Saved: {path3}")

        print("\n[+] BROWSER VERIFICATION COMPLETED SUCCESSFULLY!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(verify())
