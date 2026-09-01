# INITIAL.md - Define Your Product

---

## PRODUCT

**Name:** Video Auto Editor (MVP)

**Description:** Upload a video file → the system transcribes it locally with Whisper, picks 3–5 segments (summary / main idea / pain-point-solution) with a heuristic (no LLM call), and cuts each into a 45–75s 9:16 clip (no captions burned in), saving them locally. A single page lists processed videos and lets you preview the generated clips as small, grid-laid-out players.

**Type:** SaaS (this build = local MVP / proof of concept only — not the production SaaS)

---

## ⚠️ STACK OVERRIDES FOR THIS BUILD

CLAUDE.md's defaults (JWT + Google OAuth + PostgreSQL + Docker + 80% coverage) are for the general template and are **not achievable inside a 60-minute build alongside video processing**. For this MVP only:

| Layer | CLAUDE.md default | This build |
|-------|-------------------|------------|
| Auth | JWT + Google OAuth | **None** — no login, no user model, single local user |
| Database | PostgreSQL + Alembic | **SQLite**, no formal migrations — schema created on startup, with a lightweight `ALTER TABLE ADD COLUMN` shim for additive model changes |
| Docker | Required | **Skip** — `uvicorn`/`npm run dev` locally only |
| Test coverage | 80%+ | **Skip** — smoke test only (spec says "less edge/error cases") |
| UI | Chakra/Tailwind + Framer Motion | Tailwind only, no auth pages, CSS-only animation (no motion library) |

Everything else in CLAUDE.md (type hints, async endpoints, no `print()`/`any`/inline styles, env vars for secrets) still applies.

---

## TECH STACK

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python 3.11+ |
| Frontend | React + TypeScript + Vite |
| Database | SQLite (via SQLAlchemy — same ORM, swappable to Postgres later) |
| Video pipeline | `faster-whisper` (CTranslate2, int8, CPU transcription), `ffmpeg`/`ffprobe` (duration probe, cut + crop to 9:16) |
| UI | Tailwind |

There is **no YouTube ingestion and no LLM call** in this build: the source video is a direct file upload, and clip boundaries come from an evenly-spaced heuristic over the transcript rather than an LLM segmentation call. Both are candidates for a later iteration, not this MVP.

---

## MODULES

### Module 1: Videos (core)

**Description:** Accepts an uploaded video file, validates it (extension, size, duration), runs the pipeline as a background task (not inline in the request), and stores the source video's metadata, processing status, and live progress.

**Models:**
```
Video:
  - id, original_filename, storage_key, title
  - status: pending | processing | done | failed
  - progress_stage: transcribing | segmenting | cutting_clips | done (nullable)
  - progress_percent: 0-100 (nullable)
  - error_message (nullable)
  - language (nullable — set from Whisper's detected/forced language once transcription finishes)
  - created_at
```

**Endpoints:**
```
POST   /api/videos              - Upload a video file (multipart/form-data). Validates
                                   extension + size while streaming to disk, probes duration
                                   via ffprobe (rejects >30min with 400), creates Video
                                   (status=pending), starts the pipeline on a background
                                   thread with its own DB session, and returns immediately
                                   with the Video row. Does NOT block on the pipeline.
GET    /api/videos              - List all videos, most recent first. Frontend polls this
                                   every 3s while any video is pending/processing.
GET    /api/videos/{id}         - Get one video (current status, live progress, clips once
                                   done) — polled by the detail page every 3s while in flight.
POST   /api/videos/{id}/retry   - Reprocess a video from its already-uploaded source file
                                   (no re-upload needed) if the original processing failed.
```

**Pages:**
```
/                  - Upload form + list of videos with live status/progress badges
/videos/{id}       - Detail view: animated progress loader while pending/processing (stage
                     label, percent, shimmering bar), or the video's clips once done
```

---

### Module 2: Clips

**Description:** The generated short-form outputs belonging to a Video. Embedded in `GET /api/videos/{id}` rather than fetched separately — there is no standalone clips endpoint.

**Models:**
```
Clip:
  - id, video_id (FK)
  - type: summary | main_idea | pain_point_solution
  - hook_title (string — the first sentence-ish chunk of the clip's own transcript text)
  - start_time, end_time
  - file_path
  - created_at
```

No separate clip pages — clips render inline on `/videos/{id}` with an HTML5 `<video>` player per clip, served from the mounted `/output` static directory.

---

## PIPELINE — ASYNC WITH LIVE PROGRESS

**Request flow:**
1. `POST /api/videos` streams the upload to disk (rejecting anything over the size cap mid-stream), validates the extension, probes duration via `ffprobe`, rejects videos over 30 minutes with a 400, creates the `Video` row with `status=pending`, and **returns immediately** with that row.
2. The pipeline runs on a plain daemon `threading.Thread` with its own SQLAlchemy session (not FastAPI `BackgroundTasks`) — this keeps a many-minutes Whisper/ffmpeg run fully off Starlette's request threadpool so it never competes with other concurrent requests.
3. The frontend polls `GET /api/videos/{id}` (and the list `GET /api/videos` while anything is in flight) every 3s and stops once `status` is `done` or `failed`.

**Pipeline stages (update `Video.status`/`progress_stage`/`progress_percent` as they progress):**
1. `transcribing` (0–70%) — `faster-whisper` ("small", `compute_type=int8`, forced `language=ta`, `beam_size=1`, `vad_filter=True`, `condition_on_previous_text=False`) transcribes the uploaded file directly; there are no YouTube captions to fall back from, so this always runs. Progress is computed per-segment as the transcript is produced.
2. `segmenting` (→70%) — evenly-spaced ~60s windows are picked across the video (up to 5 clips), cycling through `summary` → `main_idea` → `pain_point_solution` slots, then validated against a 45–75s duration window with slack.
3. `cutting_clips` (70–100%) — `ffmpeg` cuts each clip in parallel (bounded by CPU core count), using input-side `-ss` (fast keyframe seek) rather than output-side seeking, and crops/pads to 9:16 (no caption burn-in — kept off the video track entirely, both for speed and per product feedback); saves to `output/{storage_key}/clip_N.mp4` and writes `Clip` rows. Progress advances per clip completed.
4. `done` (100%) — all clips saved and queryable.
5. `failed` (from any stage) — sets `error_message`, never crashes the background thread or the app; a stuck `processing` row left behind by a server restart is swept to `failed` on the next startup.

**Startup:** the Whisper model loads once (lazily, on first use) and is cached in-process for the life of the server, so only the very first upload pays the model-load cost.

---

## MVP SCOPE

Must Have:
- [x] Upload a video file → get 3–5 9:16 clips (no captions) saved locally
- [x] Upload returns immediately; pipeline runs in the background with live status/progress
- [x] List page showing videos with live status/progress
- [x] Detail page with an animated progress loader while processing, and clip playback with hook titles once done
- [x] Retry a failed video without re-uploading
- [ ] ~~User registration/login~~ (explicitly out of scope for MVP)

Explicitly out of scope: auth, multi-tenancy, cloud storage, job queue/concurrency beyond a background thread, YouTube or other remote sources, an LLM segmentation call, custom templates/branding, background music, translation, languages other than the hardcoded forced Tamil (`language="ta"`).

---

## ACCEPTANCE CRITERIA

- [x] `POST /api/videos` returns immediately (status=pending) — does not block until the pipeline finishes
- [x] Given a valid upload, the app produces 3–5 clips in `output/{storage_key}/`, with `Video.status`/`progress_stage`/`progress_percent` progressing through transcribing → segmenting → cutting_clips → done
- [x] `/` lists all videos with live status; `/videos/{id}` shows a progress loader while in flight and plays clips with hook titles once done
- [x] Bad extension / oversized upload / >30min video / unreadable file returns a clear 400 error, doesn't crash
- [x] A failed video can be retried from its already-uploaded source file
- [x] `ruff check` and `npm run lint` / `tsc -b` pass — skip coverage gate for this build

---

## RUN

```bash
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```
