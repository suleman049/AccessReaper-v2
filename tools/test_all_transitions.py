import asyncio
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def main():
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
            location.hash = 'audit?segment=high_risk';
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        buttons_to_test = [
            ("jit", "JIT Leases"),
            ("expiring", "Expiring"),
            ("inactive", "Dormant"),
            ("remediated", "Remediated"),
            ("high_risk", "High Risk"),
            ("all", "All"),
        ]

        for seg_val, label in buttons_to_test:
            print(f"Testing transition to '{seg_val}' ({label})...")
            selector = f'[data-audit-segment="{seg_val}"]'
            await driver.click(selector, wait_seconds=0.4)
            current_seg = await driver.evaluate("state.auditSegment")
            current_hash = await driver.evaluate("location.hash")
            print(f"  Result -> state.auditSegment: {current_seg}, hash: {current_hash}")
            assert current_seg == seg_val, f"Failed for {seg_val}: got {current_seg}"

        print("\nTesting Clear Filters from active segment...")
        await driver.click('[data-audit-segment="high_risk"]', wait_seconds=0.4)
        await driver.click("#clear-filters", wait_seconds=0.4)
        cleared_seg = await driver.evaluate("state.auditSegment")
        cleared_hash = await driver.evaluate("location.hash")
        print(f"  Result -> state.auditSegment: {cleared_seg}, hash: {cleared_hash}")
        assert cleared_seg == "all", f"Failed clear-filters: got {cleared_seg}"

        print("\n[ALL BUTTON TRANSITIONS PASSED FLAWLESSLY!]")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
