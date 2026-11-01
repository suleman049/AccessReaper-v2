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
    print("=== Verifying Live Real-Data UI State across All Sections ===")
    driver = BrowserDriver(headless=True)
    await driver.start()

    try:
        await driver.set_viewport(1280, 850)

        # -------------------------------------------------------------
        # STEP 1: Login Admin & Initialize Fresh Live State
        # -------------------------------------------------------------
        print("\n[Step 1] Visiting http://127.0.0.1:8100/ and authenticating...")
        await driver.navigate("http://127.0.0.1:8100/", wait_seconds=1.5)

        auth_res = await driver.evaluate("""
        (async () => {
            localStorage.clear();
            window.FirebaseIdentity.phase = 'authorized';
            window.FirebaseIdentity.user = { 
                uid: 'dev-admin-uid', 
                email: 'admin@payhive-eng.internal', 
                displayName: 'Security Admin', 
                getIdToken: async () => 'dev-token' 
            };
            window.FirebaseIdentity.profile = { 
                uid: 'dev-admin-uid', 
                email: 'admin@payhive-eng.internal', 
                name: 'Security Admin', 
                role: 'admin', 
                status: 'active', 
                organizationId: 'payhive-eng' 
            };
            window.FirebaseIdentity.notify();

            const data = await ApiClient.bootstrap();
            ApiClient.syncState(data);
            location.hash = 'dashboard';
            render();
            return {
                dataMode: data.dataMode,
                peopleCount: data.people.length,
                approvalsCount: data.approvals.length,
                runsCount: data.auditRuns.length
            };
        })()
        """)
        print(f"Auth & Bootstrap result: {auth_res}")
        await asyncio.sleep(1.2)

        # -------------------------------------------------------------
        # STEP 2: Dashboard Verification
        # -------------------------------------------------------------
        print("\n[Step 2] Verifying Dashboard (#dashboard)...")
        dash_info = await driver.evaluate("""
        (() => {
            const orgTitle = document.querySelector('.page-header h1, .brand-title, .brand-text')?.textContent || '';
            const cards = Array.from(document.querySelectorAll('.stat-card, .metric-card, .kpi-card')).map(c => c.innerText);
            const bodyText = document.body.innerText;
            return {
                orgTitle,
                cardsCount: cards.length,
                hasStubNames: bodyText.includes('Ahmad Raza') || bodyText.includes('Hamza Friend') || bodyText.includes('Test Submitter'),
                hasAcme: bodyText.includes('acme.io'),
                hasPayhive: bodyText.includes('payhive-eng')
            };
        })()
        """)
        print(f"Dashboard verification info: {dash_info}")
        assert not dash_info["hasStubNames"], "Stub names still found on Dashboard!"
        assert not dash_info["hasAcme"], "Legacy acme.io still found on Dashboard!"

        shot_dash = os.path.join(ARTIFACTS_DIR, "real_data_dashboard.png")
        await driver.screenshot(shot_dash)
        shutil.copyfile(shot_dash, os.path.join(DOCS_DIR, "real_data_dashboard.png"))
        print("✓ Captured real_data_dashboard.png")

        # -------------------------------------------------------------
        # STEP 3: Audit Findings Verification
        # -------------------------------------------------------------
        print("\n[Step 3] Verifying Audit findings (#audit)...")
        await driver.evaluate("""
        (() => {
            location.hash = 'audit';
            render();
        })()
        """)
        await asyncio.sleep(1.0)

        audit_info = await driver.evaluate("""
        (() => {
            const rows = Array.from(document.querySelectorAll('.assignment-row, tbody tr')).map(r => r.innerText);
            const bodyText = document.body.innerText;
            return {
                rowCount: rows.length,
                sampleRow: rows[0] ? rows[0].replace(/\\n+/g, ' | ') : null,
                hasStubNames: bodyText.includes('Ahmad Raza') || bodyText.includes('Hamza Friend') || bodyText.includes('Test Submitter'),
                hasAcme: bodyText.includes('acme.io') || bodyText.includes('acme/'),
                hasPayhive: bodyText.includes('payhive-eng')
            };
        })()
        """)
        print(f"Audit verification info: {audit_info}")
        assert not audit_info["hasStubNames"], "Stub names still found on Audit page!"
        assert not audit_info["hasAcme"], "Legacy acme.io still found on Audit page!"
        assert audit_info["hasPayhive"], "Expected payhive-eng findings not visible on Audit page!"

        shot_audit = os.path.join(ARTIFACTS_DIR, "real_data_audit.png")
        await driver.screenshot(shot_audit)
        shutil.copyfile(shot_audit, os.path.join(DOCS_DIR, "real_data_audit.png"))
        print("✓ Captured real_data_audit.png")

        # -------------------------------------------------------------
        # STEP 4: Approvals Queue Verification (Clean Queue, Real Actions)
        # -------------------------------------------------------------
        print("\n[Step 4] Verifying Approvals Decision Queue (#approvals)...")
        await driver.evaluate("""
        (() => {
            location.hash = 'approvals';
            render();
        })()
        """)
        await asyncio.sleep(1.0)

        approvals_info = await driver.evaluate("""
        (() => {
            const pendingCards = document.querySelectorAll('.request-card, .approval-card');
            const hasShareBtn = Array.from(document.querySelectorAll('button, a')).some(b => b.innerText.includes('Share Request Link'));
            const hasOnboardBtn = Array.from(document.querySelectorAll('button, a')).some(b => b.innerText.includes('Onboard Employee'));
            const bodyText = document.body.innerText;
            return {
                pendingCount: pendingCards.length,
                hasShareBtn,
                hasOnboardBtn,
                hasStubNames: bodyText.includes('Ahmad Raza') || bodyText.includes('Hamza Friend') || bodyText.includes('Test Submitter'),
                bodySnippet: bodyText.slice(0, 300).replace(/\\n+/g, ' ')
            };
        })()
        """)
        print(f"Approvals verification info: {approvals_info}")
        assert approvals_info["pendingCount"] == 0, f"Expected 0 pending requests, found {approvals_info['pendingCount']}"
        assert approvals_info["hasShareBtn"], "Missing 'Share Request Link' button on Approvals page!"
        assert approvals_info["hasOnboardBtn"], "Missing '+ Onboard Employee' button on Approvals page!"
        assert not approvals_info["hasStubNames"], "Stub names still found on Approvals page!"

        shot_approvals = os.path.join(ARTIFACTS_DIR, "real_data_approvals.png")
        await driver.screenshot(shot_approvals)
        shutil.copyfile(shot_approvals, os.path.join(DOCS_DIR, "real_data_approvals.png"))
        print("✓ Captured real_data_approvals.png")

        # -------------------------------------------------------------
        # STEP 5: Users / People Directory Verification
        # -------------------------------------------------------------
        print("\n[Step 5] Verifying Users / People Directory (#users)...")
        users_prep = await driver.evaluate("""
        (async () => {
            location.hash = 'users';
            if (window.UsersPage) {
                UsersPage.activeTab = 'people';
                await UsersPage.fetchPeople();
            }
            render();
            return {
                activeTab: UsersPage.activeTab,
                peopleCount: (UsersPage.people || []).length
            };
        })()
        """)
        print(f"Users prep result: {users_prep}")
        await asyncio.sleep(1.0)

        users_info = await driver.evaluate("""
        (() => {
            const rows = Array.from(document.querySelectorAll('table tbody tr')).map(r => r.innerText);
            const bodyText = document.body.innerText;
            return {
                rowCount: rows.length,
                firstFewUsers: rows.slice(0, 5).map(r => r.replace(/\\n+/g, ' | ').slice(0, 80)),
                hasStubNames: bodyText.includes('Ahmad Raza') || bodyText.includes('Hamza Friend') || bodyText.includes('Test Submitter'),
                hasAcme: bodyText.includes('acme.io'),
                hasRealMembers: bodyText.includes('Misbah Nisar') && bodyText.includes('Rasool Bux') && bodyText.includes('Saqib Anwar')
            };
        })()
        """)
        print(f"Users page verification info: {users_info}")
        assert not users_info["hasStubNames"], "Stub names still found in People directory!"
        assert not users_info["hasAcme"], "Legacy acme.io still found in People directory!"
        assert users_info["hasRealMembers"], "Expected real employees not found in People directory!"

        shot_people = os.path.join(ARTIFACTS_DIR, "real_data_people.png")
        await driver.screenshot(shot_people)
        shutil.copyfile(shot_people, os.path.join(DOCS_DIR, "real_data_people.png"))
        print("✓ Captured real_data_people.png")

        # -------------------------------------------------------------
        # STEP 6: Notification Center Dropdown
        # -------------------------------------------------------------
        print("\n[Step 6] Opening Notification Center Dropdown...")
        await driver.evaluate("""
        (() => {
            const bell = document.querySelector('#notif-bell-btn');
            if (bell) bell.click();
        })()
        """)
        await asyncio.sleep(0.8)

        notif_info = await driver.evaluate("""
        (() => {
            const dropdown = document.querySelector('#notif-dropdown');
            const items = Array.from(document.querySelectorAll('.notif-item')).map(i => i.innerText.replace(/\\n+/g, ' '));
            const bodyText = dropdown ? dropdown.innerText : '';
            return {
                isOpen: dropdown ? dropdown.classList.contains('show') || dropdown.style.display !== 'none' : false,
                itemsCount: items.length,
                sampleItem: items[0] || null,
                hasDemoStub: bodyText.includes('AUD-20261014-001') || bodyText.includes('NOTIF-DEMO') || bodyText.includes('Ahmad Raza')
            };
        })()
        """)
        print(f"Notifications dropdown info: {notif_info}")
        assert not notif_info["hasDemoStub"], "Demo stub notification found in notification dropdown!"

        shot_notifs = os.path.join(ARTIFACTS_DIR, "real_data_notifications.png")
        await driver.screenshot(shot_notifs)
        shutil.copyfile(shot_notifs, os.path.join(DOCS_DIR, "real_data_notifications.png"))
        print("✓ Captured real_data_notifications.png")

        # -------------------------------------------------------------
        # STEP 7: Public Self-Service Request Page (#request)
        # -------------------------------------------------------------
        print("\n[Step 7] Visiting Public Request Page (#request)...")
        await driver.navigate("http://127.0.0.1:8100/#request", wait_seconds=1.0)
        public_req_info = await driver.evaluate("""
        (() => {
            const repoSelect = document.querySelector('#pub-repo-select');
            const options = repoSelect ? Array.from(repoSelect.options).map(o => o.value) : [];
            return {
                optionsCount: options.length,
                repos: options,
                allPayhive: options.every(o => o.startsWith('payhive-eng/')),
                hasCoreApi: options.includes('payhive-eng/core-api')
            };
        })()
        """)
        print(f"Public request repo options: {public_req_info}")
        assert public_req_info["allPayhive"], "Not all repositories in dropdown are payhive-eng!"
        assert not public_req_info["hasCoreApi"], "Removed core-api is unexpectedly still in repository list!"

        shot_pub = os.path.join(ARTIFACTS_DIR, "real_data_public_request.png")
        await driver.screenshot(shot_pub)
        shutil.copyfile(shot_pub, os.path.join(DOCS_DIR, "real_data_public_request.png"))
        print("✓ Captured real_data_public_request.png")

        print("\n=== ALL REAL-DATA VERIFICATIONS PASSED SUCCESSFULLY! ===")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
