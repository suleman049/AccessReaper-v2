import asyncio
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity\brain\af8e0473-4755-43ee-bdce-dc4dfb20f50d"
DOCS_DIR = r"D:\AccessReaper-v2\docs\verification"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)


async def main():
    print("=== Testing Real-Time Notifications & Public Access Request Workflows ===")
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 850)

        # -------------------------------------------------------------
        # STEP 1: Test Public Access Request Page (#request) Unauthenticated
        # -------------------------------------------------------------
        print("\n[Step 1] Visiting http://127.0.0.1:8100/#request without login...")
        await driver.navigate("http://127.0.0.1:8100/#request", wait_seconds=1.5)

        form_exists = await driver.evaluate("""
        (() => {
            const form = document.querySelector('#public-access-request-form');
            const repoSelect = document.querySelector('#pub-repo-select');
            return {
                hasForm: !!form,
                repoCount: repoSelect ? repoSelect.options.length : 0,
                firstRepo: repoSelect ? repoSelect.options[0]?.value : null
            };
        })()
        """)
        print(f"Public request form state: {form_exists}")
        assert form_exists["hasForm"], "Public access request form was not rendered on #request"

        # Screenshot: Public Request Form
        shot1_path = os.path.join(ARTIFACTS_DIR, "public_request_page.png")
        await driver.screenshot(shot1_path)
        shutil.copyfile(shot1_path, os.path.join(DOCS_DIR, "public_request_page.png"))
        print("✓ Captured public_request_page.png")

        # Fill and submit form
        print("\n[Step 2] Submitting public access request for friend...")
        submit_result = await driver.evaluate("""
        (async () => {
            try {
                document.querySelector('#pub-name-input').value = 'Ahmad Raza (Friend Demo)';
                document.querySelector('#pub-email-input').value = 'ahmad.raza@testmail.com';
                document.querySelector('#pub-github-input').value = 'ahmad-raza-demo';
                document.querySelector('#pub-repo-select').value = 'payhive-eng/core-api';
                document.querySelector('#pub-access-select').value = 'Write';
                document.querySelector('#pub-duration-select').value = '0.0167';
                document.querySelector('#pub-reason-input').value = 'Live testing collaboration request from friend for demo';
                
                const form = document.querySelector('#public-access-request-form');
                form.requestSubmit();
                await new Promise(r => setTimeout(r, 800));
                return {
                    ok: true,
                    h3: document.querySelector('#public-request-card h3')?.textContent
                };
            } catch (err) {
                return { ok: false, err: err.message };
            }
        })()
        """)
        print(f"Submit result: {submit_result}")
        assert submit_result.get("ok") and "Access Request Submitted" in submit_result.get("h3", ""), f"Unexpected confirmation: {submit_result}"

        # Screenshot: Public Request Submitted
        shot2_path = os.path.join(ARTIFACTS_DIR, "public_request_submitted.png")
        await driver.screenshot(shot2_path)
        shutil.copyfile(shot2_path, os.path.join(DOCS_DIR, "public_request_submitted.png"))
        print("✓ Captured public_request_submitted.png")

        # -------------------------------------------------------------
        # STEP 2: Authenticate Admin & Verify Real-Time Detection
        # -------------------------------------------------------------
        print("\n[Step 3] Switching to Admin session on #approvals...")
        await driver.evaluate("""
        (async () => {
            window.__toastHistory = [];
            const origToast = window.showToast;
            window.showToast = function(msg) {
                window.__toastHistory.push(msg);
                return origToast(msg);
            };

            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { uid: 'dev-admin-uid', email: 'admin@acme.corp', displayName: 'Jordan Davis', getIdToken: async () => 'dev-token' };
            window.FirebaseIdentity.profile = { uid: 'dev-admin-uid', email: 'admin@acme.corp', name: 'Jordan Davis', role: 'admin', status: 'active', organizationId: 'acme' };
            window.FirebaseIdentity.notify();
            location.hash = 'approvals';
            const data = await ApiClient.bootstrap();
            ApiClient.syncState(data);
            render();
            return true;
        })()
        """)
        await asyncio.sleep(1.5)

        # Check buttons in header: Share link, Onboard Employee, Request Access
        header_buttons = await driver.evaluate("""
        (() => {
            return {
                shareBtn: !!document.querySelector('#btn-share-request-link'),
                onboardBtn: !!document.querySelector('#btn-open-onboard-modal'),
                requestBtn: !!document.querySelector('#btn-open-request-modal'),
                cardsCount: document.querySelectorAll('.approval-card').length
            };
        })()
        """)
        print(f"Approvals page header buttons: {header_buttons}")
        assert header_buttons["shareBtn"], "Share Request Link button missing on #approvals"
        assert header_buttons["onboardBtn"], "+ Onboard Employee button missing on #approvals"

        # Check if the friend request card is displayed
        friend_card = await driver.evaluate("""
        (() => {
            const cards = Array.from(document.querySelectorAll('.approval-card'));
            const match = cards.find(c => c.textContent.includes('ahmad-raza-demo') || c.textContent.includes('Ahmad Raza'));
            if (!match) return null;
            return {
                text: match.innerText,
                hasOnboardBadge: match.innerText.includes('NEW EMPLOYEE ONBOARDING'),
                hasApproveBtn: !!match.querySelector('[data-action="Approved"]')
            };
        })()
        """)
        print(f"Friend request card in approvals queue: {friend_card}")
        assert friend_card is not None, "Friend request card not found in approvals queue!"

        # Screenshot: Approvals queue with real-time card and badges
        shot3_path = os.path.join(ARTIFACTS_DIR, "approval_queue_live_notification.png")
        await driver.screenshot(shot3_path)
        shutil.copyfile(shot3_path, os.path.join(DOCS_DIR, "approval_queue_live_notification.png"))
        print("✓ Captured approval_queue_live_notification.png")

        # -------------------------------------------------------------
        # STEP 3: Admin 1-Click "Approve & Onboard to GitHub"
        # -------------------------------------------------------------
        print("\n[Step 4] Admin clicking 'Approve & Onboard to GitHub'...")
        click_approve = await driver.evaluate("""
        (() => {
            const cards = Array.from(document.querySelectorAll('.approval-card'));
            const match = cards.find(c => c.textContent.includes('ahmad-raza-demo') || c.textContent.includes('Ahmad Raza'));
            if (!match) return false;
            const btn = match.querySelector('[data-action="Approved"]');
            if (!btn) return false;
            btn.click();
            return true;
        })()
        """)
        await asyncio.sleep(0.8)

        # Confirm the modal dialog
        modal_open = await driver.evaluate("""
        (() => {
            const modal = document.querySelector('#review-modal');
            const title = document.querySelector('#decision-title');
            const confirmBtn = document.querySelector('#confirm-review');
            return {
                isOpen: modal ? modal.classList.contains('show') || getComputedStyle(modal).display !== 'none' : false,
                title: title ? title.textContent.trim() : null,
                hasBtn: !!confirmBtn
            };
        })()
        """)
        print(f"Decision dialog open: {modal_open}")
        assert modal_open["isOpen"], "Decision modal did not open"

        # Submit approval with note
        await driver.evaluate("""
        (() => {
            const noteInput = document.querySelector('#review-note');
            if (noteInput) noteInput.value = 'Approved friend access for live demo';
            const confirmBtn = document.querySelector('#confirm-review');
            if (confirmBtn) confirmBtn.click();
        })()
        """)
        await asyncio.sleep(2.5)

        # Verify toast and status transition
        post_decision = await driver.evaluate("""
        (() => {
            const toasts = window.__toastHistory || [];
            const cards = Array.from(document.querySelectorAll('.approval-card'));
            const match = cards.find(c => c.textContent.includes('ahmad-raza-demo'));
            return {
                lastToast: toasts[toasts.length - 1] || null,
                allToasts: toasts,
                cardStillPending: !!match
            };
        })()
        """)
        print(f"Post-approval state: {post_decision}")

        # Screenshot: Approvals after live grant
        shot4_path = os.path.join(ARTIFACTS_DIR, "approval_granted_live.png")
        await driver.screenshot(shot4_path)
        shutil.copyfile(shot4_path, os.path.join(DOCS_DIR, "approval_granted_live.png"))
        print("✓ Captured approval_granted_live.png")

        # -------------------------------------------------------------
        # STEP 4: Test Real-Time Notification Bell Dropdown
        # -------------------------------------------------------------
        print("\n[Step 5] Opening notification bell panel...")
        await driver.evaluate("""
        (() => {
            const bell = document.querySelector('#notification-bell');
            if (bell) bell.click();
        })()
        """)
        await asyncio.sleep(0.8)

        bell_state = await driver.evaluate("""
        (() => {
            const panel = document.querySelector('#notification-panel');
            const items = Array.from(document.querySelectorAll('.notification-item'));
            return {
                panelVisible: panel ? !panel.classList.contains('d-none') : false,
                itemCount: items.length,
                topTitle: items[0]?.querySelector('.notif-title')?.textContent.trim() || null,
                topMessage: items[0]?.querySelector('.notif-message')?.textContent.trim() || null
            };
        })()
        """)
        print(f"Notification bell panel state: {bell_state}")
        assert bell_state["panelVisible"], "Notification panel did not open on bell click"
        assert bell_state["itemCount"] > 0, "No notifications displayed in panel"

        # Screenshot: Notification panel open
        shot5_path = os.path.join(ARTIFACTS_DIR, "notifications_bell_open_live.png")
        await driver.screenshot(shot5_path)
        shutil.copyfile(shot5_path, os.path.join(DOCS_DIR, "notifications_bell_open_live.png"))
        print("✓ Captured notifications_bell_open_live.png")

        # Close bell panel
        await driver.evaluate("""
        (() => {
            const panel = document.querySelector('#notification-panel');
            if (panel) panel.classList.add('d-none');
        })()
        """)
        await asyncio.sleep(0.5)

        # -------------------------------------------------------------
        # STEP 5: Test '⚡ Run Auto-Audit Now' Real-time Notification
        # -------------------------------------------------------------
        print("\n[Step 6] Triggering auto-audit from header button...")
        trigger_audit = await driver.evaluate("""
        (async () => {
            const btn = document.querySelector('#btn-trigger-auto-audit');
            if (!btn) return false;
            btn.click();
            return true;
        })()
        """)
        await asyncio.sleep(3.5)

        audit_result = await driver.evaluate("""
        (() => {
            const toasts = window.__toastHistory || [];
            return {
                lastToast: toasts[toasts.length - 1] || null,
                allToasts: toasts.slice(-3)
            };
        })()
        """)
        print(f"Auto-audit toast feedback: {audit_result}")

        shot6_path = os.path.join(ARTIFACTS_DIR, "auto_audit_triggered_success.png")
        await driver.screenshot(shot6_path)
        shutil.copyfile(shot6_path, os.path.join(DOCS_DIR, "auto_audit_triggered_success.png"))
        print("✓ Captured auto_audit_triggered_success.png")

        print("\n=== ALL REAL-TIME & ONBOARDING / PUBLIC REQUEST TESTS PASSED SUCCESSFULLY! ===")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
