# Database Skill

> SQLite + SQLAlchemy, no migrations

This build has no Postgres and no Alembic. `app.db` is a single local SQLite
file; the schema is created on startup and additive column changes are
patched in automatically. There is no `users` table - single-tenant, no auth.

---

## Database Connection

```python
# database.py
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Schema Creation (no migrations)

```python
def create_tables() -> None:
    from app.models import Clip, Video  # lazy import, avoids a circular import
    Base.metadata.create_all(bind=engine)   # creates missing TABLES only
    _add_missing_columns()                  # patches missing COLUMNS on existing tables

def _add_missing_columns() -> None:
    """Best-effort ALTER TABLE ADD COLUMN for columns added to a model after
    an on-disk app.db already exists. Only additive, nullable columns are
    supported - anything more involved needs a real migration tool."""
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            column_type = column.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
```

**Rule of thumb:** a new nullable column on `Video`/`Clip` just works on the
next startup. Anything that isn't additive-and-nullable (renaming a column,
adding a NOT NULL without a default, dropping a column) needs a manual
one-off script or a real migration tool - don't rely on `_add_missing_columns`
for that.

---

## Models

```python
# models/base.py
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

# models/video.py
class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class Video(Base, TimestampMixin):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, index=True, nullable=False)  # output/{storage_key}/
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.PENDING, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="video", cascade="all, delete-orphan")

# models/clip.py
class ClipType(str, enum.Enum):
    SUMMARY = "summary"
    MAIN_IDEA = "main_idea"
    PAIN_POINT_SOLUTION = "pain_point_solution"

class Clip(Base, TimestampMixin):
    __tablename__ = "clips"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[ClipType] = mapped_column(Enum(ClipType), nullable=False)
    hook_title: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    video: Mapped["Video"] = relationship("Video", back_populates="clips")
```

---

## Query Patterns Actually Used

```python
# List, most recent first
db.query(Video).order_by(Video.created_at.desc()).all()

# Fetch one
db.query(Video).filter(Video.id == video_id).first()

# Startup sweep: clear zombie "processing" rows left by a killed/reloaded server
db.query(Video).filter(Video.status == VideoStatus.PROCESSING).all()
```

`clips` loads eagerly via the relationship whenever a `Video` is serialized
through `VideoResponse` - there's no separate paginated clips endpoint, so
no N+1 concern to manage here.

---

## Best Practices (this build)

- New model fields: nullable, with a sensible default - `_add_missing_columns` only handles additive changes.
- No Alembic, no migration files - don't add one unless the schema needs something `_add_missing_columns` can't do.
- `SessionLocal()` opened directly (not via `Depends(get_db)`) in two places outside a request: `main.py`'s startup sweep and the pipeline's background thread - both are outside FastAPI's dependency-injection scope.
- Tests use an in-memory SQLite engine (`sqlite:///:memory:` + `StaticPool`) and monkeypatch `SessionLocal` in both `app.main` and `app.routers.videos` so the background thread and startup hook hit the test DB too.
