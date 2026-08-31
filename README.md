# MicroSaaS Template

> **Clone. Define. Build.** Full-stack SaaS in minutes.

This repo currently has `INITIAL.md` filled out for **Video Auto Editor** — a local MVP that converts an uploaded video file into 3–5 captioned short-form clips, with the pipeline running in the background and live progress in the UI. See `INITIAL.md` for the full spec, `PRPs/video-auto-editor-prp.md` for the implementation blueprint, and `CLAUDE.md` for this build's stack overrides (no auth, SQLite, no Docker — see "Current Build Override" section there).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/manojkanur/MicroSaaS-Template-Private.git .
cd my-saas

# 2. Product is already defined in INITIAL.md (Video Auto Editor) and already
# built — see "Run Locally" below. Edit INITIAL.md if you want to change scope,
# then update PRPs/video-auto-editor-prp.md to match before extending the app.
```

---

## What You Get (this build)

- FastAPI backend running the video pipeline (upload → local Whisper transcription → heuristic segmentation → `ffmpeg` cut/caption), pipeline runs on a background thread with live status/progress
- React frontend: upload form, video list with live status, animated progress loader, clip player with hook titles
- SQLite storage (no Postgres/migrations for this build — additive schema changes are patched in on startup instead)
- No auth, no Docker, no CI, no LLM call — local MVP only

*(The template also supports the full stack below for production SaaS builds — see `CLAUDE.md`'s override table for what's toggled off here.)*

---

## How It Works

```
INITIAL.md defines the product; PRPs/video-auto-editor-prp.md is the
implementation blueprint for the app as it's actually built (already
shipped — there's no scaffold-from-scratch step left to run).

Modules:
├─ Videos  → upload endpoint, background pipeline, list + detail pages
└─ Clips   → embedded in the Video response, rendered inline per-clip

Pipeline (per upload, on a background thread):
transcribing (faster-whisper) → segmenting (heuristic) → cutting_clips (ffmpeg) → done
```

---

## Files

| File | Purpose |
|------|---------|
| `INITIAL.md` | Product spec — currently: Video Auto Editor MVP |
| `PRPs/video-auto-editor-prp.md` | Implementation blueprint matching the shipped app |
| `CLAUDE.md` | Project rules + this build's stack overrides |
| `skills/*.md` | Code patterns (5 files) |
| `agents/*.md` | Agent definitions |
| `.claude/commands/` | Custom commands |

---

## Skills (5 files)

| Skill | Contains |
|-------|----------|
| `BACKEND.md` | FastAPI + JWT + OAuth + Errors *(auth section unused this build)* |
| `FRONTEND.md` | React + UI Kit + API integration |
| `DATABASE.md` | SQLAlchemy + Alembic *(Alembic unused — SQLite, no migrations)* |
| `TESTING.md` | pytest + Vitest |
| `DEPLOYMENT.md` | Docker + GitHub Actions *(unused this build)* |

---

## Commands

| Command | Description |
|---------|-------------|
| `/setup-project` | Interactive wizard |
| `/generate-prp` | Create implementation blueprint |
| `/execute-prp` | Build with parallel agents |

---

## Tech Stack

**Template defaults:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL + SQLAlchemy
- Auth: JWT + Google OAuth
- UI: Chakra UI or Tailwind + Framer Motion
- Deploy: Docker + GitHub Actions

**This build (Video Auto Editor MVP) overrides:**
- Database: SQLite (no migrations)
- Auth: none
- Deploy: local only, no Docker
- Adds: `faster-whisper`, `ffmpeg` for the video pipeline

---

## Output Structure

```
my-saas/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/        # Video, Clip
│   │   ├── routers/       # /api/videos
│   │   ├── services/      # pipeline: transcribe, segment, cut, caption
│   │   └── auth/          # unused this build
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/          # / and /videos/{id}
│       ├── hooks/
│       └── services/
├── output/                 # generated clips, per video_id
└── app.db                  # SQLite, this build
```

---

## Run Locally

```bash
# Prerequisites (this build)
brew install ffmpeg          # or apt-get install ffmpeg / choco install ffmpeg

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# No Docker / docker-compose for this build
```
