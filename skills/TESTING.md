# Testing Skill

> pytest smoke tests only - no coverage gate, no frontend test runner set up

This build tests routing/DB wiring and error paths, not the real pipeline -
Whisper transcription, `yt-dlp` downloads, and `ffmpeg` cutting are always
mocked out via `monkeypatch`. There's no `pytest-asyncio` need (routes are
sync `def`s over a thread-based background pipeline, not `async def`), and
no Vitest/Testing Library installed on the frontend yet.

---

## Backend Fixtures

```python
# tests/conftest.py
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    """Redirect uploads to a per-test temp dir instead of the real output/."""
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

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
    # main.on_startup() and the pipeline's background thread both call
    # SessionLocal() directly (outside any request) - patch both modules'
    # reference so they hit the in-memory test DB too, not the real app.db.
    monkeypatch.setattr(app_main, "SessionLocal", TestSession)
    monkeypatch.setattr(videos_router, "SessionLocal", TestSession)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

---

## API Test Pattern

Mock the pipeline at the `pipeline_service` module boundary, not FastAPI's
routing - this tests the actual save/probe/limit/thread-start logic in
`routers/videos.py` while keeping tests near-instant:

```python
# tests/test_videos.py
def _wait_for_status(client, video_id: int, *, timeout_seconds: float = 2.0) -> dict:
    """Poll a video until its pipeline (a background thread) leaves pending/processing."""
    deadline = time.monotonic() + timeout_seconds
    body = client.get(f"/api/videos/{video_id}").json()
    while body["status"] in ("pending", "processing") and time.monotonic() < deadline:
        time.sleep(0.02)
        body = client.get(f"/api/videos/{video_id}").json()
    return body

def test_create_video_too_long(client, monkeypatch):
    monkeypatch.setattr(pipeline_service, "probe_duration_seconds", lambda _path: 5000.0)
    response = client.post("/api/videos", files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")})
    assert response.status_code == 400

def test_create_video_success(client, monkeypatch):
    def fake_run_pipeline(db, video, source_path, duration_seconds) -> None:
        video.status = VideoStatus.DONE
        db.commit()

    monkeypatch.setattr(pipeline_service, "probe_duration_seconds", lambda _path: 120.0)
    monkeypatch.setattr(pipeline_service, "run_pipeline", fake_run_pipeline)

    response = client.post("/api/videos", files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"   # returns before the (fake) pipeline finishes
    assert _wait_for_status(client, response.json()["id"])["status"] == "done"
```

The YouTube-URL path mocks one level deeper - `probe_youtube_metadata` and
`download_youtube_video` - so tests never hit the network:

```python
def test_create_video_from_url_too_long(client, monkeypatch):
    monkeypatch.setattr(pipeline_service, "probe_youtube_metadata", lambda _url: (5000.0, "A long video"))
    response = client.post("/api/videos/from-url", json={"url": "https://youtu.be/abc123"})
    assert response.status_code == 400
```

---

## Run Tests

```bash
# Backend
cd backend
pytest -v
ruff check backend/

# Frontend (no test runner configured - these are the checks that exist)
cd frontend
npm run lint         # oxlint
npx tsc -b --noEmit  # type-check
npm run build        # also catches type errors, verifies the production bundle
```

---

## Best Practices (this build)

- Smoke tests only - happy path plus the real error paths (bad extension, too long, not found, missing source file on retry). No 80% coverage gate.
- Mock at the `pipeline_service` function boundary (`probe_duration_seconds`, `run_pipeline`, `probe_youtube_metadata`, `download_youtube_video`), not deeper - keeps tests fast and decoupled from Whisper/ffmpeg/yt-dlp actually being installed correctly in CI.
- `_isolated_output_dir` is `autouse=True` - every test gets a throwaway `OUTPUT_DIR`, so nothing writes into the real `output/` during a test run.
- No frontend component/hook tests exist yet. If you add real UI test coverage, install `vitest` + `@testing-library/react` first - don't assume they're already wired up.
