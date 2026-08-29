# PRP: YouTube Auto Editor (MVP)

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | YouTube Auto Editor (MVP) |
| **Type** | SaaS (this build = local MVP / proof of concept, not the production multi-tenant SaaS) |
| **Version** | 1.0 |
| **Created** | 2026-08-29 |
| **Complexity** | Medium (video pipeline is the risk area; CRUD surface is small) |

---

## PRODUCT OVERVIEW

**Description:** Paste a YouTube URL → the system downloads the video, pulls its transcript, uses one LLM call to identify 3–5 segments (summary / main idea / pain-point-solution), cuts each into a 45–75s 9:16 clip with burned-in captions in the source language, and saves them locally. A single page lists processed videos and lets you preview the generated clips.

**Value Proposition:** Turns a long-form YouTube video into ready-to-post short-form clips with almost no manual editing.

**MVP Scope:**
- [ ] Paste YouTube URL → get 3–5 captioned 9:16 clips saved locally
- [ ] List page showing processed videos
- [ ] Detail page playing each clip with its hook title

**Explicitly out of scope:** auth, multi-tenancy, cloud storage, job queue/concurrency, non-YouTube sources, custom templates/branding, background music, translation.

---

## ⚠️ STACK OVERRIDES IN EFFECT (per CLAUDE.md / INITIAL.md)

CLAUDE.md's general template defaults (JWT + Google OAuth, PostgreSQL + Alembic, Docker, 80% coverage) do **not** apply to this build. This PRP follows the overrides below instead:

| Layer | Template default | This build |
|-------|-------------------|------------|
| Auth | JWT + Google OAuth | **None** — no login, no User model, single local user |
| Database | PostgreSQL + Alembic | **SQLite** via SQLAlchemy, schema created on startup, no migrations |
| Docker | Required | **Skip** — run locally via `uvicorn` / `npm run dev` |
| Test coverage | 80%+ | **Skip** — smoke test only |
| UI | Chakra UI or Tailwind + Framer Motion | Tailwind, no auth pages, motion optional |

All other CLAUDE.md rules (type hints, async endpoints, no `print()`/`any`/inline styles, secrets via env vars) still apply.

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | SQLite + SQLAlchemy (no Alembic, no migrations) | skills/DATABASE.md |
| Auth | None (this build) | — |
| UI | Tailwind | skills/FRONTEND.md |
| Video pipeline | `yt-dlp`, `youtube-transcript-api` (fallback), local Whisper (`small`, fallback only), `ffmpeg` | — (see PIPELINE section) |
| Testing | Smoke test only | skills/TESTING.md |
| Deployment | None — local only | skills/DEPLOYMENT.md (unused this build) |

---

## DATABASE MODELS

No `User` model — single local user, no auth this build.

### Video
```
id, youtube_url, youtube_id, title
status: pending | processing | done | failed
error_message (nullable)
language
created_at
```

### Clip
```
id, video_id (FK -> Video)
type: summary | main_idea | pain_point_solution
hook_title (string, LLM-generated)
start_time, end_time
file_path
created_at
```

Relationship: `Video 1—N Clip`. Schema created on app startup (`Base.metadata.create_all`), no Alembic migrations this build.

---

## MODULES

### Module 1: Videos (core)
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Description:** Accepts a YouTube URL, runs the full pipeline synchronously (no queue — single blocking request is fine for MVP), stores source metadata and processing status.

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| POST | /api/videos | Submit a YouTube URL, runs pipeline, returns Video + Clips |
| GET | /api/videos | List all processed videos |
| GET | /api/videos/{id} | Get one video with its clips |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|-------------|
| / | HomePage | UrlSubmitForm, VideoList |
| /videos/{id} | VideoDetailPage | ClipPlayer (x per clip), StatusBanner |

---

### Module 2: Clips
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Description:** Generated short-form outputs belonging to a Video. No standalone pages — clips render inline on `/videos/{id}`.

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | /api/videos/{video_id}/clips | List clips for a video (also embedded in `GET /api/videos/{id}`) |

**Frontend:** Rendered inline on `VideoDetailPage` via an HTML5 `<video>` player per clip, showing `hook_title`.

---

## PIPELINE (service layer, invoked by `POST /api/videos`)

Implemented as `backend/app/services/pipeline_service.py` — not inline endpoint logic.

1. Validate URL, extract `youtube_id`. Reject videos >30 min (400 + message).
2. Download via `yt-dlp` (≤1080p mp4).
3. Get transcript: YouTube captions first; local Whisper (`small`) only if no captions exist.
4. **One** LLM call with the full timestamped transcript → structured JSON: 3–5 clips, each with `type`, `start`, `end` (45–75s), `hook_title`. Same language as source, no translation.
5. `ffmpeg`: cut each segment, crop/pad to 9:16, burn in captions from the transcript slice.
6. Save files to `/output/{youtube_id}/clip_N.mp4`; write `Video` + `Clip` rows to SQLite.
7. On any failure past step 2, set `status=failed` with `error_message` — never crash the request.

---

## PHASE EXECUTION PLAN

Only DATABASE-AGENT, BACKEND-AGENT, and FRONTEND-AGENT are defined in `/agents` for this build (no DEVOPS-AGENT/TEST-AGENT/REVIEW-AGENT files exist — Docker and coverage gates are skipped per the stack override, so their work is folded into BACKEND-AGENT/manual validation instead).

**Phase 1: Foundation (3 agents in parallel)**
- DATABASE-AGENT: `Video`/`Clip` SQLAlchemy models, `database.py` (SQLite engine + session, `create_all` on startup)
- BACKEND-AGENT: `main.py`, `config.py` (env vars incl. `LLM_API_KEY`), project structure, `pipeline_service.py` skeleton, `/output` dir handling
- FRONTEND-AGENT: Vite + TS + Tailwind setup, folder structure, router, base layout (no auth pages/context)

**Validation Gate 1:** `pip install -r requirements.txt`, app boots and creates `app.db`, `npm install`, `npm run dev` boots

**Phase 2: Modules (backend + frontend in parallel)**
- Videos module: `POST/GET /api/videos`, `GET /api/videos/{id}` + pipeline_service full implementation (steps 1–7 above) → HomePage (URL form + video list) + VideoDetailPage (clip players)
- Clips: embedded serialization on Video endpoints + inline players on VideoDetailPage

**Validation Gate 2:** `ruff check backend/`, `npm run lint && npm run type-check`

**Phase 3: Quality (manual, no dedicated agents this build)**
- Smoke test: `pytest backend/tests -v` (happy path + invalid URL / no-captions / >30min error paths only — not a coverage gate)
- Manual pipeline run against 5–10 sample videos covering: normal talk, tutorial, and one video with no captions (exercises Whisper fallback)

**Final Validation:** App runs locally end-to-end; `/` lists videos; `/videos/{id}` plays clips with hook titles; failed videos show `error_message` without crashing the server

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload` (starts, creates `app.db`), `cd frontend && npm install && npm run dev` |
| 2 | `ruff check backend/`, `npm run lint && npm run type-check` |
| 3 | `pytest backend/tests -v` (smoke only — no `--cov-fail-under`) |
| Final | Manual run: submit a real YouTube URL via `/`, confirm clips appear in `/output/{youtube_id}/` and play on `/videos/{id}` |

---

## ENVIRONMENT VARIABLES

```env
# This build (YouTube Auto Editor MVP)
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key
LLM_API_KEY=xxx
VITE_API_URL=http://localhost:8000

# Template defaults (NOT used this build — no auth/Postgres)
# DATABASE_URL=postgresql://user:pass@localhost:5432/db
# GOOGLE_CLIENT_ID=xxx
# GOOGLE_CLIENT_SECRET=xxx
```

---

## ACCEPTANCE CRITERIA

- [ ] Given a valid YouTube URL, the app produces 3–5 clips in `/output/{youtube_id}/`
- [ ] `/` lists all processed videos; `/videos/{id}` plays their clips with hook titles
- [ ] Invalid URL / no-captions / >30min video returns a clear error, doesn't crash
- [ ] 5–10 sample videos pre-processed and browsable, covering: normal talk, tutorial, and one video with no captions (Whisper fallback path exercised)
- [ ] `ruff check` and `npm run type-check` pass — coverage gate skipped for this build

---

## NEXT STEP

Execute with parallel agents:
```bash
/execute-prp PRPs/youtube-auto-editor-prp.md
```
