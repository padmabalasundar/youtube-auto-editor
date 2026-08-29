"""FastAPI application entrypoint."""
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, create_tables
from app.models.video import Video, VideoStatus
from app.routers import videos

# Video titles/transcripts can be in any language (no translation, per spec).
# Windows consoles default to a legacy codepage (e.g. cp1252) that can't
# encode most non-Latin text, which would crash logger.warning/.exception
# calls with UnicodeEncodeError the moment a non-English title/error string
# is logged - silently hiding the real error behind an encoding one instead.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory must exist before StaticFiles is constructed (it checks at
# construction time, which happens at import — before the startup hook runs).
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR), name="output")


@app.on_event("startup")
async def on_startup() -> None:
    """Create database tables, ensure the output directory exists, and clear zombie rows.

    A video can be left permanently stuck at status="processing" if the
    server process dies or reloads (e.g. `--reload` restarting the worker)
    while its pipeline thread was mid-run — the row was already committed to
    "processing" before the interruption, but nothing is working on it
    anymore. Sweep those on every startup so the UI doesn't show a video as
    "processing" forever; the user has to resubmit the URL either way, since
    there's no checkpoint/resume for an interrupted pipeline run.
    """
    create_tables()
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        stuck = db.query(Video).filter(Video.status == VideoStatus.PROCESSING).all()
        for video in stuck:
            video.status = VideoStatus.FAILED
            video.error_message = "Interrupted by a server restart. Please resubmit this URL."
        if stuck:
            db.commit()
            logger.warning("Marked %d stuck 'processing' video(s) as failed on startup.", len(stuck))
    finally:
        db.close()

    logger.info("Startup complete: tables ready, output dir=%s", settings.OUTPUT_DIR)


app.include_router(videos.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
