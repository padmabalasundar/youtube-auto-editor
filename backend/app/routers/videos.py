"""Video submission and retrieval endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.exceptions import ValidationError
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoCreate, VideoResponse
from app.services import pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoResponse, status_code=201)
async def create_video(payload: VideoCreate, db: Session = Depends(get_db)) -> Video:
    """Submit a YouTube URL, then run the full clip-generation pipeline synchronously."""
    try:
        metadata = pipeline_service.extract_video_metadata(payload.youtube_url)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.warning("Failed to extract metadata for %s: %s", payload.youtube_url, e)
        raise HTTPException(status_code=400, detail="Invalid YouTube URL") from e

    video = Video(
        youtube_url=payload.youtube_url,
        youtube_id=metadata["youtube_id"],
        title=metadata["title"],
        status=VideoStatus.PENDING,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    pipeline_service.run_pipeline(db, video)

    db.refresh(video)
    return video


@router.get("", response_model=list[VideoResponse])
async def list_videos(db: Session = Depends(get_db)) -> list[Video]:
    """List all videos, most recently created first."""
    return db.query(Video).order_by(Video.created_at.desc()).all()


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, db: Session = Depends(get_db)) -> Video:
    """Fetch a single video by id."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video
