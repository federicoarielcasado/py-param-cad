"""
pytest fixtures shared across all tests.

Uses an in-memory SQLite database for fast, isolated test runs.
Each test function gets a fresh database with seeded piece types.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cad_generator.data.models import Base, PieceType


@pytest.fixture(scope="function")
def db_engine():
    """In-memory SQLite engine, fresh per test function."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Transactional session; rolls back after each test."""
    SessionFactory = sessionmaker(bind=db_engine)
    session = SessionFactory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def seeded_session(db_session):
    """Session with one PieceType (base_plate) pre-loaded."""
    now = datetime.now(timezone.utc).isoformat()
    pt = PieceType(
        code="base_plate",
        display_name="Placa Base Estructural",
        discipline="structural",
        category="base",
        description="Placa base para anclaje estructural.",
        catalog_version="1.0",
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(pt)
    db_session.commit()
    yield db_session
