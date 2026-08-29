# MicroSaaS Template

> **Clone. Define. Build.** Full-stack SaaS in minutes.

This repo currently has `INITIAL.md` filled out for **YouTube Auto Editor** — a local MVP that converts a YouTube URL into 3–5 captioned short-form clips. See `INITIAL.md` for the full spec, and `CLAUDE.md` for this build's stack overrides (no auth, SQLite, no Docker — see "Current Build Override" section there).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/manojkanur/MicroSaaS-Template-Private.git .
cd my-saas

# 2. Product is already defined in INITIAL.md (YouTube Auto Editor)
# Edit it if you want to change scope

# 3. Generate blueprint
/generate-prp INITIAL.md

# 4. Build with parallel agents
/execute-prp PRPs/youtube-auto-editor-prp.md
```

---

## What You Get (this build)

- FastAPI backend running the video pipeline (`yt-dlp` → transcript → LLM segmentation → `ffmpeg` cut/caption)
- React frontend: paste-URL form, video list, clip player with hook titles
- SQLite storage (no Postgres/migrations for this build)
- No auth, no Docker, no CI — local MVP only

*(The template also supports the full stack below for production SaaS builds — see `CLAUDE.md`'s override table for what's toggled off here.)*

---

## How It Works

```
INITIAL.md → /generate-prp → PRP blueprint → /execute-prp → Full App

Phase 1 (Parallel):
├─ DATABASE-AGENT  → SQLite models (Video, Clip)
├─ BACKEND-AGENT   → API + video pipeline service
├─ FRONTEND-AGENT  → React pages (list + detail/player)
└─ DEVOPS-AGENT    → skipped this build (no Docker)

Phase 2 (Per Module):
├─ Backend endpoints (POST/GET /api/videos, GET /api/videos/{id})
└─ Frontend pages (/  and  /videos/{id})

Phase 3:
└─ Smoke tests only (80% coverage gate skipped this build)
```

---

## Files

| File | Purpose |
|------|---------|
| `INITIAL.md` | Product spec — currently: YouTube Auto Editor MVP |
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

**This build (YouTube Auto Editor MVP) overrides:**
- Database: SQLite (no migrations)
- Auth: none
- Deploy: local only, no Docker
- Adds: `yt-dlp`, `youtube-transcript-api`, `ffmpeg` for the video pipeline

---

## Output Structure

```
my-saas/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/        # Video, Clip
│   │   ├── routers/       # /api/videos
│   │   ├── services/      # pipeline: download, transcript, segment, cut, caption
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
brew install ffmpeg          # or apt-get install ffmpeg
pip install yt-dlp youtube-transcript-api

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
