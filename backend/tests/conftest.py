import os
import tempfile

import pytest

# Point the app at an isolated SQLite file BEFORE importing the app modules.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["WATER_DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["WATER_SEED_ON_STARTUP"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_database():
    """Each test gets a freshly seeded schema (fast on SQLite)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.database import SessionLocal
    from app.seed import seed

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield
