import asyncio
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def main():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)
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

        # 1. Initially drawer should be hidden
        visible_init = await driver.evaluate(
            "document.querySelector('#advanced-filters-drawer').style.display !== 'none'"
        )
        print(f"Drawer initial visible: {visible_init}")
        assert not visible_init, "Drawer should be collapsed initially"

        # 2. Click Filters toggle
        await driver.click("#toggle-advanced-filters", wait_seconds=0.5)
        visible_clicked = await driver.evaluate(
            "document.querySelector('#advanced-filters-drawer').style.display !== 'none'"
        )
        print(f"Drawer visible after click: {visible_clicked}")
        assert visible_clicked, "Drawer should be open after clicking toggle"

        # 3. Change a filter
        await driver.evaluate("""
        (() => {
            const sel = document.querySelector('#risk-filter');
            sel.value = 'High';
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        })()
        """)
        await asyncio.sleep(0.5)

        filtered_count = await driver.evaluate("document.querySelectorAll('.audit-table tbody tr').length")
        print(f"Filtered rows for High risk: {filtered_count}")
        assert filtered_count > 0, "Should show filtered high risk rows"

        # 4. Click clear filters
        await driver.click("#clear-filters", wait_seconds=0.5)
        state_risk = await driver.evaluate("state.auditRisk")
        print(f"State risk after clear: {state_risk}")
        assert state_risk == "All risks", "State risk should be reset to 'All risks'"

        print("[OK] Filter drawer and controls test passed perfectly!")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
