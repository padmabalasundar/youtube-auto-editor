"""Core video-processing pipeline: transcribe, segment, cut clips.

`probe_duration_seconds` is a cheap pre-check the router calls right after
saving an upload to disk, before any `Video` DB row is created (so a too-long
upload never touches the database). `run_pipeline` is the heavy, synchronous
pipeline that mutates and commits a single already-persisted `Video` row; it
never raises - any failure is captured onto the row itself (`status=failed`,
`error_message=...`) so the caller can simply re-read the row after the call
returns.
"""
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal, TypedDict

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.clip import Clip, ClipType
from app.models.video import Video, VideoStatus

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
# Safety cap on a single upload's size, to keep disk/memory usage bounded on
# what's meant to be a lightweight local MVP.
MAX_UPLOAD_BYTES = 1500 * 1024 * 1024

MIN_CLIP_SECONDS = 45.0
MAX_CLIP_SECONDS = 75.0
# How far outside [MIN_CLIP_SECONDS, MAX_CLIP_SECONDS] a proposed clip
# duration is still tolerated (rather than skipped outright) as defensive
# slack against imprecise segmentation.
CLIP_DURATION_SLACK_SECONDS = 15.0

TARGET_CLIP_SECONDS = 60.0
MAX_CLIPS = 5
CLIP_TYPE_CYCLE: list[Literal["summary", "main_idea", "pain_point_solution"]] = [
    "summary",
    "main_idea",
    "pain_point_solution",
    "pain_point_solution",
    "pain_point_solution",
]

# Each ffmpeg encode is itself multi-threaded; running several full-width
# encodes at once oversubscribes CPU cores. Capping per-process threads and
# bounding how many run concurrently keeps total thread usage close to the
# core count instead of thrashing.
FFMPEG_THREADS_PER_CLIP = 2


class TranscriptSegment(TypedDict):
    """A single timestamped transcript segment."""

    start: float
    end: float
    text: str


class ClipSegment(BaseModel):
    """One proposed clip: a time window plus its title and slot type."""

    type: Literal["summary", "main_idea", "pain_point_solution"]
    start: float
    end: float
    hook_title: str


def probe_duration_seconds(path: str) -> float:
    """Read a media file's duration via ffprobe. Raises on an unreadable/invalid file."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def find_source_file(output_dir: str, storage_key: str) -> str | None:
    """Locate an already-uploaded source file for `storage_key`, if it still exists."""
    folder = os.path.join(output_dir, storage_key)
    if not os.path.isdir(folder):
        return None
    for name in os.listdir(folder):
        if name.startswith("source."):
            return os.path.join(folder, name)
    return None


def _transcribe_with_whisper(source_path: str) -> tuple[list[TranscriptSegment], str | None]:
    """Transcribe an uploaded video locally with Whisper.

    Uploads have no YouTube captions to fall back from, so this always runs -
    unlike the old YouTube-URL flow, there's no "try captions first" step.
    """
    # Lazy import: Whisper pulls in torch, which is heavy and not guaranteed
    # to be installed. Keep the import local to this call.
    import whisper

    logger.info(
        "Transcribing %s locally with Whisper ('small' model, forced "
        "language=ta). This can take several minutes on CPU with no "
        "progress logged in between; watch for the tqdm progress bar below.",
        source_path,
    )
    model = whisper.load_model("small")
    # verbose=False: prints a tqdm progress bar (vs. None's total silence,
    # or True's noisy per-segment dump) so a long CPU run isn't
    # indistinguishable from a hang in the server logs.
    #
    # language="ta": forced rather than auto-detected, per explicit choice -
    # auto-detect can misfire and forcing the known language improves
    # accuracy. This hardcodes transcription to Tamil for every upload;
    # supporting other languages would mean making this a per-submission
    # hint rather than a fixed constant.
    result = model.transcribe(source_path, verbose=False, language="ta")
    segments: list[TranscriptSegment] = [
        {
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": str(seg["text"]),
        }
        for seg in result["segments"]
    ]
    language: str | None = result.get("language")
    return segments, language


def _derive_title(segments: list[TranscriptSegment], start: float, end: float) -> str:
    """Best-effort clip title: the first sentence-ish chunk of its transcript text."""
    text = " ".join(
        seg["text"].strip() for seg in segments if seg["end"] > start and seg["start"] < end
    ).strip()
    if not text:
        return "Clip"
    for delimiter in (". ", "! ", "? ", "\n"):
        idx = text.find(delimiter)
        if 10 < idx < 80:
            return text[: idx + 1].strip()
    return f"{text[:77]}..." if len(text) > 80 else text


def _segment_clips_heuristic(segments: list[TranscriptSegment], video_duration: float) -> list[ClipSegment]:
    """Pick clip windows without an LLM: evenly-spaced ~60s windows across the video.

    No Anthropic (or any) API call - titles come from each window's own
    transcript text rather than being AI-generated. Noticeably lower quality
    than an LLM pick, but free and has no external dependency.
    """
    if not segments or video_duration <= 0:
        raise RuntimeError("No transcript content available to segment.")

    clip_length = TARGET_CLIP_SECONDS
    num_clips = min(MAX_CLIPS, int(video_duration // clip_length))
    if num_clips < 1:
        # Video shorter than one full-length clip: use a single clip
        # spanning it (validated/possibly dropped downstream if too short).
        num_clips = 1
        clip_length = video_duration

    spacing = video_duration / num_clips
    clips: list[ClipSegment] = []
    for i in range(num_clips):
        start = i * spacing
        end = min(start + clip_length, video_duration)
        if end - start < 1.0:
            continue
        clips.append(
            ClipSegment(
                type=CLIP_TYPE_CYCLE[i % len(CLIP_TYPE_CYCLE)],
                start=start,
                end=end,
                hook_title=_derive_title(segments, start, end),
            )
        )
    return clips


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
        # veryfast: much quicker than libx264's "medium" default at a modest
        # bitrate-efficiency cost - the right tradeoff for a local MVP where
        # wall-clock time matters more than file size.
        "-preset",
        "veryfast",
        "-threads",
        str(FFMPEG_THREADS_PER_CLIP),
        "-c:a",
        "aac",
        clip_filename,
    ]
    subprocess.run(command, check=True, capture_output=True, cwd=output_dir)


def _cut_all_clips(
    output_dir: str,
    source_filename: str,
    segments: list[TranscriptSegment],
    valid_clips: list[ClipSegment],
) -> list[tuple[ClipSegment, str]]:
    """Cut every clip in parallel - each ffmpeg subprocess is independent I/O+CPU work.

    Returns (clip_segment, clip_filename) pairs in the original clip order.
    Raises (propagating the first error) if any single clip fails to cut.
    """

    def _cut_one(index: int, clip_segment: ClipSegment) -> tuple[int, str]:
        srt_filename = f"clip_{index + 1}.srt"
        clip_filename = f"clip_{index + 1}.mp4"
        srt_path = os.path.join(output_dir, srt_filename)
        _write_srt(segments, clip_segment.start, clip_segment.end, srt_path)
        _cut_clip(
            output_dir=output_dir,
            source_filename=source_filename,
            srt_filename=srt_filename,
            clip_filename=clip_filename,
            start=clip_segment.start,
            end=clip_segment.end,
        )
        return index, clip_filename

    cpu_count = os.cpu_count() or 4
    max_workers = max(1, min(len(valid_clips), cpu_count // FFMPEG_THREADS_PER_CLIP))

    results: list[tuple[ClipSegment, str] | None] = [None] * len(valid_clips)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_cut_one, i, clip) for i, clip in enumerate(valid_clips)]
        for future in as_completed(futures):
            index, clip_filename = future.result()  # re-raises if _cut_one raised
            results[index] = (valid_clips[index], clip_filename)

    return [pair for pair in results if pair is not None]


def run_pipeline(db: Session, video: Video, source_path: str) -> None:
    """Run the full clip-generation pipeline for an already-persisted, already-uploaded Video.

    `source_path` is the already-saved upload on disk (the router saves it
    before creating the DB row). Mutates and commits `video` in place; never
    raises - any failure along the way is captured onto `video.status` /
    `video.error_message`.
    """
    video.status = VideoStatus.PROCESSING
    db.commit()

    try:
        output_dir = os.path.dirname(source_path)
        source_filename = os.path.basename(source_path)

        segments, language = _transcribe_with_whisper(source_path)
        if not segments:
            raise RuntimeError("No transcript segments were produced")
        video.language = language

        video_duration = segments[-1]["end"]
        proposed_clips = _segment_clips_heuristic(segments, video_duration)

        valid_clips = _validate_clips(proposed_clips, video_duration)
        if len(valid_clips) < 1:
            raise RuntimeError("No valid clips were produced by the segmentation step")

        clip_type_map = {
            "summary": ClipType.SUMMARY,
            "main_idea": ClipType.MAIN_IDEA,
            "pain_point_solution": ClipType.PAIN_POINT_SOLUTION,
        }

        cut_results = _cut_all_clips(output_dir, source_filename, segments, valid_clips)
        for clip_segment, clip_filename in cut_results:
            relative_file_path = f"{os.path.basename(output_dir)}/{clip_filename}"
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
        logger.exception("Pipeline failed for video id=%s storage_key=%s", video.id, video.storage_key)
        return
