import sqlite3

con = sqlite3.connect(r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db")
print("Total rows in audit_log:", con.execute("SELECT count(*) FROM audit_log").fetchone()[0])
print("Remaining audit_runs:", con.execute("SELECT id, status, sources, sample FROM audit_runs").fetchall())
print("Remaining audit_snapshots:", con.execute("SELECT count(*) FROM audit_snapshots").fetchone()[0])
print("Sample snapshots:", con.execute("SELECT id, at, label FROM audit_snapshots WHERE label LIKE '%sample%'").fetchall())
print("ACME anywhere in audit_log:", con.execute("SELECT count(*) FROM audit_log WHERE detail LIKE '%acme%' OR title LIKE '%acme%' OR actor LIKE '%acme%'").fetchone()[0])
print("Settings:", con.execute("SELECT key, value FROM settings").fetchall())
print("Total assignments:", con.execute("SELECT count(*) FROM assignments").fetchone()[0])
print("Assignments by origin:", con.execute("SELECT origin, count(*) FROM assignments GROUP BY origin").fetchall())
print("Total identities:", con.execute("SELECT count(*) FROM identities").fetchone()[0])
print("Total resources:", con.execute("SELECT count(*) FROM resources").fetchone()[0])
print("Resources by source:", con.execute("SELECT source, count(*) FROM resources GROUP BY source").fetchall())






