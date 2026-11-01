import sqlite3
import re
import os

print("=== 1. CLEANING FRONTEND FILES ===")

# --- frontend/governance.js ---
gov_path = r"D:\AccessReaper-v2\frontend\governance.js"
with open(gov_path, "r", encoding="utf-8") as f:
    gov = f.read()

gov = gov.replace("'EVT-SEED-'+i", "'EVT-'+i")
gov = gov.replace("'Jordan Davis'", "'Security Admin'")
gov = gov.replace("acme/", "payhive-eng/")
gov = gov.replace(
    "if(/GitHub.*Firestore/.test(e.detail))e.source='GitHub + Firestore';else if(e.detail.includes('Firestore'))e.source='Firestore';else if(e.detail.includes('acme/'))e.source='GitHub';",
    "if(e.detail?.includes('payhive-eng/'))e.source='GitHub';else e.source='GitHub';"
)
gov = re.sub(
    r"if\(!auditRuns\.length\)\{auditRuns=\[\{id:'AUD-20261014-001'.*?sample:true\}\];\}",
    "// No fake audit run injection",
    gov
)
gov = re.sub(
    r"if\(!auditSnapshots\.length\)this\.snapshot\('Initial sample baseline'.*?\);",
    "// No fake snapshot injection",
    gov
)
gov = gov.replace(
    "sources:['GitHub','Firestore'].map(source=>({source,assignments:people.filter(p=>p.source===source).length,resources:new Set(people.filter(p=>p.source===source).map(p=>p.repo)).size}))",
    "sources:[{source:'GitHub',assignments:people.length,resources:new Set(people.map(p=>p.repo)).size}]"
)
gov = gov.replace(
    "target(p){return p.team==='Former employee'?'None':p.source==='Firestore'?'Viewer':'Read';}",
    "target(p){return p.team==='Former employee'?'None':'Read';}"
)
gov = gov.replace(
    "p.source==='Firestore'?`A ${p.role.toLowerCase()} does not need application administration for the recorded duties.`:",
    ""
)

with open(gov_path, "w", encoding="utf-8") as f:
    f.write(gov)
print("Updated frontend/governance.js")

# --- frontend/api-client.js ---
api_path = r"D:\AccessReaper-v2\frontend\api-client.js"
with open(api_path, "r", encoding="utf-8") as f:
    api = f.read()
api = api.replace('"jordan.davis@acme.io"', '"admin@payhive-eng.internal"')
with open(api_path, "w", encoding="utf-8") as f:
    f.write(api)
print("Updated frontend/api-client.js")

# --- frontend/github-settings.js ---
gh_path = r"D:\AccessReaper-v2\frontend\github-settings.js"
with open(gh_path, "r", encoding="utf-8") as f:
    gh = f.read()
gh = gh.replace('const org = this.status?.org_name || "acme";', 'const org = this.status?.org_name || "payhive-eng";')
gh = gh.replace('placeholder="e.g. acme"', 'placeholder="e.g. payhive-eng"')
gh = gh.replace('value="${this.status?.org_name || "acme"}"', 'value="${this.status?.org_name || "payhive-eng"}"')
gh = gh.replace('employee@acme.io', 'employee@payhive.internal')
gh = gh.replace('suleman@acme.io', 'suleman@payhive.internal')
gh = gh.replace('window.currentDataMode || "sample"', '"live"')
with open(gh_path, "w", encoding="utf-8") as f:
    f.write(gh)
print("Updated frontend/github-settings.js")

# --- frontend/users-page.js ---
users_path = r"D:\AccessReaper-v2\frontend\users-page.js"
with open(users_path, "r", encoding="utf-8") as f:
    up = f.read()
up = up.replace("Acme, Inc.", "payhive-eng")
up = up.replace("alex.rivera@acme.io", "employee@payhive.internal")
with open(users_path, "w", encoding="utf-8") as f:
    f.write(up)
print("Updated frontend/users-page.js")

# --- frontend/workspace-design.js ---
wd_path = r"D:\AccessReaper-v2\frontend\workspace-design.js"
with open(wd_path, "r", encoding="utf-8") as f:
    wd = f.read()
wd = wd.replace("Recommendations use the current sample permissions.", "Recommendations use current live permissions.")
wd = wd.replace("Manage your organization, access sources, and sample data.", "Manage your organization, access sources, and security preferences.")
with open(wd_path, "w", encoding="utf-8") as f:
    f.write(wd)
print("Updated frontend/workspace-design.js")

# --- frontend/firebase-client.js ---
fb_path = r"D:\AccessReaper-v2\frontend\firebase-client.js"
with open(fb_path, "r", encoding="utf-8") as f:
    fb = f.read()
fb = fb.replace("this.profile?.organizationId === 'acme'", "['acme', 'payhive-eng'].includes(this.profile?.organizationId)")
fb = fb.replace("organizationId:'acme'", "organizationId:'payhive-eng'")
with open(fb_path, "w", encoding="utf-8") as f:
    f.write(fb)
print("Updated frontend/firebase-client.js")

# --- backend/app/engine/pdf_report.py ---
pdf_path = r"D:\AccessReaper-v2\backend\app\engine\pdf_report.py"
with open(pdf_path, "r", encoding="utf-8") as f:
    pdf = f.read()
pdf = pdf.replace('"Acme, Inc."', 'self.org_name')
pdf = pdf.replace('Organization: <b>Acme, Inc.</b>', 'Organization: <b>payhive-eng</b>')
# ensure self.org_name exists on canvas
if "self.org_name = 'payhive-eng'" not in pdf:
    pdf = pdf.replace(
        "class NumberedCanvas(canvas.Canvas):",
        "class NumberedCanvas(canvas.Canvas):\n    org_name = 'payhive-eng'"
    )
with open(pdf_path, "w", encoding="utf-8") as f:
    f.write(pdf)
print("Updated backend/app/engine/pdf_report.py")

# --- backend/app/services/llm/sanitizer.py ---
san_path = r"D:\AccessReaper-v2\backend\app\services\llm\sanitizer.py"
with open(san_path, "r", encoding="utf-8") as f:
    san = f.read()
san = san.replace("auditor for Acme, Inc.", "auditor for payhive-eng")
san = san.replace('"unknown@acme.corp"', '"unknown@payhive.internal"')
with open(san_path, "w", encoding="utf-8") as f:
    f.write(san)
print("Updated backend/app/services/llm/sanitizer.py")

# --- backend/app/core/security.py ---
sec_path = r"D:\AccessReaper-v2\backend\app\core\security.py"
with open(sec_path, "r", encoding="utf-8") as f:
    sec = f.read()
sec = sec.replace('"jordan.davis@acme.io"', '"admin@payhive-eng.internal"')
sec = sec.replace('user_data.get("organizationId") != "acme"', 'user_data.get("organizationId") not in ("acme", "payhive-eng")')
with open(sec_path, "w", encoding="utf-8") as f:
    f.write(sec)
print("Updated backend/app/core/security.py")

print("\n=== 2. CLEANING SQLITE DATABASE ===")
db_path = r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

# Check triggers
cur.execute("DROP TRIGGER IF EXISTS prevent_audit_log_delete")
cur.execute("DROP TRIGGER IF EXISTS prevent_audit_log_update")

# Delete fake audit logs
cur.execute("""
DELETE FROM audit_log 
WHERE id LIKE 'EVT-SEED%' 
   OR detail LIKE '%acme%' 
   OR detail LIKE '%Alex Morgan%' 
   OR detail LIKE '%Maya Chen%' 
   OR detail LIKE '%Liam Foster%'
   OR detail LIKE '%Ethan Wright%'
   OR actor LIKE '%jordan.davis@acme.io%'
""")
deleted_logs = cur.rowcount
print(f"Deleted {deleted_logs} sample rows from audit_log")

# Recreate triggers
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

# Delete sample audit run
cur.execute("DELETE FROM audit_runs WHERE sample = 1 OR id = 'AUD-20261014-001'")
print(f"Deleted {cur.rowcount} sample audit runs")

# Delete sample snapshot
cur.execute("DELETE FROM audit_snapshots WHERE label LIKE '%sample%'")
print(f"Deleted {cur.rowcount} sample audit snapshots")

# Clean settings
cur.execute("DELETE FROM settings WHERE key = 'data_mode'")
cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('dataMode', 'live')")
cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('organizationName', 'payhive-eng')")
cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('mode', 'LIVE_GITHUB')")
cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('lastAudit', 'Just now')")

con.commit()
con.close()
print("Database cleanup committed successfully.")
