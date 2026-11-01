import sqlite3

con = sqlite3.connect(r'D:\AccessReaper-v2\backend\data\accessreaper_v2.db')
cur = con.cursor()

def dump_table(name, limit=10):
    col_info = cur.execute(f"PRAGMA table_info({name})").fetchall()
    cols = [c[1] for c in col_info]
    print(f"\n--- {name} (cols: {cols}) ---")
    rows = cur.execute(f"SELECT * FROM {name} LIMIT {limit}").fetchall()
    for r in rows:
        print(dict(zip(cols, r)))

dump_table('identities', 20)
dump_table('access_requests', 30)
dump_table('assignments', 5)
dump_table('github_configs', 5)
dump_table('sync_runs', 5)
dump_table('github_identity_map', 20)
dump_table('findings', 5)
dump_table('settings', 10)
