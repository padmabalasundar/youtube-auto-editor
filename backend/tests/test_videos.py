"""Smoke tests for the videos API.

Covers the happy path plus the bad-extension / too-long-video / not-found /
retry error paths. The real pipeline (Whisper, ffmpeg) is mocked out - these
tests verify routing/DB wiring and upload handling, not the pipeline itself.
"""
from app.models.video import Video, VideoStatus
from app.services import pipeline_service


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_videos_empty(client):
    response = client.get("/api/videos")
    assert response.status_code == 200
    assert response.json() == []


def test_create_video_rejects_bad_extension(client):
    response = client.post(
        "/api/videos", files={"file": ("notes.txt", b"not a video", "text/plain")}
    )
    assert response.status_code == 400


def test_create_video_too_long(client, monkeypatch):
    monkeypatch.setattr(pipeline_service, "probe_duration_seconds", lambda _path: 5000.0)

    response = client.post(
        "/api/videos", files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
    )
    assert response.status_code == 400


def test_create_video_success(client, monkeypatch):
    def fake_run_pipeline(db, video: Video, source_path: str) -> None:
        video.status = VideoStatus.DONE
        video.language = "ta"
        db.commit()

    monkeypatch.setattr(pipeline_service, "probe_duration_seconds", lambda _path: 120.0)
    monkeypatch.setattr(pipeline_service, "run_pipeline", fake_run_pipeline)

    response = client.post(
        "/api/videos", files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "clip.mp4"
    assert body["status"] == "done"
    assert body["clips"] == []


def test_get_video_not_found(client):
    response = client.get("/api/videos/9999")
    assert response.status_code == 404


def test_retry_video_not_found(client):
    response = client.post("/api/videos/9999/retry")
    assert response.status_code == 404


def test_retry_video_missing_source_file(client, monkeypatch):
    monkeypatch.setattr(pipeline_service, "probe_duration_seconds", lambda _path: 120.0)
    monkeypatch.setattr(
        pipeline_service, "run_pipeline", lambda db, video, source_path: None
    )
    created = client.post(
        "/api/videos", files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
    ).json()

    # The upload's source file exists on disk, so simulate it having been
    # removed (e.g. output/ cleaned up) by pointing find_source_file at "gone".
    monkeypatch.setattr(pipeline_service, "find_source_file", lambda _output_dir, _key: None)

    response = client.post(f"/api/videos/{created['id']}/retry")
    assert response.status_code == 400
