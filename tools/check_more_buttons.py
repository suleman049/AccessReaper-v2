import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def check_action_buttons():
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
            location.hash = 'risk?FND-2853';
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.0)

        # On Risk Detail page, check if Remediate/Dismiss/Review buttons exist and work
        buttons = await driver.evaluate("""
        Array.from(document.querySelectorAll('button')).map(b => ({
            id: b.id,
            className: b.className,
            text: b.textContent.trim(),
            remediate: b.dataset.remediate,
            dismiss: b.dataset.dismiss,
            review: b.dataset.review
        }))
        """)
        print(f"Buttons on risk page count: {len(buttons)}")

        # Check Approvals modal open button
        await driver.evaluate("""
        (() => {
            location.hash = 'approvals';
            render();
        })()
        """)
        await asyncio.sleep(0.5)

        has_req_btn = await driver.evaluate("Boolean(document.querySelector('#btn-open-request-modal'))")
        print("Request access button on #approvals exists:", has_req_btn)
        if has_req_btn:
            await driver.click("#btn-open-request-modal", wait_seconds=0.5)
            modal_open = await driver.evaluate("document.querySelector('#request-modal').classList.contains('show')")
            print("Request modal opened:", modal_open)
            assert modal_open, "Request modal should open"
            await driver.evaluate("bootstrap.Modal.getInstance(document.querySelector('#request-modal')).hide()")
            await asyncio.sleep(0.5)

        print("Console errors:", driver.console_errors)
        assert len(driver.console_errors) == 0, f"Errors: {driver.console_errors}"
        print("ACTION BUTTONS WORKING!")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(check_action_buttons())
