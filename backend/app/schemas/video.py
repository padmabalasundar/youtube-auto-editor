"""Pydantic schemas for the Video / Clip API surface."""
from datetime import datetime

from pydantic import BaseModel

from app.models.clip import ClipType
from app.models.video import VideoStatus


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
    original_filename: str
    storage_key: str
    title: str | None = None
    status: VideoStatus
    error_message: str | None = None
    language: str | None = None
    progress_stage: str | None = None
    progress_percent: int | None = None
    created_at: datetime
    clips: list[ClipResponse] = []

    class Config:
        from_attributes = True
