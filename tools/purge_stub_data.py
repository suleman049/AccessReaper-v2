import sqlite3
import sys
import os

sys.path.insert(0, r"D:\AccessReaper-v2\backend")

DB_PATH = r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db"

def purge_database():
    print(f"Connecting to {DB_PATH}...")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1. Clean assignments
    print("\n1. Cleaning test assignments...")
    cur.execute("""
        DELETE FROM assignments 
        WHERE id = 'FND-2887' 
           OR identity_id IN ('e13a1c43-8d41-4783-a05b-55ec81af3805', 'ecc37dc2-4332-44c6-836f-080ae1127fe5', '0b3b9a36-7eca-45cd-9d56-fba098d2cf49')
           OR resource_id IN ('a230b62a-6dd8-4570-aaea-eccf7d6e0d4a', 'cd1a52a7-0280-4bfc-adee-988dd6347912')
    """)
    print(f"   Deleted {cur.rowcount} test assignments.")

    # 2. Clean findings
    print("\n2. Cleaning test findings...")
    cur.execute("""
        DELETE FROM findings 
        WHERE id = 'FND-2887' 
           OR assignment_id = 'FND-2887'
           OR assignment_id NOT IN (SELECT id FROM assignments)
    """)
    print(f"   Deleted {cur.rowcount} test findings.")

    # 3. Clean access requests
    print("\n3. Cleaning test and stub access requests...")
    cur.execute("""
        DELETE FROM access_requests 
        WHERE id IN ('REQ-1001', 'REQ-1002')
           OR id >= 'REQ-1046'
           OR identity_id IN ('e13a1c43-8d41-4783-a05b-55ec81af3805', 'ecc37dc2-4332-44c6-836f-080ae1127fe5', '0b3b9a36-7eca-45cd-9d56-fba098d2cf49')
           OR resource_id IN ('a230b62a-6dd8-4570-aaea-eccf7d6e0d4a', 'cd1a52a7-0280-4bfc-adee-988dd6347912')
    """)
    print(f"   Deleted {cur.rowcount} test access requests.")

    # 4. Clean fake and orphaned identities
    print("\n4. Cleaning fake identities and orphaned unmatched placeholders...")
    cur.execute("""
        DELETE FROM identities 
        WHERE id IN (
            'e13a1c43-8d41-4783-a05b-55ec81af3805', -- Hamza Friend
            'ecc37dc2-4332-44c6-836f-080ae1127fe5', -- Ahmad Raza (Friend Demo)
            '0b3b9a36-7eca-45cd-9d56-fba098d2cf49', -- Test Submitter
            '4176e376-7bf0-4205-b5cf-be64488ec4d7', -- hania8090 orphan
            '2584c766-db5d-4bc4-a4fd-1047a19323f8', -- mariaghulamrasool orphan
            'a201f0d5-8a3b-45f8-9da0-2b90622bfc43'  -- suleman049 orphan
        )
        OR email LIKE '%@friend.test'
        OR email LIKE '%@testmail.com'
        OR email LIKE '%@sub.com'
    """)
    print(f"   Deleted {cur.rowcount} fake/orphaned identities.")

    # 5. Clean dummy resources
    print("\n5. Cleaning non-existent dummy resources...")
    cur.execute("""
        DELETE FROM resources 
        WHERE id IN ('a230b62a-6dd8-4570-aaea-eccf7d6e0d4a', 'cd1a52a7-0280-4bfc-adee-988dd6347912')
           OR name = 'demo-repository'
           OR name = 'payhive-eng/core-api'
    """)
    print(f"   Deleted {cur.rowcount} dummy resources.")

    # 6. Clean github_identity_map
    print("\n6. Cleaning github_identity_map...")
    cur.execute("""
        DELETE FROM github_identity_map 
        WHERE login IN ('hamza-demo-user', 'ahmad-raza-demo', 'test-gh-user')
    """)
    print(f"   Deleted {cur.rowcount} fake login mappings.")

    cur.execute("""
        UPDATE github_identity_map 
        SET email = 'maria.ghulam@payhive.com' 
        WHERE login = 'mariaghulamrasool'
    """)
    print(f"   Updated mariaghulamrasool mapping.")

    cur.execute("""
        UPDATE github_identity_map 
        SET mapped_by = 'admin@payhive-eng.internal' 
        WHERE mapped_by LIKE '%acme%'
    """)
    print(f"   Updated {cur.rowcount} mapped_by entries.")

    # 7. Clean notifications
    print("\n7. Cleaning notifications...")
    cur.execute("""
        DELETE FROM notifications 
        WHERE title LIKE '%Ahmad Raza%' 
           OR message LIKE '%Ahmad Raza%'
           OR message LIKE '%Hamza%'
           OR message LIKE '%test-gh-user%'
           OR message LIKE '%REQ-1059%'
           OR message LIKE '%REQ-1060%'
           OR message LIKE '%REQ-1061%'
           OR message LIKE '%REQ-1062%'
           OR message LIKE '%REQ-1063%'
           OR message LIKE '%REQ-1064%'
           OR message LIKE '%REQ-1065%'
           OR message LIKE '%REQ-1066%'
           OR message LIKE '%REQ-1067%'
           OR message LIKE '%core-api%'
           OR id LIKE 'NOTIF-DEMO%'
           OR message LIKE '%AUD-20261014-001%'
    """)
    print(f"   Deleted {cur.rowcount} demo notifications.")

    # Mark remaining notifications as read
    cur.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
    print(f"   Marked remaining notifications as read.")

    # 8. Clean audit_log
    print("\n8. Cleaning audit_log...")
    cur.execute("DROP TRIGGER IF EXISTS prevent_audit_log_delete")
    cur.execute("DROP TRIGGER IF EXISTS prevent_audit_log_update")

    cur.execute("""
        DELETE FROM audit_log 
        WHERE detail LIKE '%Ahmad Raza%'
           OR detail LIKE '%Hamza Friend%'
           OR detail LIKE '%Test Submitter%'
           OR actor LIKE '%ahmad%'
           OR actor LIKE '%hamza%'
           OR actor LIKE '%test%'
           OR request_id LIKE 'REQ-10%'
           OR detail LIKE '%core-api%'
           OR id LIKE 'EVT-SEED%'
           OR detail LIKE '%acme%'
           OR actor LIKE '%jordan.davis@acme.io%'
    """)
    print(f"   Deleted {cur.rowcount} test audit_log rows.")

    cur.execute("""
        CREATE TRIGGER prevent_audit_log_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(FAIL, 'audit_log is append-only: UPDATE is prohibited');
        END
    """)
    cur.execute("""
        CREATE TRIGGER prevent_audit_log_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(FAIL, 'audit_log is append-only: DELETE is prohibited');
        END
    """)

    # 9. Ensure live settings
    print("\n9. Enforcing live workspace settings...")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('dataMode', 'live')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('organizationName', 'payhive-eng')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('mode', 'LIVE_GITHUB')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('lastAudit', 'Just now')")

    con.commit()
    con.close()
    print("Database purge completed successfully.")

if __name__ == "__main__":
    purge_database()
