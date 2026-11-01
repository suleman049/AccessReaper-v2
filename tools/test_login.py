import asyncio
import json
import sys
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

async def test():
    driver = BrowserDriver(headless=True)
    await driver.start()
    try:
        await driver.navigate("http://127.0.0.1:8100/#login", wait_seconds=2.0)
        
        # Authenticate dev user
        auth_script = """
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
            if (window.ApiClient) {
                ApiClient.loadAndRender();
            }
            location.hash = 'settings';
            if (typeof render === 'function') render();
            return true;
        })()
        """
        await driver.evaluate(auth_script)
        await asyncio.sleep(2.0)
        
        info = await driver.evaluate("""
        ({
            hash: location.hash,
            title: document.title,
            crumb: document.querySelector('#crumb-title')?.textContent,
            riskCard: Boolean(document.querySelector('#risk-rules-settings-card')),
            scheduleCard: Boolean(document.querySelector('#schedule-settings-card')),
            usersNav: Boolean(document.querySelector('a[href="#users"]')),
            h1: document.querySelector('h1')?.textContent
        })
        """)
        print("SETTINGS CHECK RESULT:", info)
        await driver.screenshot(r"D:\AccessReaper-v2\docs\verification\test_settings_live.png")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(test())
