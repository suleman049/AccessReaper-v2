import asyncio
import sys
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

async def check():
    d = BrowserDriver(headless=True)
    await d.start()
    await d.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)
    await d.evaluate("""(async () => {
        window.FirebaseIdentity.phase = 'authorized';
        window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'admin@acme.corp', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
        window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'admin@acme.corp', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
        window.FirebaseIdentity.notify();
        if (window.ApiClient) {
            await window.ApiClient.loadAndRender();
        }
    })()""")
    await asyncio.sleep(1.0)
    await d.evaluate("""(() => {
        location.hash = 'risk?FND-2841';
        render();
    })()""")
    await asyncio.sleep(0.5)
    res = await d.evaluate("""(() => {
        return {
            title: document.querySelector('.risk-hero h2')?.textContent,
            hasEvidence: Boolean(document.querySelector('.evidence-snapshot')),
            policyContext: document.querySelector('.policy-context')?.innerHTML,
            hasRecommendation: Boolean(document.querySelector('.recommendation'))
        };
    })()""")
    print("Result:", res)
    print("Console errors:", d.console_errors)
    await d.close()

if __name__ == "__main__":
    asyncio.run(check())
