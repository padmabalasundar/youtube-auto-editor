"""Database engine, session, and table creation for the SQLite-backed app."""
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""



def get_db() -> Generator[Session, None, None]:
    """Yield a database session, closing it once the request is done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables from the models' metadata, then patch in any new columns.

    Imported lazily here (rather than at module level) to avoid a circular
    import, since the models import `Base` from this module.
    """
    from app.models import Clip, Video  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Best-effort `ALTER TABLE ... ADD COLUMN` for columns added to a model
    after a local `app.db` already exists.

    This build has no migration system (SQLite, schema created on startup) -
    `create_all` only creates missing *tables*, not missing columns on an
    existing one, so without this an older on-disk `app.db` would keep
    failing every query the moment a model gains a new column. Only additive,
    nullable columns are supported; anything more involved needs a real
    migration tool.
    """
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            column_type = column.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
