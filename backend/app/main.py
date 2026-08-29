"""FastAPI application entrypoint."""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.routers import videos

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
    """Create database tables and ensure the output directory exists."""
    create_tables()
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    logger.info("Startup complete: tables ready, output dir=%s", settings.OUTPUT_DIR)


app.include_router(videos.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
