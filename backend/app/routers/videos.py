"""Video upload and retrieval endpoints."""
import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoResponse
from app.services import pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


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


@router.post("", response_model=VideoResponse, status_code=201)
def create_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Video:
    """Upload a video file, then run the full clip-generation pipeline synchronously.

    Plain `def`, not `async def`: the pipeline (Whisper, ffmpeg) is all
    blocking I/O/CPU work. FastAPI runs sync route functions in a worker
    thread pool, so this one long-running request doesn't freeze the single
    asyncio event loop for every other concurrent request (list/detail pages,
    other submissions) the way an `async def` calling blocking code would.
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
        raise HTTPException(400, "Video exceeds the 30-minute limit")

    video = Video(
        original_filename=original_filename,
        storage_key=storage_key,
        title=Path(original_filename).stem,
        status=VideoStatus.PENDING,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    pipeline_service.run_pipeline(db, video, source_path)

    db.refresh(video)
    return video


@router.post("/{video_id}/retry", response_model=VideoResponse, status_code=201)
def retry_video(video_id: int, db: Session = Depends(get_db)) -> Video:
    """Reprocess a video using its already-uploaded file - no re-upload needed."""
    original = db.query(Video).filter(Video.id == video_id).first()
    if original is None:
        raise HTTPException(status_code=404, detail="Video not found")

    source_path = pipeline_service.find_source_file(settings.OUTPUT_DIR, original.storage_key)
    if source_path is None:
        raise HTTPException(400, "Original uploaded file is no longer available; please upload again")

    retry = Video(
        original_filename=original.original_filename,
        storage_key=original.storage_key,
        title=original.title,
        status=VideoStatus.PENDING,
    )
    db.add(retry)
    db.commit()
    db.refresh(retry)

    pipeline_service.run_pipeline(db, retry, source_path)

    db.refresh(retry)
    return retry


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
