"""Pytest fixtures: isolated in-memory database + demo-seeded TestClient.

Every test gets a freshly rebuilt, re-seeded database so cases are independent.
"""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SEED_ON_STARTUP"] = "false"  # fixtures seed explicitly

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, main as main_mod, models
from app.database import get_db
from app.main import app
from app.seed import seed_demo


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


@pytest.fixture()
def session_factory():
    engine = _make_engine()
    factory = sessionmaker(bind=engine, future=True)
    # repoint every module-level binding the app uses
    database.engine = engine
    database.SessionLocal = factory
    main_mod.engine = engine
    main_mod.SessionLocal = factory

    def _override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    models.Base.metadata.create_all(bind=engine)
    db = factory()
    seed_demo(db)
    db.close()
    yield factory
    app.dependency_overrides.clear()
    models.Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# --- demo-data lookup helpers ----------------------------------------------

@pytest.fixture()
def pipe_by_code(db):
    from app import models
    cache = {p.code: p for p in db.query(models.Pipe).all()}

    def _find(code):
        return cache[code]

    return _find


@pytest.fixture()
def node_by_code(db):
    from app import models
    cache = {n.code: n for n in db.query(models.NetworkNode).all()}

    def _find(code):
        return cache[code]

    return _find


@pytest.fixture()
def team_by_name(db):
    from app import models
    cache = {t.name: t for t in db.query(models.RepairTeam).all()}

    def _find(name):
        return cache[name]

    return _find
