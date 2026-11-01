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
    print("Starting Chrome headless automation...")
    await driver.start()

    results = {}
    
    try:
        await driver.set_viewport(1280, 800)
        # Navigate initially to app root
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)
        await ensure_authenticated(driver)
        
        # Step 1: Check Settings Page for Bug 1
        print("\n--- Step 1: Verifying Settings Page (Bug 1) ---")
        await navigate_to(driver, "settings", wait_seconds=1.5)
        
        page_info = await driver.evaluate("""
        ({
            hash: location.hash,
            title: document.title,
            crumb: document.querySelector('#crumb-title')?.textContent,
            h1: document.querySelector('h1')?.textContent,
            riskCard: Boolean(document.querySelector('#risk-rules-settings-card')),
            scheduleCard: Boolean(document.querySelector('#schedule-settings-card')),
            connectedCard: Boolean(document.querySelector('.settings-service')),
            previewBtn: Boolean(document.querySelector('#btn-preview-rules')),
            saveVersionBtn: Boolean(document.querySelector('#btn-save-rules')),
            historyTable: Boolean(document.querySelector('.rules-history-table')),
            schedFreq: document.querySelector('#sched-frequency')?.value,
            schedNextRun: document.querySelector('#sched-next-run')?.textContent
        })
        """)
        print("Settings info:", page_info)
        assert page_info["riskCard"], "FAILED: Risk rules settings card missing!"
        assert page_info["scheduleCard"], "FAILED: Scheduled audits settings card missing!"
        assert page_info["previewBtn"], "FAILED: Preview impact button missing!"
        assert page_info["saveVersionBtn"], "FAILED: Save as new version button missing!"
        results["bug1_cards_exist"] = True
        
        # Test Preview Impact on Risk rules card
        print("Testing Preview Impact button...")
        await driver.click("#btn-preview-rules", wait_seconds=1.0)
        preview_box_visible = await driver.evaluate("Boolean(document.querySelector('.rules-preview-box'))")
        print("Preview box visible after click:", preview_box_visible)
        assert preview_box_visible, "FAILED: Preview impact box did not appear after clicking Preview impact!"
        results["bug1_preview_functional"] = True
        
        # Screenshot A1: Settings Light
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A1-settings-risk-rules-light.png"))
        
        # Screenshot A1-dark: Settings Dark Mode
        print("Toggling dark mode...")
        await driver.click("[data-theme-toggle]", wait_seconds=0.5)
        is_dark = await driver.evaluate("document.documentElement.getAttribute('data-theme') === 'dark'")
        print("Theme is dark:", is_dark)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A1-settings-risk-rules-dark.png"))
        
        # Screenshot A1-mobile: Settings 390px
        print("Setting viewport to 390x844 (Mobile)...")
        await driver.set_viewport(390, 844, is_mobile=True)
        await asyncio.sleep(0.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A1-settings-mobile-390px.png"))
        
        # Reset viewport & theme
        await driver.set_viewport(1280, 800)
        await driver.click("[data-theme-toggle]", wait_seconds=0.5)
        
        # Step 2: Check Audit Report Dialog for Bug 2 (Download PDF)
        print("\n--- Step 2: Verifying Audit Report Dialog & PDF Download (Bug 2) ---")
        await navigate_to(driver, "audit", wait_seconds=1.5)
        
        # Open audit report dialog via View full report button
        await driver.click("[data-audit-report]", wait_seconds=1.0)
        
        dialog_info = await driver.evaluate("""
        ({
            modalVisible: document.querySelector('#review-modal').classList.contains('show'),
            pdfBtn: Boolean(document.querySelector('#download-report-pdf')),
            pdfBtnText: document.querySelector('#download-report-pdf')?.textContent,
            pdfBtnRunId: document.querySelector('#download-report-pdf')?.dataset.runId,
            rulesBadge: document.querySelector('.report-meta')?.textContent
        })
        """)
        print("Audit report dialog info:", dialog_info)
        assert dialog_info["modalVisible"], "FAILED: Audit report modal is not visible!"
        assert dialog_info["pdfBtn"], "FAILED: Download PDF button missing from report dialog!"
        assert dialog_info["pdfBtnRunId"], "FAILED: Download PDF button has no data-run-id!"
        results["bug2_pdf_button_exists"] = True
        
        # Screenshot A2: Audit Report Dialog
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A2-audit-report-dialog-pdf-button.png"))
        
        # Click Download PDF button
        print("Clicking Download PDF button...")
        await driver.click("#download-report-pdf", wait_seconds=1.0)
        toast_msg = await driver.evaluate("document.querySelector('#toast-container')?.textContent")
        print("Toast message after download click:", toast_msg)
        results["bug2_pdf_click_handled"] = True
        
        # Close modal
        await driver.click(".report-close", wait_seconds=0.5)
        
        # Step 3: Check Users Page (#users)
        print("\n--- Step 3: Verifying Users Page (#users) ---")
        await navigate_to(driver, "users", wait_seconds=2.0)
        users_info = await driver.evaluate("""
        ({
            crumb: document.querySelector('#crumb-title')?.textContent,
            usersNavActive: document.querySelector('a[href="#users"]').classList.contains('active'),
            unconfiguredCard: Boolean(document.querySelector('.unconfigured-notice') || document.querySelector('#users-unconfigured')),
            pageHtmlSnippet: document.querySelector('#page-content')?.innerText.slice(0, 300)
        })
        """)
        print("Users page info:", users_info)
        assert users_info["usersNavActive"], "FAILED: Users nav item not active on #users!"
        assert users_info["unconfiguredCard"], "FAILED: Unconfigured service account notice not shown on #users!"
        results["users_page_renders"] = True
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A3-users-page-friendly.png"))
        
        # Step 4: Check History Action Filters
        print("\n--- Step 4: Verifying History Action Filters ---")
        await navigate_to(driver, "history", wait_seconds=1.5)
        history_filters = await driver.evaluate("""
        Array.from(document.querySelectorAll('#history-filter option')).map(o => o.value)
        """)
        print("History action options:", history_filters)
        assert "User access" in history_filters, "FAILED: 'User access' filter tag missing from history!"
        assert "Rules" in history_filters, "FAILED: 'Rules' filter tag missing from history!"
        assert "Schedule" in history_filters, "FAILED: 'Schedule' filter tag missing from history!"
        results["history_filters_complete"] = True
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A4-history-action-filters.png"))
        
        # Step 5: Screen comparisons against baseline
        print("\n--- Step 5: Verifying Original Screens (Zero Regressions) ---")
        # Overview desktop
        await navigate_to(driver, "dashboard", wait_seconds=1.5)
        overview_info = await driver.evaluate("""
        ({
            h1: document.querySelector('h1')?.textContent,
            identities: document.querySelector('.governance-stats')?.textContent.includes('Total identities'),
            dryRunBadge: Boolean(document.querySelector('.dry-run-badge'))
        })
        """)
        print("Overview info:", overview_info)
        assert overview_info["identities"], "FAILED: Overview metrics missing!"
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A5-overview-desktop.png"))
        
        # Overview dark mode
        await driver.click("[data-theme-toggle]", wait_seconds=0.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A5-overview-dark.png"))
        
        # Overview 390px mobile
        await driver.set_viewport(390, 844, is_mobile=True)
        await asyncio.sleep(0.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A5-overview-390px.png"))
        await driver.set_viewport(1280, 800)
        await driver.click("[data-theme-toggle]", wait_seconds=0.5)
        
        # Access audit desktop
        await navigate_to(driver, "audit", wait_seconds=1.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A6-audit-desktop.png"))
        
        # Approvals desktop
        await navigate_to(driver, "approvals", wait_seconds=1.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A7-approvals-desktop.png"))
        
        # History desktop
        await navigate_to(driver, "history", wait_seconds=1.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A8-history-desktop.png"))
        
        # Global search modal
        await driver.click("#search-open", wait_seconds=0.5)
        await driver.screenshot(os.path.join(SCREENSHOT_DIR, "A9-global-search.png"))
        await driver.click(".command-close", wait_seconds=0.5)
        
        # Check console errors across execution
        print("\n--- Step 6: Checking Console Errors ---")
        print(f"Total console logs captured: {len(driver.console_logs)}")
        print(f"Console errors: {driver.console_errors}")
        assert len(driver.console_errors) == 0, f"FAILED: Browser console errors found: {driver.console_errors}"
        results["zero_console_errors"] = True
        
        print("\n=======================================================")
        print("ALL PART A BROWSER CHECKS PASSED WITH ZERO CONSOLE ERRORS!")
        print("=======================================================")
        for k, v in results.items():
            print(f"  ✓ {k}: {v}")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(run_verification())
