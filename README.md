# Video Auto Editor

> Upload a long video, get back short, captioned, vertical clips — automatically.

A local single-user MVP that turns an uploaded video into 3–5 short-form clips: it transcribes the audio, picks the best moments, and cuts each one into a 9:16 vertical clip with `ffmpeg`. No YouTube URL fetching, no login, no cloud dependency — everything runs on your own machine (or your own server).

Repo: https://github.com/padmabalasundar/youtube-auto-editor

---

## Features

- **Upload & forget** — drop in a video file; clip generation runs on a background thread while you watch live progress (transcribing → segmenting → cutting) from the UI.
- **Local transcription** — [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (`small`, int8, CPU) transcribes the audio locally, no external API calls.
- **Automatic clip selection** — a heuristic segmenter picks 3–5 evenly-spaced ~60s windows and cycles them through `summary` / `main idea` / `pain point & solution` slots, titled from their own transcript text.
- **Vertical clips, ready to post** — each clip is cropped to 1080×1920 (9:16) via `ffmpeg`.
- **Resilient pipeline** — a video with no detectable speech (silent source, or the whole track filtered out as non-speech) still produces evenly time-sliced clips instead of failing outright; a failed run can be retried from the already-uploaded source without re-uploading.
- **Live status UI** — a dark, Netflix-inspired frontend: upload hero, a poster-grid of your videos with status badges, and an animated per-stage progress bar while a video processes.
- **No accounts, no database server** — SQLite, schema created on startup, single local user. Nothing to configure before your first upload.

### Current limits

- Transcription language is hardcoded to Tamil (`language="ta"` in `pipeline_service.py`) — change that constant to transcribe other languages.
- Videos over 30 minutes or 1.5GB are rejected up front (`MAX_VIDEO_DURATION_SECONDS`, `MAX_UPLOAD_BYTES` in `backend/app/config.py` / `pipeline_service.py`).
- Clip selection is a fixed-length heuristic, not an LLM pick — fast and free, but it doesn't understand content the way a model-based segmenter would.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python 3.11+, SQLAlchemy + SQLite |
| Frontend | React + TypeScript + Vite, Tailwind CSS |
| Transcription | `faster-whisper` (CPU, int8) |
| Video processing | `ffmpeg` / `ffprobe` |
| Auth | None — local single-user MVP |

See `CLAUDE.md` for the full rationale behind these choices (this build intentionally overrides the repo's template defaults — Postgres/JWT/Docker are the template's defaults for a future multi-tenant SaaS, not used here).

---

## How It Works

```
Upload (POST /api/videos)
        │
        ▼
  transcribing   — faster-whisper transcribes the audio locally
        │
        ▼
  segmenting     — heuristic picks 3–5 clip windows across the video
        │
        ▼
  cutting_clips  — ffmpeg cuts + crops each window to a 9:16 clip
        │
        ▼
       done      — clips listed on the video's detail page
```

The frontend polls `GET /api/videos/{id}` while a video is `pending`/`processing` to show live progress; clips and their metadata come back embedded in the video response once `status` is `done`.

---

## Project Structure

```
.
├── backend/
│   └── app/
│       ├── main.py               # FastAPI app, CORS, static /output mount
│       ├── config.py              # env-driven settings
│       ├── models/                # Video, Clip (SQLAlchemy)
│       ├── routers/videos.py      # upload / list / detail / retry
│       └── services/pipeline_service.py   # transcribe → segment → cut
├── frontend/
│   └── src/
│       ├── pages/                 # HomePage (upload + list), VideoDetailPage
│       ├── components/            # Button, Card, StatusBadge, ProgressLoader
│       ├── hooks/useVideos.ts     # React Query hooks
│       └── services/api.ts
├── output/                        # generated clips + uploaded sources, per video
└── app.db                         # SQLite database
```

---

## Run Locally

**Prerequisites:** Python 3.11+, Node 18+, `ffmpeg`/`ffprobe` on your `PATH`.

```bash
# ffmpeg
brew install ffmpeg          # macOS
# or: sudo apt-get install ffmpeg   (Ubuntu/Debian)
# or: choco install ffmpeg         (Windows)

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (in a separate terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend runs at `http://localhost:5173` and talks to the backend at `http://localhost:8000` (`VITE_API_URL` in `frontend/.env`).

---

## Deployment

There's no Docker setup for this build — it's designed to run as two lightweight local processes. To host it on your own server:

- Serve the backend with `uvicorn` behind a process manager (e.g. a `systemd` unit), bound to `127.0.0.1`.
- Build the frontend (`npm run build`) and serve the static `dist/` output directly from your reverse proxy.
- Point an Nginx (or similar) server block at both: proxy `/api/` and `/output/` to the backend, serve everything else as static files, and terminate TLS with Let's Encrypt/Certbot.

---

## Documentation

| File | Purpose |
|------|---------|
| `INITIAL.md` | Original product spec |
| `PRPs/video-auto-editor-prp.md` | Implementation blueprint matching the shipped app |
| `CLAUDE.md` | Project rules + this build's stack overrides |
| `skills/*.md` | Backend/Frontend/Database/Testing/Deployment reference notes |
