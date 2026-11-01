import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")
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
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        # 1. Dashboard buttons
        print("--- Testing Dashboard Buttons ---")
        dash_buttons = await driver.evaluate("""
        Array.from(document.querySelectorAll('button, a[data-page-link]')).map(el => ({
            tag: el.tagName,
            text: el.textContent.trim().replace(/\\s+/g, ' '),
            dataset: Object.assign({}, el.dataset),
            href: el.getAttribute('href'),
            id: el.id
        }))
        """)
        print(f"Found {len(dash_buttons)} clickable elements on Dashboard")
        for b in dash_buttons[:10]:
            print("  -", b)

        # Click View Security Audit on Dashboard
        view_audit_btn = await driver.evaluate("Boolean(document.querySelector('[data-page-link=\"audit\"]'))")
        print(f"Has [data-page-link='audit']: {view_audit_btn}")
        if view_audit_btn:
            await driver.click('[data-page-link="audit"]', wait_seconds=0.5)
            h = await driver.evaluate("location.hash")
            print(f"Hash after clicking View Security Audit: {h}")

        # Now on #audit
        print("--- Testing Audit Page Buttons ---")
        audit_buttons = await driver.evaluate("""
        Array.from(document.querySelectorAll('button, a[data-page-link]')).map(el => ({
            tag: el.tagName,
            text: el.textContent.trim().replace(/\\s+/g, ' '),
            dataset: Object.assign({}, el.dataset),
            href: el.getAttribute('href'),
            id: el.id
        }))
        """)
        print(f"Found {len(audit_buttons)} clickable elements on Audit page")
        for b in audit_buttons:
            print("  -", b)

        # Click High Risk segment
        await driver.click('[data-audit-segment="high_risk"]', wait_seconds=0.5)
        seg = await driver.evaluate("state.auditSegment")
        print(f"Clicked High Risk, state.auditSegment = {seg}")

        # Click "Show All (30)" in the banner
        banner_show_all = await driver.evaluate("Boolean(document.querySelector('.alert button[data-audit-segment=\"all\"]'))")
        print(f"Banner has Show All button: {banner_show_all}")
        if banner_show_all:
            await driver.click('.alert button[data-audit-segment="all"]', wait_seconds=0.5)
            seg2 = await driver.evaluate("state.auditSegment")
            print(f"Clicked Show All in banner, state.auditSegment = {seg2}")

        # Click Export CSV
        print("Testing Export CSV button...")
        has_export = await driver.evaluate("Boolean(document.querySelector('[data-export=\"audit\"]'))")
        print(f"Has export button: {has_export}")
        if has_export:
            await driver.click('[data-export="audit"]', wait_seconds=0.5)
            toast_text = await driver.evaluate("document.querySelector('.toast-card')?.textContent")
            print(f"Toast after export: {toast_text}")

        # Check console errors
        print("Console errors:", driver.console_errors)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
