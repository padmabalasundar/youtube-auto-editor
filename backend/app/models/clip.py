"""Clip model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.video import Video


class ClipType(str, enum.Enum):
    """The kind of short-form clip generated from a video."""

    SUMMARY = "summary"
    MAIN_IDEA = "main_idea"
    PAIN_POINT_SOLUTION = "pain_point_solution"


class Clip(Base, TimestampMixin):
    """A generated short-form clip belonging to a video."""

    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[ClipType] = mapped_column(Enum(ClipType), nullable=False)
    hook_title: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    video: Mapped["Video"] = relationship("Video", back_populates="clips")
