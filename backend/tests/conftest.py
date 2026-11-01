"""
Test configuration and fixtures for AccessReaper v2.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base
from app.db.seed import seed_database
from app.db.session import get_db, setup_immutability_triggers
from app.main import app

# Set test environment
settings.ENV = "dev"
settings.AUTH_MODE = "dev"
settings.HOST = "127.0.0.1"
settings.ALLOW_MANUAL_AUDIT = True
settings.MUTATING_RATE_LIMIT_PER_MINUTE = 1000

# Use in-memory or dedicated test SQLite database
TEST_DB_URL = "sqlite:///D:/AccessReaper-v2/backend/data/test_accessreaper_v2.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    setup_immutability_triggers(test_engine)
    with TestingSessionLocal() as db:
        seed_database(db, reset_mode=True)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8100")


@pytest.fixture
def auth_headers() -> dict:
    return {"X-Dev-User": "jordan.davis@acme.io"}
