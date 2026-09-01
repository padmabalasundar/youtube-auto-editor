# Backend Skill

> FastAPI + local video pipeline (no auth, no external LLM calls)

This build has no users/accounts — every route is unauthenticated, single-tenant.
There is no `auth/` package and no JWT/OAuth in this project.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app, CORS, static /output mount, startup sweep
│   ├── config.py        # Settings (env-driven)
│   ├── database.py      # SQLite engine/session, additive-column patching
│   ├── models/          # Video, Clip (SQLAlchemy)
│   ├── schemas/         # Pydantic response models
│   ├── routers/         # videos.py - the only router
│   └── services/        # pipeline_service.py - transcribe/segment/cut
├── tests/
└── requirements.txt
```

---

## Main App

```python
# main.py
app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generated clips/uploaded sources are served directly as static files.
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR), name="output")

app.include_router(videos.router, prefix="/api")

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
```

On startup, any `Video` row still `status="processing"` from a prior server run is swept to `failed` — there's no checkpoint/resume for an interrupted pipeline.

---

## Config

```python
# config.py
class Settings(BaseSettings):
    APP_NAME: str = "YouTube Auto Editor"
    DATABASE_URL: str = "sqlite:///./app.db"
    SECRET_KEY: str = "dev-secret-key"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    OUTPUT_DIR: str = "./output"
    MAX_VIDEO_DURATION_SECONDS: int = 1800

    class Config:
        env_file = ".env"
        extra = "ignore"  # .env also carries VITE_API_URL for the frontend

settings = Settings()
```

---

## Router Pattern (two input paths, one pipeline)

A `Video` can come from a file upload or a YouTube URL - both validate/probe duration, then hand off to the same shared helper that creates the row and starts the background pipeline thread:

```python
# routers/videos.py
router = APIRouter(prefix="/videos", tags=["videos"])

def _create_video_and_start_pipeline(db, *, original_filename, storage_key, title, source_path, duration_seconds) -> Video:
    video = Video(original_filename=original_filename, storage_key=storage_key, title=title, status=VideoStatus.PENDING)
    db.add(video)
    db.commit()
    db.refresh(video)
    threading.Thread(target=_run_pipeline_in_background, args=(video.id, source_path, duration_seconds), daemon=True).start()
    return video

@router.post("", response_model=VideoResponse, status_code=201)
def create_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Video:
    ...  # save upload, probe_duration_seconds, enforce MAX_VIDEO_DURATION_SECONDS, then _create_video_and_start_pipeline

@router.post("/from-url", response_model=VideoResponse, status_code=201)
def create_video_from_url(payload: VideoUrlRequest, db: Session = Depends(get_db)) -> Video:
    ...  # is_youtube_url, probe_youtube_metadata (no download), enforce limit, download_youtube_video, re-probe, then _create_video_and_start_pipeline

@router.post("/{video_id}/retry", response_model=VideoResponse, status_code=201)
def retry_video(video_id: int, db: Session = Depends(get_db)) -> Video:
    ...  # find_source_file(storage_key), reprocess without re-uploading
```

Run the pipeline on a plain daemon `threading.Thread`, not a FastAPI `BackgroundTask` - a many-minutes Whisper/ffmpeg run must stay fully off Starlette's request threadpool so it never competes with other requests. The background thread opens its own `SessionLocal()` since the request's `Depends(get_db)` session closes as soon as the response is sent.

---

## Pipeline Service Pattern

```python
# services/pipeline_service.py
def run_pipeline(db: Session, video: Video, source_path: str, duration_seconds: float) -> None:
    """Never raises - any failure is captured onto video.status/error_message."""
    try:
        segments, language = _transcribe_with_whisper(source_path, duration_seconds, on_progress=_report_progress)
        video.language = language
        video_duration = duration_seconds  # always the real probed duration, never derived from the transcript
        proposed_clips = _segment_clips_heuristic(segments, video_duration)
        valid_clips = _validate_clips(proposed_clips, video_duration)
        cut_results = _cut_all_clips(output_dir, source_filename, valid_clips, on_progress=_report_progress)
        # ... persist Clip rows, video.status = DONE
    except Exception as e:
        video.status = VideoStatus.FAILED
        video.error_message = str(e)
        db.commit()
```

Key decisions:
- **`faster-whisper`** (`small`, int8, CPU), `language=None` to auto-detect rather than force a single language.
- **No LLM call** for clip selection - a heuristic picks evenly-spaced ~60s windows and cycles them through `summary`/`main_idea`/`pain_point_solution`, titled from the window's own transcript text (or `"Clip N"` if there's no transcript at all, e.g. a silent source).
- Always segment against the **real ffprobe-measured duration**, not the last transcript segment's end time - Whisper's VAD can miss trailing speech, which would otherwise make the pipeline think the video ends early and silently drop real content.
- `ffmpeg` crops every clip to 1080x1920 (9:16), no burned-in captions.
- YouTube URLs are validated by hostname (`youtube.com`, `youtu.be`, etc.) before ever being handed to `yt-dlp` - don't widen this to a generic "fetch any URL" surface.

---

## Requirements

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.25
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
python-multipart>=0.0.9   # UploadFile/File(...) multipart parsing
faster-whisper>=1.0.0     # local transcription, any language
yt-dlp>=2024.12.6         # YouTube URL input path
# ffmpeg/ffprobe are system binaries, not pip packages - must be on PATH
```
