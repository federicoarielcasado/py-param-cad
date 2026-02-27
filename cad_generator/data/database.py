"""
Database engine, session factory, and initialization utilities.

Usage:
    from cad_generator.data.database import get_session, init_db

    init_db()  # call once at application startup

    with get_session() as session:
        design = session.get(Design, 1)
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from cad_generator.config.settings import settings
from cad_generator.data.models import Base

# Module-level engine singleton.
# check_same_thread=False required for SQLite when sessions are created
# in background threads (e.g., during CAD generation subprocess management).
_engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=settings.db_echo,
)


@event.listens_for(_engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record):
    """Enable WAL mode and enforce foreign key constraints on every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


def init_db() -> None:
    """
    Create all tables if they do not exist and seed the piece catalog.
    Safe to call multiple times (idempotent).
    """
    Base.metadata.create_all(_engine)
    _seed_piece_types()


def _seed_piece_types() -> None:
    """Populate piece_types table from piece_catalog.json if the table is empty."""
    import json

    from cad_generator.data.models import PieceType

    with get_session() as session:
        count = session.query(PieceType).count()
        if count > 0:
            return  # already seeded

        catalog_path = settings.catalog_path
        if not catalog_path.exists():
            return  # catalog not yet created; skip silently

        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        for piece_data in data.get("pieces", []):
            pt = PieceType(
                code=piece_data["code"],
                display_name=piece_data["display_name"],
                discipline=piece_data["discipline"],
                category=piece_data["category"],
                description=piece_data.get("description", ""),
                catalog_version=data.get("catalog_version", "1.0"),
            )
            session.add(pt)
        session.commit()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager providing a transactional database session.

    Automatically rolls back on exception and always closes the session.

    Usage:
        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    session = _SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
