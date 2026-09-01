"""Video model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clip import Clip


class VideoStatus(str, enum.Enum):
    """Processing status of a video."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Video(Base, TimestampMixin):
    """An uploaded video submitted for auto-editing."""

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    # Folder key under OUTPUT_DIR (e.g. output/{storage_key}/source.mp4,
    # clip_1.mp4, ...) - a generated id, since there's no YouTube id anymore.
    storage_key: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus),
        default=VideoStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    # Live pipeline progress, e.g. stage="transcribing" percent=42 - polled by
    # the frontend while status is pending/processing to drive a progress bar.
    progress_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    clips: Mapped[list["Clip"]] = relationship(
        "Clip",
        back_populates="video",
        cascade="all, delete-orphan",
    )
