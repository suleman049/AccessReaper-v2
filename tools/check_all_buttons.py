import asyncio
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def check_buttons():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)
        # Auth dev admin
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

        # 1. Test clicking [data-audit-segment="high_risk"]
        print("Testing click on [data-audit-segment='high_risk']...")
        await driver.click('[data-audit-segment="high_risk"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "high_risk", f"Expected high_risk, got {seg}"

        # 2. Test clicking [data-audit-segment="jit"]
        print("Testing click on [data-audit-segment='jit']...")
        await driver.click('[data-audit-segment="jit"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "jit", f"Expected jit, got {seg}"

        # 3. Test clicking [data-audit-segment="expiring"]
        print("Testing click on [data-audit-segment='expiring']...")
        await driver.click('[data-audit-segment="expiring"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "expiring", f"Expected expiring, got {seg}"

        # 4. Test clicking [data-audit-segment="inactive"]
        print("Testing click on [data-audit-segment='inactive']...")
        await driver.click('[data-audit-segment="inactive"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "inactive", f"Expected inactive, got {seg}"

        # 5. Test clicking [data-audit-segment="remediated"]
        print("Testing click on [data-audit-segment='remediated']...")
        await driver.click('[data-audit-segment="remediated"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "remediated", f"Expected remediated, got {seg}"

        # 6. Test clicking [data-audit-segment="all"]
        print("Testing click on [data-audit-segment='all']...")
        await driver.click('[data-audit-segment="all"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        rows = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Segment: {seg}, Rows: {rows}")
        assert seg == "all", f"Expected all, got {seg}"

        # 7. Test clicking table action "Review" / "Details" button
        print("Testing click on first table action button...")
        first_btn_text = await driver.evaluate("document.querySelector('.table-action')?.textContent")
        print(f"First table action button text: {first_btn_text}")
        await driver.click(".table-action", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Location hash after click: {hash_val}")
        assert "risk" in hash_val, f"Expected risk hash, got {hash_val}"

        # Go back to audit
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            render();
        })()
        """)
        await asyncio.sleep(0.5)

        # 8. Test [data-audit-report]
        print("Testing click on [data-audit-report]...")
        await driver.click("[data-audit-report]", wait_seconds=0.5)
        modal_show = await driver.evaluate("document.querySelector('#review-modal').classList.contains('show')")
        print(f"Report modal opened: {modal_show}")
        assert modal_show, "Review modal should be visible"

        # Close modal
        await driver.evaluate("bootstrap.Modal.getInstance(document.querySelector('#review-modal')).hide()")
        await asyncio.sleep(0.5)

        # 9. Test sidebar links
        print("Testing sidebar navigation...")
        await driver.click("[data-page='approvals']", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Hash after clicking Approvals: {hash_val}")
        assert hash_val == "#approvals", f"Expected #approvals, got {hash_val}"

        await driver.click("[data-page='history']", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Hash after clicking Audit history: {hash_val}")
        assert hash_val == "#history", f"Expected #history, got {hash_val}"

        await driver.click("[data-page='users']", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Hash after clicking Users: {hash_val}")
        assert hash_val == "#users", f"Expected #users, got {hash_val}"

        await driver.click("[data-page='settings']", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Hash after clicking Settings: {hash_val}")
        assert hash_val == "#settings", f"Expected #settings, got {hash_val}"

        await driver.click("[data-page='audit']", wait_seconds=0.5)
        hash_val = await driver.evaluate("location.hash")
        print(f"Hash after clicking Access audit: {hash_val}")
        assert hash_val == "#audit", f"Expected #audit, got {hash_val}"

        # 10. Check console errors
        print("Console errors:", driver.console_errors)
        assert len(driver.console_errors) == 0, f"Errors: {driver.console_errors}"
        print("ALL BUTTON CHECKS PASSED!")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(check_buttons())
