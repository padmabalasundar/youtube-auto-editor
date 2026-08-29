"""Database engine, session, and table creation for the SQLite-backed app."""
from collections.abc import Generator

from sqlalchemy import create_engine
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
    """Create all tables from the models' metadata.

    Imported lazily here (rather than at module level) to avoid a circular
    import, since the models import `Base` from this module.
    """
    from app.models import Clip, Video  # noqa: F401

    Base.metadata.create_all(bind=engine)
