import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"D:\AccessReaper-v2\backend\data\accessreaper_v2.db")
rows = c.execute(
    "SELECT id, actor, tag, title, detail, occurred_at FROM audit_log WHERE actor LIKE '%Auto-Pilot%' ORDER BY occurred_at DESC LIMIT 5"
).fetchall()
for r in rows:
    print(r)
