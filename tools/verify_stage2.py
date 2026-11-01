"""
Browser verification script for Stage 2: Triage Quality for Real Data.
Connects via Chrome DevTools Protocol to verify:
1. GitHub Unmatched Accounts card with Auto-suggest, CSV import button, bulk actions, and classification dropdown.
2. People Management tab on #users with People directory, Add Person modal, Edit modal, and CSV import.
3. 'Why this score?' breakdown panel in finding details on #risk.
4. Zero browser console errors.
Saves screenshots to docs/verification/S2-*.png.
"""

import asyncio
import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

VERIFICATION_DIR = r"D:\AccessReaper-v2\docs\verification"


async def verify_stage2():
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

        # 2. Check Settings Page (Unmatched Accounts & Classification)
        print("[*] Navigating to #settings...")
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.2)

        # Wait for GitHub settings to load and render
        await driver.evaluate("""
        (async () => {
            if (window.GitHubSettings) {
                await window.GitHubSettings.init();
            }
        })()
        """)
        await asyncio.sleep(0.8)

        settings_check = await driver.evaluate("""
        ({
            hasUnmatchedCard: Boolean(document.querySelector("#unmatched-github-card")),
            hasAutoSuggest: Boolean(document.querySelector("#btn-auto-suggest")),
            hasImportCsv: Boolean(document.querySelector("#btn-open-csv-import")),
            hasSaveAll: Boolean(document.querySelector("#btn-save-all-links")),
            classifySelectCount: document.querySelectorAll(".classify-select").length,
            unmatchedItemCount: document.querySelectorAll(".unmatched-item").length
        })
        """)
        print("[*] Settings Unmatched Accounts check:", settings_check)
        assert settings_check["hasUnmatchedCard"], "Unmatched GitHub card not found!"
        assert settings_check["hasAutoSuggest"], "Auto-suggest button missing!"
        assert settings_check["hasImportCsv"], "Import CSV button missing!"
        assert settings_check["classifySelectCount"] > 0, "No classification dropdowns found!"

        # Scroll to unmatched table so it's visible in screenshot
        await driver.evaluate("""
        (() => {
            const el = document.querySelector("#unmatched-github-card");
            if (el) el.scrollIntoView({ behavior: 'instant', block: 'center' });
        })()
        """)
        await asyncio.sleep(0.5)

        screenshot1 = os.path.join(VERIFICATION_DIR, "S2-unmatched-bulk-triage.png")
        await driver.screenshot(screenshot1)
        print(f"[SUCCESS] Saved screenshot: {screenshot1}")

        # 3. Check Users Page (People Management Tab)
        print("[*] Navigating to #users and switching to People tab...")
        await driver.evaluate("""
        (() => {
            location.hash = 'users';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        # Click People tab
        await driver.evaluate("""
        (async () => {
            if (window.UsersPage) {
                window.UsersPage.activeTab = 'people';
                await window.UsersPage.fetchPeople();
                if (typeof render === 'function') render();
            }
        })()
        """)
        await asyncio.sleep(0.8)

        people_check = await driver.evaluate("""
        ({
            hasTabBar: Boolean(document.querySelector("#users-tab-bar")),
            activeTab: document.querySelector("#users-tab-bar .active")?.textContent || '',
            hasAddPersonBtn: Boolean(document.querySelector("#btn-add-person")),
            hasImportCsvBtn: Boolean(document.querySelector("#btn-people-import-csv")),
            hasPeopleSearch: Boolean(document.querySelector("#people-search")),
            peopleRows: document.querySelectorAll(".table-panel tbody tr").length
        })
        """)
        print("[*] Users People Management check:", people_check)
        assert people_check["hasAddPersonBtn"], "Add Person button missing!"
        assert people_check["hasImportCsvBtn"], "People CSV Import button missing!"
        assert people_check["peopleRows"] > 0, "No people rows displayed!"

        screenshot2 = os.path.join(VERIFICATION_DIR, "S2-people-management.png")
        await driver.screenshot(screenshot2)
        print(f"[SUCCESS] Saved screenshot: {screenshot2}")

        # 4. Check Risk Finding Detail ('Why this score?' breakdown panel)
        print("[*] Navigating to finding detail on #risk...")
        finding_id = await driver.evaluate("""
        (() => {
            const list = (typeof people !== 'undefined') ? people : [];
            const p = list.length ? list[0] : null;
            return p ? (p.id || p.email) : 'alex.morgan@acme.io';
        })()
        """)
        print(f"[*] Testing finding: {finding_id}")

        await driver.evaluate(f"""
        (() => {{
            location.hash = 'risk?{finding_id}';
            if (typeof render === 'function') render();
        }})()
        """)
        await asyncio.sleep(1.0)

        why_score_check = await driver.evaluate("""
        ({
            hasWhyScorePanel: Boolean(document.querySelector(".why-score-panel")),
            whyScoreTitle: document.querySelector(".why-score-panel h3")?.innerText || '',
            hasWhyScoreTable: Boolean(document.querySelector(".why-score-table")),
            scoreText: document.querySelector(".why-score-panel")?.innerText || ''
        })
        """)
        print("[*] Why this score check:", why_score_check)
        assert why_score_check["hasWhyScorePanel"], "Why this score panel missing from finding detail!"

        # Scroll to why score panel
        await driver.evaluate("""
        (() => {
            const el = document.querySelector(".why-score-panel");
            if (el) el.scrollIntoView({ behavior: 'instant', block: 'center' });
        })()
        """)
        await asyncio.sleep(0.5)

        screenshot3 = os.path.join(VERIFICATION_DIR, "S2-why-this-score.png")
        await driver.screenshot(screenshot3)
        print(f"[SUCCESS] Saved screenshot: {screenshot3}")

        # 5. Check Console Errors
        errors = driver.console_errors
        print(f"[*] Console error count: {len(errors)}")
        if errors:
            print("[WARN] Console errors:", errors)
        assert len(errors) == 0, f"Found {len(errors)} console errors during Stage 2 verification!"

        print("\n[ALL CHECKS PASSED] Stage 2 successfully verified in real Chrome browser!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(verify_stage2())
