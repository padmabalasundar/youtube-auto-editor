# CLAUDE.md - Project Rules

> Rules Claude follows in every conversation.

---

## ⚠️ Current Build Override (Video Auto Editor MVP)

This project's default stack (below) is for the general template. The **current build** (see `INITIAL.md`) is a 60-minute local MVP with no user accounts, so these defaults are overridden until stated otherwise:

| Layer | Template default | This build |
|-------|-------------------|------------|
| Auth | JWT + Google OAuth | **None** — no login, single local user |
| Database | PostgreSQL + Alembic | **SQLite**, schema created on startup, no migrations |
| Docker | Required | **Skip** — run locally via `uvicorn` / `npm run dev` |
| Test coverage | 80%+ | **Skip** — smoke test only |

All other rules below (type hints, async endpoints, forbidden patterns, env vars for secrets) still apply. Revert this table to the template defaults before building the real multi-tenant SaaS.

---

## Tech Stack

- **Backend:** FastAPI + Python 3.11+
- **Frontend:** React + TypeScript + Vite
- **Database:** PostgreSQL + SQLAlchemy *(this build: SQLite + SQLAlchemy — see override above)*
- **Auth:** JWT + Google OAuth *(this build: none — see override above)*
- **UI:** Chakra UI or Tailwind + Framer Motion
- **Video pipeline** *(this build only)*: `faster-whisper`, `ffmpeg`

---

## Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py
│   │   ├── models/, schemas/, routers/, services/, auth/
│   ├── alembic/         # unused this build (SQLite, no migrations)
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/, pages/, hooks/, services/, context/, types/
├── output/              # generated clips, this build only
├── skills/               # 5 skill files
├── agents/               # Agent definitions
└── .claude/commands/     # /generate-prp, /execute-prp
```

---

## Code Standards

### Python
```python
# Type hints required
def get_user(db: Session, user_id: int) -> User:
    pass

# Async endpoints
@router.get("/users/{id}")
async def get_user(id: int, db: Session = Depends(get_db)):
    pass
```

### TypeScript
```typescript
// Interfaces required - NO any types
interface User { id: number; email: string; }

const fetchUser = async (id: number): Promise<User> => { ... };
```

---

## Forbidden

- `print()` → use `logging`
- Plain passwords → use bcrypt *(n/a this build — no auth)*
- Hardcoded secrets → use env vars
- `any` type in TypeScript
- `console.log` in production
- Inline styles → use UI framework

---

## Workflow

```
1. Edit INITIAL.md (define product)
2. /generate-prp INITIAL.md
3. /execute-prp PRPs/[name]-prp.md
```

---

## Skills

| Task | Skill |
|------|-------|
| API + Auth | `skills/BACKEND.md` *(auth section unused this build)* |
| React + UI | `skills/FRONTEND.md` |
| Models | `skills/DATABASE.md` |
| Tests | `skills/TESTING.md` |
| Docker | `skills/DEPLOYMENT.md` *(unused this build)* |

---

## Agents

| Agent | Role |
|-------|------|
| DATABASE-AGENT | Models — SQLite this build, no migrations |
| BACKEND-AGENT | API — no auth this build; owns the video pipeline service |
| FRONTEND-AGENT | UI + pages — no login/register pages this build |
| DEVOPS-AGENT | Not used this build (no Docker) |

---

## Validation

```bash
ruff check backend/ && pytest    # smoke tests only this build
npm run lint && npm run type-check
# docker-compose build            # skip this build
```

---

## Environment Variables

```env
# This build (Video Auto Editor MVP)
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key
VITE_API_URL=http://localhost:8000

# Template defaults (not used this build)
# DATABASE_URL=postgresql://user:pass@localhost:5432/db
# GOOGLE_CLIENT_ID=xxx
# GOOGLE_CLIENT_SECRET=xxx
```
