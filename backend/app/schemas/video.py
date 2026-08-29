"""Pydantic schemas for the Video / Clip API surface."""
from datetime import datetime

from pydantic import BaseModel

from app.models.clip import ClipType
from app.models.video import VideoStatus


class VideoCreate(BaseModel):
    """Payload for submitting a new YouTube video for processing."""

    youtube_url: str


class ClipResponse(BaseModel):
    """A generated short-form clip returned to clients."""

    id: int
    video_id: int
    type: ClipType
    hook_title: str
    start_time: float
    end_time: float
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    """A video and its generated clips returned to clients."""

    id: int
    youtube_url: str
    youtube_id: str
    title: str | None = None
    status: VideoStatus
    error_message: str | None = None
    language: str | None = None
    created_at: datetime
    clips: list[ClipResponse] = []

    class Config:
        from_attributes = True
