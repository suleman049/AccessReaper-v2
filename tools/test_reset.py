import sys
sys.path.insert(0, r"D:\AccessReaper-v2\backend")

from app.db.session import SessionLocal
from app.db.seed import seed_database
s = SessionLocal()
seed_database(s, reset_mode=True)
s.close()
print("Reset succeeded!")
