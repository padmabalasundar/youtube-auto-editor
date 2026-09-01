# PRP: Video Auto Editor (MVP)

> Implementation blueprint — reflects the shipped app, not a forward-looking build plan

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | Video Auto Editor (MVP) |
| **Type** | SaaS (this build = local MVP / proof of concept, not the production multi-tenant SaaS) |
| **Version** | 2.0 — revised after the pivot from YouTube-URL ingestion to direct file upload |
| **Created** | 2026-08-29 |
| **Revised** | 2026-08-31 |
| **Complexity** | Medium (video pipeline is the risk area; CRUD surface is small) |

> Supersedes the original `youtube-auto-editor-prp.md`, written before the product pivoted from "paste a YouTube URL" to "upload a video file" (see `git log -- backend/app/routers/videos.py`). Renamed to match `INITIAL.md`'s current product name.

---

## PRODUCT OVERVIEW

**Description:** Upload a video file → the system transcribes it locally with Whisper, picks 3–5 segments (summary / main idea / pain-point-solution) with a heuristic (no LLM call), and cuts each into a 45–75s 9:16 clip (no captions burned in), saving them locally. A single page lists processed videos and lets you preview the generated clips as small grid-laid-out players, with live status/progress while a video is in flight.

**Value Proposition:** Turns a long-form video file into ready-to-post short-form clips with almost no manual editing.

**MVP Scope:**
- [x] Upload a video file → get 3–5 9:16 clips (no captions) saved locally
- [x] Upload returns immediately; pipeline runs in the background with live status/progress
- [x] List page showing videos with live status/progress
- [x] Detail page with an animated progress loader while processing, and clip playback with hook titles once done
- [x] Retry a failed video without re-uploading

**Explicitly out of scope:** auth, multi-tenancy, cloud storage, job queue/concurrency beyond a background thread, YouTube or other remote sources, an LLM segmentation call, custom templates/branding, background music, translation, languages other than the hardcoded forced Tamil (`language="ta"`).

---

## ⚠️ STACK OVERRIDES IN EFFECT (per CLAUDE.md / INITIAL.md)

CLAUDE.md's general template defaults (JWT + Google OAuth, PostgreSQL + Alembic, Docker, 80% coverage) do **not** apply to this build. This PRP follows the overrides below instead:

| Layer | Template default | This build |
|-------|-------------------|------------|
| Auth | JWT + Google OAuth | **None** — no login, no User model, single local user |
| Database | PostgreSQL + Alembic | **SQLite** via SQLAlchemy, schema created on startup, plus a lightweight `ALTER TABLE ADD COLUMN` shim (`app/database.py::_add_missing_columns`) for additive model changes instead of real migrations |
| Docker | Required | **Skip** — run locally via `uvicorn` / `npm run dev` |
| Test coverage | 80%+ | **Skip** — smoke test only |
| UI | Chakra UI or Tailwind + Framer Motion | Tailwind, no auth pages, CSS-only animation (no motion library installed) |

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
| Video pipeline | `faster-whisper` (CTranslate2, int8, CPU transcription), `ffmpeg`/`ffprobe` (duration probe, cut + crop to 9:16) | — (see PIPELINE section) |
| Testing | Smoke test only | skills/TESTING.md |
| Deployment | None — local only | skills/DEPLOYMENT.md (unused this build) |

There is **no YouTube ingestion, no `yt-dlp`, no `youtube-transcript-api`, and no LLM call** — the original PRP's design for these was superseded before it shipped. The source video is a direct file upload, and clip boundaries come from an evenly-spaced heuristic over the transcript.

---

## DATABASE MODELS

No `User` model — single local user, no auth this build.

### Video
```
id, original_filename, storage_key, title
status: pending | processing | done | failed
progress_stage: transcribing | segmenting | cutting_clips | done (nullable)
progress_percent: 0-100 (nullable)
error_message (nullable)
language (nullable — set once transcription finishes)
created_at
```

### Clip
```
id, video_id (FK -> Video)
type: summary | main_idea | pain_point_solution
hook_title (string — first sentence-ish chunk of the clip's own transcript text)
start_time, end_time
file_path
created_at
```

Relationship: `Video 1—N Clip`. Schema created on app startup (`Base.metadata.create_all`); `progress_stage`/`progress_percent` were added after the table already existed in some local `app.db` files, so `_add_missing_columns()` patches them in on startup without dropping data.

---

## MODULES

### Module 1: Videos (core)
**Owner (this build):** BACKEND-AGENT (video pipeline + endpoints) + FRONTEND-AGENT (upload form, list, detail/progress UI) — no dedicated DATABASE-AGENT pass since the models are small enough to live in BACKEND-AGENT's scope.

**Description:** Accepts an uploaded video file, validates it (extension, size, duration), starts the pipeline on a background thread with its own DB session, and returns immediately. Stores source metadata, processing status, and live progress.

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| POST | /api/videos | Upload a video file (multipart/form-data); returns the `Video` row (status=pending) immediately, pipeline runs in the background |
| GET | /api/videos | List all videos, most recent first |
| GET | /api/videos/{id} | Get one video with live status/progress and its clips once done |
| POST | /api/videos/{id}/retry | Reprocess a video from its already-uploaded source file (no re-upload needed) |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|-------------|
| / | HomePage | upload form, video list with `StatusBadge` (shows live percent while processing) |
| /videos/{id} | VideoDetailPage | `ProgressLoader` (animated stage/percent bar) while in flight, clip players once done, retry button on failure |

---

### Module 2: Clips
**Owner (this build):** BACKEND-AGENT + FRONTEND-AGENT

**Description:** Generated short-form outputs belonging to a Video. No standalone pages or endpoint — clips are embedded in `GET /api/videos/{id}` and render inline on `/videos/{id}`.

**Frontend:** Rendered inline on `VideoDetailPage` via an HTML5 `<video>` player per clip (served from the mounted `/output` static dir), showing `hook_title` and clip type.

---

## PIPELINE (service layer, invoked by `POST /api/videos`)

Implemented as `backend/app/services/pipeline_service.py`, orchestrated by `backend/app/routers/videos.py`.

**Request flow:**
1. `POST /api/videos` streams the upload to disk (rejecting mid-stream if it exceeds the size cap), validates the extension, probes duration via `ffprobe`, rejects videos over 30 minutes with a 400, creates the `Video` row (`status=pending`), and **returns immediately** with that row.
2. The pipeline runs on a plain daemon `threading.Thread` with its own SQLAlchemy session (`app/routers/videos.py::_run_pipeline_in_background`) — deliberately not FastAPI `BackgroundTasks`, so a many-minutes Whisper/ffmpeg run stays fully off Starlette's request threadpool and never competes with other concurrent requests.
3. The frontend polls `GET /api/videos/{id}` (and `GET /api/videos` while anything is in flight) every 3s and stops once `status` is `done` or `failed`.

**Pipeline stages** (`run_pipeline` updates `Video.status`/`progress_stage`/`progress_percent` as they progress):
1. `transcribing` (0–70% of the bar) — `faster-whisper` ("small", `compute_type=int8`, forced `language=ta`, `beam_size=1`, `vad_filter=True`, `condition_on_previous_text=False`) transcribes the uploaded file directly; there are no captions to fall back from, so this always runs. Progress is computed per-segment as the transcript streams out of the model.
2. `segmenting` (→70%) — evenly-spaced ~60s windows are picked across the video (up to 5 clips), cycling through `summary` → `main_idea` → `pain_point_solution` slots, then validated against a 45–75s duration window with slack.
3. `cutting_clips` (70–100%) — `ffmpeg` cuts each clip in parallel (bounded by CPU core count), using input-side `-ss` (fast keyframe seek) instead of output-side seeking so late-in-the-video clips don't pay for decoding everything before them, and crops/pads to 9:16 (no caption burn-in — dropped both for speed and per product feedback); saves to `output/{storage_key}/clip_N.mp4` and writes `Clip` rows. Progress advances per clip completed.
4. `done` (100%) — all clips saved and queryable.
5. `failed` (from any stage) — sets `error_message`, never crashes the background thread or the app; a `processing` row left stuck by a server restart is swept to `failed` on the next startup (`app/main.py::on_startup`).

**Model loading:** the Whisper model loads lazily on first use and is cached in-process for the server's lifetime (`pipeline_service.py::_get_whisper_model`), so only the first upload pays the model-load cost.

---

## IMPLEMENTATION STATUS

This PRP documents an **already-shipped** app, not a forward plan — there is no Phase 1/2/3 agent dispatch to run. If you're looking at this because you're about to change the pipeline or its endpoints, the modules above and the file pointers below are the map; there's no scaffold-from-scratch step to redo.

| Area | Status | Key files |
|------|--------|-----------|
| Models + DB shim | Done | `backend/app/models/video.py`, `backend/app/models/clip.py`, `backend/app/database.py` |
| Upload + background pipeline | Done | `backend/app/routers/videos.py`, `backend/app/services/pipeline_service.py` |
| Progress tracking | Done | `Video.progress_stage`/`progress_percent`, polled via `frontend/src/hooks/useVideos.ts` |
| List + detail UI | Done | `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/VideoDetailPage.tsx`, `frontend/src/components/ui/ProgressLoader.tsx` |
| Smoke tests | Done | `backend/tests/test_videos.py` (mocks the pipeline; covers upload/retry/error paths, not Whisper/ffmpeg itself) |
| Docker / CI / auth | Not built (out of scope this build) | — |

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| Backend boots | `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload` (starts, creates/patches `app.db`) |
| Frontend boots | `cd frontend && npm install && npm run dev` |
| Lint/types | `cd backend && ruff check app/ tests/`; `cd frontend && npm run lint && npx tsc -b --noEmit` |
| Smoke tests | `cd backend && pytest tests/ -v` (no `--cov-fail-under`) |
| Manual pipeline run | Upload a real video via `/`, confirm clips appear in `output/{storage_key}/` and play on `/videos/{id}` with correct hook titles |

---

## ENVIRONMENT VARIABLES

```env
# This build (Video Auto Editor MVP)
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key
VITE_API_URL=http://localhost:8000

# Template defaults (NOT used this build — no auth/Postgres/LLM)
# DATABASE_URL=postgresql://user:pass@localhost:5432/db
# GOOGLE_CLIENT_ID=xxx
# GOOGLE_CLIENT_SECRET=xxx
# LLM_API_KEY=xxx
```

---

## ACCEPTANCE CRITERIA

- [x] `POST /api/videos` returns immediately (status=pending) — does not block until the pipeline finishes
- [x] Given a valid upload, the app produces 3–5 clips in `output/{storage_key}/`, with `Video.status`/`progress_stage`/`progress_percent` progressing through transcribing → segmenting → cutting_clips → done
- [x] `/` lists all videos with live status; `/videos/{id}` shows a progress loader while in flight and plays clips with hook titles once done
- [x] Bad extension / oversized upload / >30min video / unreadable file returns a clear 400 error, doesn't crash
- [x] A failed video can be retried from its already-uploaded source file
- [x] `ruff check` and `npm run lint` / `tsc -b` pass — coverage gate skipped for this build

---

## NEXT STEP

There's no `/execute-prp` step left to run — the app described here is already built and running. Use this PRP as the reference map when extending it (e.g. adding YouTube-URL ingestion or an LLM segmentation call as a follow-up module), and update it alongside `INITIAL.md` if the shipped product changes again.
