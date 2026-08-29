"""Smoke tests for the videos API.

Covers the happy path plus the invalid-URL / too-long-video / not-found error
paths. The real pipeline (yt-dlp download, transcript, LLM call, ffmpeg) is
mocked out - these tests verify routing/DB wiring, not the pipeline itself.
"""
from app.exceptions import ValidationError
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


def test_create_video_invalid_url(client, monkeypatch):
    def fake_extract(_url: str):
        raise ValidationError("Invalid YouTube URL")

    monkeypatch.setattr(pipeline_service, "extract_video_metadata", fake_extract)

    response = client.post("/api/videos", json={"youtube_url": "not-a-youtube-url"})
    assert response.status_code == 400


def test_create_video_too_long(client, monkeypatch):
    def fake_extract(_url: str):
        raise ValidationError("Video exceeds the 30-minute limit")

    monkeypatch.setattr(pipeline_service, "extract_video_metadata", fake_extract)

    response = client.post("/api/videos", json={"youtube_url": "https://youtube.com/watch?v=long"})
    assert response.status_code == 400


def test_create_video_success(client, monkeypatch):
    def fake_extract(_url: str):
        return {"youtube_id": "abc123", "title": "Test Video", "duration": 120.0}

    def fake_run_pipeline(db, video: Video) -> None:
        video.status = VideoStatus.DONE
        video.language = "en"
        db.commit()

    monkeypatch.setattr(pipeline_service, "extract_video_metadata", fake_extract)
    monkeypatch.setattr(pipeline_service, "run_pipeline", fake_run_pipeline)

    response = client.post("/api/videos", json={"youtube_url": "https://youtube.com/watch?v=abc123"})
    assert response.status_code == 201
    body = response.json()
    assert body["youtube_id"] == "abc123"
    assert body["status"] == "done"
    assert body["clips"] == []


def test_get_video_not_found(client):
    response = client.get("/api/videos/9999")
    assert response.status_code == 404
