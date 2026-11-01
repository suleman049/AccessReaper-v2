"""
Browser verification script for leftover label fixes in AccessReaper v2.
Verifies and screenshots:
1. docs/verification/fix-audit-collapsed.png - Access audit page collapsed disclosure header
2. docs/verification/fix-audit-expanded.png - Access audit page expanded disclosure
3. docs/verification/fix-overview.png - Dashboard overview card
4. docs/verification/fix-finding-detail.png - Finding detail view (#risk?FND-2841)
5. docs/verification/fix-report-dialog.png - Audit report dialog modal
6. PDF check - verifies /api/audits/{id}/export-pdf returns valid PDF bytes
"""

import asyncio
import os
import sys
import httpx

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

VERIFICATION_DIR = r"D:\AccessReaper-v2\docs\verification"


async def run_verification():
    os.makedirs(VERIFICATION_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 850)
        print("[*] Navigating to http://127.0.0.1:8100/...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # Authorize as Admin
        print("[*] Authorizing in dev mode...")
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

        # 1. Access audit page: Collapsed disclosure
        print("[*] Verifying #audit collapsed disclosure...")
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            if (typeof render === 'function') render();
            const d = document.querySelector('.audit-summary-disclosure');
            if (d) d.open = false;
        })()
        """)
        await asyncio.sleep(1.0)

        header_text = await driver.evaluate("""
        (() => {
            const sum = document.querySelector('.audit-summary-disclosure summary');
            return sum ? sum.innerText : '';
        })()
        """)
        print("[*] Collapsed header text:", repr(header_text.encode('ascii', 'replace').decode('ascii')))
        assert "Gemini" not in header_text, f"Gemini leaked in collapsed header: {header_text}"
        assert "Preview" not in header_text, f"Preview leaked in collapsed header: {header_text}"

        path_collapsed = os.path.join(VERIFICATION_DIR, "fix-audit-collapsed.png")
        await driver.screenshot(path_collapsed)
        print(f"[+] Saved: {path_collapsed}")

        # 2. Access audit page: Expanded disclosure
        print("[*] Verifying #audit expanded disclosure...")
        await driver.evaluate("""
        (() => {
            const d = document.querySelector('.audit-summary-disclosure');
            if (d) d.open = true;
        })()
        """)
        await asyncio.sleep(0.5)

        expanded_text = await driver.evaluate("""
        (() => {
            const d = document.querySelector('.audit-summary-disclosure');
            return d ? d.innerText : '';
        })()
        """)
        print("[*] Expanded text snippet:", repr(expanded_text[:200].encode('ascii', 'replace').decode('ascii')))
        assert "Gemini" not in expanded_text, f"Gemini leaked in expanded text: {expanded_text}"

        path_expanded = os.path.join(VERIFICATION_DIR, "fix-audit-expanded.png")
        await driver.screenshot(path_expanded)
        print(f"[+] Saved: {path_expanded}")

        # 3. Overview Dashboard
        print("[*] Verifying #dashboard overview card...")
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        overview_text = await driver.evaluate("""
        (() => {
            const c = document.querySelector('.latest-audit-card');
            return c ? c.innerText : '';
        })()
        """)
        print("[*] Overview card text snippet:", repr(overview_text[:200].encode('ascii', 'replace').decode('ascii')))
        assert "Gemini" not in overview_text, f"Gemini leaked in overview: {overview_text}"

        path_overview = os.path.join(VERIFICATION_DIR, "fix-overview.png")
        await driver.screenshot(path_overview)
        print(f"[+] Saved: {path_overview}")

        # 4. Finding Detail View
        print("[*] Verifying finding detail view...")
        # Check 4a: Without AI explanation (template fallback)
        await driver.evaluate("""
        (() => {
            const firstId = (people[0] && people[0].id) || 'FND-2853';
            location.hash = 'risk?' + firstId;
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(1.0)

        detail_text = await driver.evaluate("""
        (() => {
            const el = document.querySelector('.policy-context');
            return el ? el.innerText : '';
        })()
        """)
        print("[*] Finding detail (template fallback) text:", repr(detail_text.encode('ascii', 'replace').decode('ascii')))
        assert "Gemini" not in detail_text, f"Gemini leaked in finding detail: {detail_text}"
        assert "Preview" not in detail_text, f"Preview leaked in finding detail: {detail_text}"
        assert "is not connected" not in detail_text, f"'is not connected' found: {detail_text}"
        assert "Generated from report data" in detail_text, f"Expected 'Generated from report data': {detail_text}"

        # Check 4b: With live Groq AI explanation
        await driver.evaluate("""
        (() => {
            if (people[0] && people[0].finding) {
                people[0].finding.aiExplanation = "Collaborator has administrative privileges on production repository.";
                people[0].finding.aiStatus = "success";
                people[0].finding.aiModel = "openai/gpt-oss-120b";
            }
            if (typeof render === 'function') render();
        })()
        """)
        await asyncio.sleep(0.5)

        groq_detail_text = await driver.evaluate("""
        (() => {
            const el = document.querySelector('.policy-context');
            return el ? el.innerText : '';
        })()
        """)
        print("[*] Finding detail (live Groq) text:", repr(groq_detail_text.encode('ascii', 'replace').decode('ascii')))
        assert "Groq" in groq_detail_text, f"Expected Groq badge in finding detail: {groq_detail_text}"
        assert "Generated by Groq — verify before acting" in groq_detail_text, f"Expected Groq disclaimer: {groq_detail_text}"
        assert "Gemini" not in groq_detail_text, f"Gemini leaked in finding detail: {groq_detail_text}"
        assert "Preview" not in groq_detail_text, f"Preview leaked in finding detail: {groq_detail_text}"

        path_detail = os.path.join(VERIFICATION_DIR, "fix-finding-detail.png")
        await driver.screenshot(path_detail)
        print(f"[+] Saved: {path_detail}")

        # 5. Audit Report Dialog Modal
        print("[*] Verifying Audit Report dialog modal...")
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            if (typeof render === 'function') render();
            const repId = (auditRuns.at(-1) || {}).id || 'AUD-20261014-001';
            Governance.report(repId);
        })()
        """)
        await asyncio.sleep(1.5)

        modal_text = await driver.evaluate("""
        (() => {
            const m = document.querySelector('#review-modal');
            return m ? m.innerText : '';
        })()
        """)
        print("[*] Modal text snippet:", repr(modal_text[:250].encode('ascii', 'replace').decode('ascii')))
        assert "Gemini" not in modal_text, f"Gemini leaked in audit report dialog: {modal_text}"

        path_modal = os.path.join(VERIFICATION_DIR, "fix-report-dialog.png")
        await driver.screenshot(path_modal)
        print(f"[+] Saved: {path_modal}")

        # Close modal
        await driver.evaluate("""
        (() => {
            const m = document.querySelector('#review-modal');
            if (m && window.bootstrap) {
                const inst = bootstrap.Modal.getInstance(m);
                if (inst) inst.hide();
            }
        })()
        """)
        await asyncio.sleep(0.5)

        # 6. PDF Smoke Verification
        print("[*] Verifying PDF export endpoint...")
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "http://127.0.0.1:8100/api/audits/AUD-20261014-001/report.pdf",
                headers={"Authorization": "Bearer dev-token", "X-Dev-User": "admin@acme.corp"},
            )
            assert res.status_code == 200, f"PDF export failed with status {res.status_code}"
            assert res.content.startswith(b"%PDF-"), "Response does not start with %PDF-"
            print(f"[+] PDF export successful: {len(res.content)} bytes, starts with {res.content[:8]}")

        print("[OK] All browser verifications passed successfully!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_verification())
