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
            // User arrives via hash with segment param:
            location.hash = 'audit?segment=high_risk';
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        seg_init = await driver.evaluate("state.auditSegment")
        print(f"Initial state.auditSegment: {seg_init}")

        # Now simulate user clicking 'All (30)'
        print("Clicking All (30) button...")
        await driver.click('[data-audit-segment="all"]', wait_seconds=0.5)

        seg_after = await driver.evaluate("state.auditSegment")
        print(f"state.auditSegment after clicking All: {seg_after}")

        if seg_after != "all":
            print("BUG CONFIRMED: Click did not change segment to 'all'! It stayed:", seg_after)
        else:
            print("Segment changed correctly to 'all'")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
