import asyncio
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def _run_smoke():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.set_viewport(1280, 800)
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=2.0)

        for _ in range(30):
            try:
                has_fb = await driver.evaluate("Boolean(window.FirebaseIdentity)")
                if has_fb:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)

        # Authenticate dev admin
        await driver.evaluate("""
        (() => {
            if (!window.FirebaseIdentity) {
                window.FirebaseIdentity = {
                    phase: 'authorized',
                    user: null,
                    profile: null,
                    get authorized() { return true; },
                    notify: () => { document.dispatchEvent(new Event('identity-changed')); }
                };
            }
            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'jordan.davis@acme.io', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'jordan.davis@acme.io', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            if (typeof window.FirebaseIdentity.notify === 'function') window.FirebaseIdentity.notify();
            return true;
        })()
        """)
        await asyncio.sleep(0.5)

        # 1. Assert Settings Cards Exist
        await driver.evaluate("""
        (() => {
            location.hash = 'settings';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        settings_cards = await driver.evaluate("""
        ({
            riskCard: Boolean(document.querySelector('#risk-rules-settings-card')),
            scheduleCard: Boolean(document.querySelector('#schedule-settings-card')),
            previewBtn: Boolean(document.querySelector('#btn-preview-rules')),
            saveVersionBtn: Boolean(document.querySelector('#btn-save-rules'))
        })
        """)
        assert settings_cards["riskCard"], "Risk rules settings card missing from #settings"
        assert settings_cards["scheduleCard"], "Scheduled audits settings card missing from #settings"
        assert settings_cards["previewBtn"], "Preview impact button missing from #settings"
        assert settings_cards["saveVersionBtn"], "Save as new version button missing from #settings"

        # 2. Assert Audit Report Modal & PDF Button
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        await driver.click("[data-audit-report]", wait_seconds=1.0)
        report_modal = await driver.evaluate("""
        ({
            modalVisible: document.querySelector('#review-modal').classList.contains('show'),
            pdfBtn: Boolean(document.querySelector('#download-report-pdf')),
            pdfBtnRunId: document.querySelector('#download-report-pdf')?.dataset.runId
        })
        """)
        assert report_modal["modalVisible"], "Audit report dialog not visible"
        assert report_modal["pdfBtn"], "Download PDF button missing from audit report dialog"
        assert report_modal["pdfBtnRunId"] and report_modal["pdfBtnRunId"].startswith("AUD-"), (
            f"Unexpected audit run ID: {report_modal['pdfBtnRunId']}"
        )

        # Zero console errors
        assert len(driver.console_errors) == 0, f"Browser console errors: {driver.console_errors}"
    finally:
        await driver.close()


def test_settings_cards_and_pdf_smoke():
    asyncio.run(_run_smoke())
