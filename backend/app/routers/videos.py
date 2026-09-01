"""Video upload and retrieval endpoints."""
import logging
import os
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import get_db
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoResponse
from app.services import pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


class VideoUrlRequest(BaseModel):
    """Body for POST /videos/from-url."""

    url: str


def _save_upload(file: UploadFile, output_dir: str, source_path: str) -> None:
    """Stream the upload to disk, enforcing MAX_UPLOAD_BYTES; cleans up on failure."""
    size = 0
    try:
        with open(source_path, "wb") as f:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > pipeline_service.MAX_UPLOAD_BYTES:
                    limit_mb = pipeline_service.MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise HTTPException(400, f"File exceeds the {limit_mb}MB limit")
                f.write(chunk)
    except HTTPException:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    finally:
        file.file.close()


def _run_pipeline_in_background(video_id: int, source_path: str, duration_seconds: float) -> None:
    """Run the pipeline for `video_id` on its own thread with its own DB session.

    The request's `db` session (from `Depends(get_db)`) closes as soon as the
    response is sent, so this thread can't reuse it - it opens a fresh
    `SessionLocal()` and re-fetches the row instead. Run as a plain daemon
    thread rather than a FastAPI `BackgroundTask`: that keeps a many-minutes
    Whisper/ffmpeg run fully off Starlette's request threadpool, so it can
    never compete with (or get starved by) other concurrent requests.
    """
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if video is None:
            return
        pipeline_service.run_pipeline(db, video, source_path, duration_seconds)
    finally:
        db.close()


def _create_video_and_start_pipeline(
    db: Session,
    *,
    original_filename: str,
    storage_key: str,
    title: str | None,
    source_path: str,
    duration_seconds: float,
) -> Video:
    """Persist a new `Video` row (status "pending") and kick off its pipeline thread.

    Shared by both input paths (file upload and YouTube URL) once each has
    produced a `source.<ext>` file on disk and knows its duration.
    """
    video = Video(
        original_filename=original_filename,
        storage_key=storage_key,
        title=title,
        status=VideoStatus.PENDING,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    threading.Thread(
        target=_run_pipeline_in_background,
        args=(video.id, source_path, duration_seconds),
        daemon=True,
    ).start()

    return video


@router.post("", response_model=VideoResponse, status_code=201)
def create_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Video:
    """Upload a video file, then kick off clip generation in the background.

    Returns as soon as the file is saved and the `Video` row is created
    (status "pending") - the actual pipeline (Whisper transcription, ffmpeg
    cutting) runs on a background thread and can take several minutes. The
    frontend polls `GET /videos/{id}` for live status/progress instead of
    waiting on this request.
    """
    original_filename = file.filename or "upload"
    ext = Path(original_filename).suffix.lower()
    if ext not in pipeline_service.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(pipeline_service.ALLOWED_EXTENSIONS))
        raise HTTPException(400, f"Unsupported file type '{ext or '(none)'}'. Allowed: {allowed}")

    storage_key = uuid.uuid4().hex[:12]
    output_dir = os.path.join(settings.OUTPUT_DIR, storage_key)
    os.makedirs(output_dir, exist_ok=True)
    source_path = os.path.join(output_dir, f"source{ext}")

    _save_upload(file, output_dir, source_path)

    try:
        duration = pipeline_service.probe_duration_seconds(source_path)
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(400, "Could not read this file as a video.") from e

    if duration > settings.MAX_VIDEO_DURATION_SECONDS:
        shutil.rmtree(output_dir, ignore_errors=True)
        limit_minutes = settings.MAX_VIDEO_DURATION_SECONDS // 60
        raise HTTPException(400, f"Video exceeds the {limit_minutes}-minute limit")

    return _create_video_and_start_pipeline(
        db,
        original_filename=original_filename,
        storage_key=storage_key,
        title=Path(original_filename).stem,
        source_path=source_path,
        duration_seconds=duration,
    )


@router.post("/from-url", response_model=VideoResponse, status_code=201)
def create_video_from_url(payload: VideoUrlRequest, db: Session = Depends(get_db)) -> Video:
    """Download a YouTube video by URL, then kick off clip generation exactly like an upload.

    Duration is checked against the same limit as uploads before anything is
    downloaded, using yt-dlp's metadata-only lookup - a too-long video is
    rejected without ever being fetched.
    """
    if not pipeline_service.is_youtube_url(payload.url):
        raise HTTPException(400, "Only YouTube URLs are supported")

    try:
        duration, title = pipeline_service.probe_youtube_metadata(payload.url)
    except Exception as e:
        raise HTTPException(400, "Could not read this YouTube URL.") from e

    if duration > settings.MAX_VIDEO_DURATION_SECONDS:
        limit_minutes = settings.MAX_VIDEO_DURATION_SECONDS // 60
        raise HTTPException(400, f"Video exceeds the {limit_minutes}-minute limit")

    storage_key = uuid.uuid4().hex[:12]
    output_dir = os.path.join(settings.OUTPUT_DIR, storage_key)
    os.makedirs(output_dir, exist_ok=True)

    try:
        source_path = pipeline_service.download_youtube_video(payload.url, output_dir)
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(400, "Could not download this YouTube video.") from e

    # Re-probe the actual downloaded file rather than trusting yt-dlp's
    # reported metadata duration, matching the upload path's source of truth.
    try:
        duration = pipeline_service.probe_duration_seconds(source_path)
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(400, "Downloaded file could not be read as a video.") from e

    return _create_video_and_start_pipeline(
        db,
        original_filename=f"{title}.mp4",
        storage_key=storage_key,
        title=title,
        source_path=source_path,
        duration_seconds=duration,
    )


@router.post("/{video_id}/retry", response_model=VideoResponse, status_code=201)
def retry_video(video_id: int, db: Session = Depends(get_db)) -> Video:
    """Reprocess a video using its already-uploaded file - no re-upload needed."""
    original = db.query(Video).filter(Video.id == video_id).first()
    if original is None:
        raise HTTPException(status_code=404, detail="Video not found")

    source_path = pipeline_service.find_source_file(settings.OUTPUT_DIR, original.storage_key)
    if source_path is None:
        raise HTTPException(400, "Original uploaded file is no longer available; please upload again")

    try:
        duration = pipeline_service.probe_duration_seconds(source_path)
    except Exception as e:
        raise HTTPException(400, "Could not read this file as a video.") from e

    return _create_video_and_start_pipeline(
        db,
        original_filename=original.original_filename,
        storage_key=original.storage_key,
        title=original.title,
        source_path=source_path,
        duration_seconds=duration,
    )


@router.get("", response_model=list[VideoResponse])
def list_videos(db: Session = Depends(get_db)) -> list[Video]:
    """List all videos, most recently created first."""
    return db.query(Video).order_by(Video.created_at.desc()).all()


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: int, db: Session = Depends(get_db)) -> Video:
    """Fetch a single video by id."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video
