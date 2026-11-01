import asyncio
import os
import shutil
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"


async def main():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.set_viewport(1280, 850)
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)
        await driver.evaluate("""
        (async () => {
            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'admin@acme.corp', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'admin@acme.corp', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            window.FirebaseIdentity.notify();
            location.hash = 'audit';
            state.auditSegment = 'all';
            state.showFilters = true;
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)
        p = os.path.join(DOCS_DIR, "comfy_audit_filters_open.png")
        await driver.screenshot(p)
        shutil.copy2(p, os.path.join(ARTIFACTS_DIR, "comfy_audit_filters_open.png"))
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
