# INITIAL.md - Define Your Product

---

## PRODUCT

**Name:** YouTube Auto Editor (MVP)

**Description:** Paste a YouTube URL → the system downloads the video, pulls its transcript, uses one LLM call to identify 3–5 segments (summary / main idea / pain-point-solution), cuts each into a 45–75s 9:16 clip with burned-in captions in the source language, and saves them locally. A single page lists processed videos and lets you preview the generated clips.

**Type:** SaaS (this build = local MVP / proof of concept only — not the production SaaS)

---

## ⚠️ STACK OVERRIDES FOR THIS BUILD

CLAUDE.md's defaults (JWT + Google OAuth + PostgreSQL + Docker + 80% coverage) are for the general template and are **not achievable inside a 60-minute build alongside video processing**. For this MVP only:

| Layer | CLAUDE.md default | This build |
|-------|-------------------|------------|
| Auth | JWT + Google OAuth | **None** — no login, no user model, single local user |
| Database | PostgreSQL + Alembic | **SQLite**, no migrations — schema created on startup |
| Docker | Required | **Skip** — `uvicorn`/`npm run dev` locally only |
| Test coverage | 80%+ | **Skip** — smoke test only (spec says "less edge/error cases") |
| UI | Chakra/Tailwind + Framer Motion | Tailwind, no auth pages, motion optional |

Everything else in CLAUDE.md (type hints, async endpoints, no `print()`/`any`/inline styles, env vars for secrets) still applies.

---

## TECH STACK

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python 3.11+ |
| Frontend | React + TypeScript + Vite |
| Database | SQLite (via SQLAlchemy — same ORM, swappable to Postgres later) |
| Video pipeline | `yt-dlp` (download + captions), `youtube-transcript-api` fallback, `ffmpeg` (cut + caption burn-in) |
| UI | Tailwind |

---

## MODULES

### Module 1: Videos (core)

**Description:** Accepts a YouTube URL, runs the pipeline synchronously (no queue — single request, blocking is fine for MVP), stores the source video's metadata and processing status.

**Models:**
```
Video:
  - id, youtube_url, youtube_id, title
  - status: pending | processing | done | failed
  - error_message (nullable)
  - language
  - created_at
```

**Endpoints:**
```
POST   /api/videos          - Submit a YouTube URL, runs pipeline, returns Video + Clips
GET    /api/videos          - List all processed videos
GET    /api/videos/{id}     - Get one video with its clips
```

**Pages:**
```
/                  - Paste-URL form + list of processed videos
/videos/{id}       - Detail view: video title + its 3–5 clips (player + hook title per clip)
```

---

### Module 2: Clips

**Description:** The generated short-form outputs belonging to a Video.

**Models:**
```
Clip:
  - id, video_id (FK)
  - type: summary | main_idea | pain_point_solution
  - hook_title (string, curiosity-inducing, LLM-generated)
  - start_time, end_time
  - file_path
  - created_at
```

**Endpoints:**
```
GET    /api/videos/{video_id}/clips   - List clips for a video (also embedded in GET /api/videos/{id})
```
No separate clip pages — clips render inline on `/videos/{id}` with an HTML5 `<video>` player per clip.

---

## PIPELINE (inside `POST /api/videos`, as a service — not per-endpoint logic)

1. Validate URL, extract `youtube_id`. Reject if video >30 min (return 400 with message).
2. Download via `yt-dlp` (≤1080p mp4).
3. Get transcript: YouTube captions first; Whisper (`small`, local) only if no captions exist.
4. **One** LLM call with the full timestamped transcript → structured JSON: 3–5 clips, each with `type`, `start`, `end` (45–75s), `hook_title`. Same language as source, no translation.
5. `ffmpeg`: cut each segment, crop/pad to 9:16, burn in captions from the transcript slice.
6. Save to `/output/{youtube_id}/clip_N.mp4`; write `Video` + `Clip` rows to SQLite.
7. On any failure past step 2, mark `status=failed` with `error_message` — don't crash the request.

---

## MVP SCOPE

Must Have:
- [x] Paste YouTube URL → get 3–5 captioned 9:16 clips saved locally
- [x] List page showing processed videos
- [x] Detail page playing each clip with its hook title
- [ ] ~~User registration/login~~ (explicitly out of scope for MVP)

Explicitly out of scope: auth, multi-tenancy, cloud storage, job queue/concurrency, non-YouTube sources, custom templates/branding, background music, translation.

---

## ACCEPTANCE CRITERIA

- [ ] Given a valid YouTube URL, the app produces 3–5 clips in `/output/{youtube_id}/`
- [ ] `/` lists all processed videos; `/videos/{id}` plays their clips with hook titles
- [ ] Invalid URL / no-captions / >30min video returns a clear error, doesn't crash
- [ ] 5–10 sample videos pre-processed and browsable, covering: normal talk, tutorial, and one video with no captions (Whisper fallback path exercised)
- [ ] `ruff check` and `npm run type-check` pass — skip coverage gate for this build

---

## RUN

```bash
/generate-prp INITIAL.md
/execute-prp PRPs/youtube-auto-editor-prp.md
```
