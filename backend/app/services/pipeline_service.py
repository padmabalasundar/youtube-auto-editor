"""Core video-processing pipeline: download, transcribe, segment, cut clips.

`extract_video_metadata` is a cheap pre-check the router calls before it ever
creates a `Video` row (so an invalid URL / too-long video never touches the
database). `run_pipeline` is the heavy, synchronous pipeline that mutates and
commits a single already-persisted `Video` row; it never raises - any failure
is captured onto the row itself (`status=failed`, `error_message=...`) so the
caller can simply re-read the row after the call returns.
"""
import logging
import os
import subprocess
from typing import Literal, TypedDict

import anthropic
import yt_dlp
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ValidationError
from app.models.clip import Clip, ClipType
from app.models.video import Video, VideoStatus

logger = logging.getLogger(__name__)

MIN_CLIP_SECONDS = 45.0
MAX_CLIP_SECONDS = 75.0
# How far outside [MIN_CLIP_SECONDS, MAX_CLIP_SECONDS] a model-proposed clip
# duration is still tolerated (rather than skipped outright) as defensive
# slack against imprecise model output.
CLIP_DURATION_SLACK_SECONDS = 15.0


class TranscriptSegment(TypedDict):
    """A single timestamped transcript segment."""

    start: float
    end: float
    text: str


class VideoMetadata(TypedDict):
    """Metadata extracted from a YouTube URL before any DB row is created."""

    youtube_id: str
    title: str | None
    duration: float | None


class ClipSegment(BaseModel):
    """One clip segment proposed by the segmentation model."""

    type: Literal["summary", "main_idea", "pain_point_solution"]
    start: float
    end: float
    hook_title: str


class SegmentationResult(BaseModel):
    """The full set of clip segments proposed by the segmentation model."""

    clips: list[ClipSegment]


def extract_video_metadata(youtube_url: str) -> VideoMetadata:
    """Fetch id/title/duration for a YouTube URL without downloading it.

    Raises whatever `yt_dlp` raises (e.g. `yt_dlp.utils.DownloadError`) for an
    invalid/unreachable URL - the caller is expected to translate that into a
    400. Raises `ValidationError` directly if the video's duration is unknown
    or exceeds `settings.MAX_VIDEO_DURATION_SECONDS`.
    """
    ydl_opts: dict[str, bool | str] = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    duration = info.get("duration")
    if duration is None or duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise ValidationError("Video exceeds the 30-minute limit")

    return VideoMetadata(
        youtube_id=info["id"],
        title=info.get("title"),
        duration=duration,
    )


def _download_source_video(youtube_url: str, output_dir: str) -> str:
    """Download the source video into `output_dir` as `source.mp4`."""
    source_path = os.path.join(output_dir, "source.mp4")
    ydl_opts: dict[str, str | bool] = {
        "quiet": True,
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
            "best[height<=1080][ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": source_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return source_path


def _fetch_transcript(youtube_id: str, source_path: str) -> tuple[list[TranscriptSegment], str | None]:
    """Get timestamped transcript segments and a detected language.

    Tries the YouTube captions API first; falls back to local Whisper
    transcription of the downloaded source video if no captions exist.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(youtube_id)
        segments: list[TranscriptSegment] = [
            {
                "start": float(snippet.start),
                "end": float(snippet.start) + float(snippet.duration),
                "text": snippet.text,
            }
            for snippet in fetched
        ]
        language: str | None = getattr(fetched, "language_code", None)
        if not segments:
            raise ValueError("Empty transcript returned")
        return segments, language
    except Exception as api_error:  # noqa: BLE001 - any captions failure falls back to Whisper
        logger.warning(
            "youtube_transcript_api failed for %s, falling back to Whisper: %s",
            youtube_id,
            api_error,
        )

    # Lazy import: Whisper pulls in torch, which is heavy and not guaranteed
    # to be installed. Keep the import local to this fallback path only.
    import whisper

    model = whisper.load_model("small")
    result = model.transcribe(source_path)
    whisper_segments: list[TranscriptSegment] = [
        {
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": str(seg["text"]),
        }
        for seg in result["segments"]
    ]
    whisper_language: str | None = result.get("language")
    return whisper_segments, whisper_language


def _build_timestamped_transcript(segments: list[TranscriptSegment]) -> str:
    """Render segments as `[start-end] text` lines for the LLM prompt."""
    lines = [f"[{seg['start']:.2f}-{seg['end']:.2f}] {seg['text']}" for seg in segments]
    return "\n".join(lines)


def _segment_clips(timestamped_transcript: str) -> SegmentationResult:
    """Ask Claude to pick clip segments from the timestamped transcript."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.parse(
        model="claude-opus-5",
        max_tokens=4096,
        system=(
            "You select short-form clips from a YouTube transcript. Given a timestamped "
            "transcript, pick 3 to 5 segments: one 'summary', one 'main_idea', and up to "
            "3 'pain_point_solution' segments. Each segment must be 45 to 75 seconds long "
            "(end - start), use timestamps that exist in the transcript, and get a short, "
            "curiosity-inducing hook_title in the SAME language as the transcript - do not translate."
        ),
        messages=[{"role": "user", "content": timestamped_transcript}],
        output_format=SegmentationResult,
    )
    result: SegmentationResult = response.parsed_output
    return result


def _validate_clips(clips: list[ClipSegment], video_duration: float | None) -> list[ClipSegment]:
    """Drop clips with implausible durations or out-of-bounds timestamps."""
    valid: list[ClipSegment] = []
    for clip in clips:
        duration = clip.end - clip.start
        if duration <= 0:
            continue
        if duration < MIN_CLIP_SECONDS - CLIP_DURATION_SLACK_SECONDS:
            continue
        if duration > MAX_CLIP_SECONDS + CLIP_DURATION_SLACK_SECONDS:
            continue
        if clip.start < 0:
            continue
        if video_duration is not None and clip.end > video_duration:
            continue
        valid.append(clip)
    return valid


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(
    segments: list[TranscriptSegment],
    clip_start: float,
    clip_end: float,
    srt_path: str,
) -> None:
    """Write an SRT file for the transcript segments overlapping [clip_start, clip_end]."""
    overlapping = [seg for seg in segments if seg["end"] > clip_start and seg["start"] < clip_end]
    lines: list[str] = []
    for index, seg in enumerate(overlapping, start=1):
        rebased_start = max(0.0, seg["start"] - clip_start)
        rebased_end = max(0.0, min(seg["end"], clip_end) - clip_start)
        lines.append(str(index))
        lines.append(f"{_format_srt_timestamp(rebased_start)} --> {_format_srt_timestamp(rebased_end)}")
        lines.append(seg["text"])
        lines.append("")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _cut_clip(
    output_dir: str,
    source_filename: str,
    srt_filename: str,
    clip_filename: str,
    start: float,
    end: float,
) -> None:
    """Run ffmpeg to slice, crop-to-vertical, and burn subtitles for one clip.

    `cwd` is set to `output_dir` so `source_filename`/`srt_filename` can stay
    relative - this avoids the ffmpeg `subtitles=` filter's `:` escaping
    problem with Windows drive letters (e.g. `G:\\...`) entirely.
    """
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"subtitles={srt_filename}"
    )
    command = [
        "ffmpeg",
        "-y",
        "-i",
        source_filename,
        "-ss",
        str(start),
        "-to",
        str(end),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        clip_filename,
    ]
    subprocess.run(command, check=True, capture_output=True, cwd=output_dir)


def run_pipeline(db: Session, video: Video) -> None:
    """Run the full clip-generation pipeline for an already-persisted Video.

    Mutates and commits `video` in place; never raises - any failure along
    the way is captured onto `video.status` / `video.error_message`.
    """
    video.status = VideoStatus.PROCESSING
    db.commit()

    try:
        output_dir = os.path.join(settings.OUTPUT_DIR, video.youtube_id)
        os.makedirs(output_dir, exist_ok=True)

        source_path = _download_source_video(video.youtube_url, output_dir)

        segments, language = _fetch_transcript(video.youtube_id, source_path)
        if not segments:
            raise RuntimeError("No transcript segments were produced")
        video.language = language

        timestamped_transcript = _build_timestamped_transcript(segments)

        segmentation_result = _segment_clips(timestamped_transcript)

        video_duration = segments[-1]["end"] if segments else None
        valid_clips = _validate_clips(segmentation_result.clips, video_duration)
        if len(valid_clips) < 1:
            raise RuntimeError("No valid clips were produced by the segmentation model")

        clip_type_map = {
            "summary": ClipType.SUMMARY,
            "main_idea": ClipType.MAIN_IDEA,
            "pain_point_solution": ClipType.PAIN_POINT_SOLUTION,
        }

        for index, clip_segment in enumerate(valid_clips, start=1):
            srt_filename = f"clip_{index}.srt"
            clip_filename = f"clip_{index}.mp4"
            srt_path = os.path.join(output_dir, srt_filename)

            _write_srt(segments, clip_segment.start, clip_segment.end, srt_path)
            _cut_clip(
                output_dir=output_dir,
                source_filename="source.mp4",
                srt_filename=srt_filename,
                clip_filename=clip_filename,
                start=clip_segment.start,
                end=clip_segment.end,
            )

            relative_file_path = f"{video.youtube_id}/{clip_filename}"
            clip = Clip(
                video_id=video.id,
                type=clip_type_map[clip_segment.type],
                hook_title=clip_segment.hook_title,
                start_time=clip_segment.start,
                end_time=clip_segment.end,
                file_path=relative_file_path,
            )
            db.add(clip)

        video.status = VideoStatus.DONE
        db.commit()
    except Exception as e:
        video.status = VideoStatus.FAILED
        video.error_message = str(e)
        db.commit()
        logger.exception("Pipeline failed for video id=%s youtube_id=%s", video.id, video.youtube_id)
        return
