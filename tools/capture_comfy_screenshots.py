import asyncio
import os
import shutil
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"


async def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 850)
        print("[*] Navigating to http://127.0.0.1:8100/...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        # 1. Dev Auth
        print("[*] Authorizing as Jordan Davis (Admin)...")
        await driver.evaluate("""
        (async () => {
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

        # Screenshot 1: Comfy Audit View (All assignments)
        print("[*] Navigating to #audit...")
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            state.auditSegment = 'all';
            render();
        })()
        """)
        await asyncio.sleep(1.0)
        p1 = os.path.join(DOCS_DIR, "comfy_audit_all.png")
        await driver.screenshot(p1)
        shutil.copy2(p1, os.path.join(ARTIFACTS_DIR, "comfy_audit_all.png"))
        print(f"[+] Saved comfy_audit_all.png")

        # Screenshot 2: Comfy High Risk Segment
        print("[*] Toggling High Risk segment...")
        await driver.evaluate("""
        (() => {
            state.auditSegment = 'high_risk';
            render();
        })()
        """)
        await asyncio.sleep(0.8)
        p2 = os.path.join(DOCS_DIR, "comfy_audit_high_risk.png")
        await driver.screenshot(p2)
        shutil.copy2(p2, os.path.join(ARTIFACTS_DIR, "comfy_audit_high_risk.png"))
        print(f"[+] Saved comfy_audit_high_risk.png")

        # Screenshot 3: Comfy JIT Segment
        print("[*] Toggling JIT segment...")
        await driver.evaluate("""
        (() => {
            state.auditSegment = 'jit';
            render();
        })()
        """)
        await asyncio.sleep(0.8)
        p3 = os.path.join(DOCS_DIR, "comfy_audit_jit.png")
        await driver.screenshot(p3)
        shutil.copy2(p3, os.path.join(ARTIFACTS_DIR, "comfy_audit_jit.png"))
        print(f"[+] Saved comfy_audit_jit.png")

        # Screenshot 4: Comfy Overview Dashboard
        print("[*] Navigating to #dashboard...")
        await driver.evaluate("""
        (() => {
            location.hash = 'dashboard';
            render();
        })()
        """)
        await asyncio.sleep(1.0)
        p4 = os.path.join(DOCS_DIR, "comfy_overview_dashboard.png")
        await driver.screenshot(p4)
        shutil.copy2(p4, os.path.join(ARTIFACTS_DIR, "comfy_overview_dashboard.png"))
        print(f"[+] Saved comfy_overview_dashboard.png")

        print("[✓] All comfy screenshots captured successfully.")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
