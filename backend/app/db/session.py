"""
Database session and connection management for AccessReaper v2.
Enforces SQLite foreign keys and append-only database triggers on audit_log.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

# Connect args for SQLite to allow multi-threading in FastAPI
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces SQLite foreign keys, WAL mode, and busy timeout on every connection."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA cache_size=-10000;")
        except Exception:
            pass
        cursor.close()


def setup_immutability_triggers(engine_or_conn):
    """
    Creates DB-level SQLite triggers to guarantee that audit_log is strictly append-only.
    Any attempt to UPDATE or DELETE an audit log record will fail at the SQLite engine level.
    """
    triggers_sql = [
        """
        CREATE TRIGGER IF NOT EXISTS prevent_audit_log_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(FAIL, 'audit_log is append-only: UPDATE is prohibited');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS prevent_audit_log_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(FAIL, 'audit_log is append-only: DELETE is prohibited');
        END;
        """,
    ]
    with engine.begin() as conn:
        for sql in triggers_sql:
            conn.exec_driver_sql(sql)


def init_db():
    """Initializes schema and triggers, adding any missing automation columns safely."""
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        setup_immutability_triggers(engine)

    # Automatically add new automation columns if not present
    new_cols = [
        ("assignments", "expires_at", "DATETIME"),
        ("assignments", "is_temporary", "BOOLEAN DEFAULT 0"),
        ("assignments", "warning_email_sent_at", "DATETIME"),
        ("access_requests", "duration_hours", "INTEGER"),
        ("access_requests", "expires_at", "DATETIME"),
    ]
    with engine.begin() as conn:
        for table, col, col_type in new_cols:
            try:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
            except Exception:
                pass  # Column already exists


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
