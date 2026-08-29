"""Shared FastAPI dependencies.

Local single-user MVP: no authentication, so this module only re-exports
the database session dependency.
"""
from app.database import get_db

__all__ = ["get_db"]
