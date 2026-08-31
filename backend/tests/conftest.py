"""Shared pytest fixtures: an in-memory SQLite test database and test client.

Smoke tests only for this build (no coverage gate) - happy path plus the
invalid-URL / too-long-video error paths, per PRPs/youtube-auto-editor-prp.md.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as app_main
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.routers import videos as videos_router


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    """Redirect uploads to a per-test temp dir instead of the real output/."""
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    # app.main.on_startup() and the pipeline's background-thread runner both
    # call SessionLocal() directly (outside any request, so neither can use
    # the Depends(get_db) override above) - without this, they'd hit the real
    # production database file instead of the in-memory test one.
    monkeypatch.setattr(app_main, "SessionLocal", TestSession)
    monkeypatch.setattr(videos_router, "SessionLocal", TestSession)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
