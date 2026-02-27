"""
Tests for PieceController.generate() — full pipeline with mocked CAD engine.

These are integration-ish tests: the real DB logic (repositories, models)
runs against an in-memory SQLite, while the FreeCAD subprocess is replaced
by a MagicMock so the test suite has no FreeCAD dependency.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cad_generator.cad.base_engine import GenerationResult
from cad_generator.core.piece_controller import (
    GenerationRequest,
    GenerationResponse,
    PieceController,
)
from cad_generator.data.models import Base, Design, PieceType, Revision


# ---------------------------------------------------------------------------
# Shared parameter sets
# ---------------------------------------------------------------------------

VALID_PARAMS: dict = {
    "largo": 300.0,
    "ancho": 200.0,
    "espesor": 12.0,
    "material": "ASTM_A36",
    "patron_perforaciones": "rectangular_4",
    "diametro_perforacion": 18.0,
    "margen_perforacion": 30.0,
    "tiene_ranuras": False,
    "ancho_ranura": 12.0,
    "largo_ranura": 40.0,
    "acabado_superficial": "laminado_caliente",
}

# These violate VR-BP-01 (espesor < 4) and VR-BP-04 (margen < 1.5 * d)
INVALID_PARAMS: dict = {
    **VALID_PARAMS,
    "espesor": 1.0,
    "margen_perforacion": 5.0,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
    """Fresh in-memory SQLite engine with schema created and one PieceType seeded."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False)

    now = datetime.now(timezone.utc).isoformat()
    with Factory() as s:
        s.add(PieceType(
            code="base_plate",
            display_name="Placa Base Estructural",
            discipline="structural",
            category="base",
            description="Placa base.",
            catalog_version="1.0",
            is_active=1,
            created_at=now,
            updated_at=now,
        ))
        s.commit()

    yield Factory

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def patched_controller(in_memory_db, tmp_path):
    """
    Returns a factory(mock_engine) -> PieceController configured to:
      - use the in-memory test DB (via patched get_session)
      - write outputs to tmp_path (via patched settings)
      - delegate CAD generation to the supplied mock engine
    """
    @contextmanager
    def _session():
        s = in_memory_db()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    mock_settings = MagicMock()
    mock_settings.outputs_dir = tmp_path

    def make_controller(mock_engine: MagicMock) -> PieceController:
        ctrl = PieceController()
        ctrl._engine = mock_engine
        return ctrl

    # Keep the patches active for the whole test via yield inside a with-block
    with (
        patch("cad_generator.core.piece_controller.get_session", _session),
        patch("cad_generator.core.piece_controller.settings", mock_settings),
    ):
        yield make_controller, in_memory_db


# ---------------------------------------------------------------------------
# Helper to insert a Design directly into the test DB
# ---------------------------------------------------------------------------

def _insert_design(factory, design_name: str = "Placa Test") -> int:
    """Insert a Design row linked to the base_plate piece type. Returns design.id."""
    with factory() as s:
        pt = s.query(PieceType).filter_by(code="base_plate").first()
        d = Design(piece_type_id=pt.id, name=design_name, description="")
        s.add(d)
        s.commit()
        return d.id


# ---------------------------------------------------------------------------
# Mock engine factories
# ---------------------------------------------------------------------------

def _success_engine(tmp_path: Path, revision_code: str = "A") -> MagicMock:
    fcstd = tmp_path / f"base_plate_{revision_code}.FCStd"
    step  = tmp_path / f"base_plate_{revision_code}.step"
    fcstd.touch()
    step.touch()
    eng = MagicMock()
    eng.generate.return_value = GenerationResult(
        success=True, fcstd_path=fcstd, step_path=step, warnings=[]
    )
    eng.is_available.return_value = True
    eng.get_engine_name.return_value = "MockEngine"
    return eng


def _failure_engine() -> MagicMock:
    eng = MagicMock()
    eng.generate.return_value = GenerationResult(
        success=False, error_message="Fallo simulado del motor CAD."
    )
    eng.is_available.return_value = True
    eng.get_engine_name.return_value = "MockEngine"
    return eng


# ---------------------------------------------------------------------------
# Tests: invalid parameters  (abort before any DB write or CAD call)
# ---------------------------------------------------------------------------

class TestGenerateInvalidParams:

    def test_returns_failure_with_errors(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=INVALID_PARAMS)
        )

        assert response.success is False
        assert len(response.errors) > 0

    def test_cad_engine_not_called(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        ctrl.generate(GenerationRequest(design_id=design_id, parameters=INVALID_PARAMS))

        eng.generate.assert_not_called()

    def test_no_revision_created_in_db(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        ctrl.generate(GenerationRequest(design_id=design_id, parameters=INVALID_PARAMS))

        with factory() as s:
            count = s.query(Revision).filter_by(design_id=design_id).count()
        assert count == 0


# ---------------------------------------------------------------------------
# Tests: design not found
# ---------------------------------------------------------------------------

class TestGenerateDesignNotFound:

    def test_nonexistent_design_returns_error(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        response = ctrl.generate(
            GenerationRequest(design_id=99999, parameters=VALID_PARAMS)
        )

        assert response.success is False
        assert "no encontrado" in response.errors[0].lower()

    def test_cad_engine_not_called_when_design_missing(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        ctrl.generate(GenerationRequest(design_id=99999, parameters=VALID_PARAMS))

        eng.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: successful generation
# ---------------------------------------------------------------------------

class TestGenerateSuccess:

    def test_response_is_successful(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_success_engine(tmp_path))

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        assert response.success is True

    def test_first_revision_code_is_A(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_success_engine(tmp_path))

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        assert response.revision_code == "A"

    def test_second_generation_increments_to_B(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        eng = _success_engine(tmp_path)
        # Override generate to always return success (paths don't matter for code test)
        eng.generate.return_value = GenerationResult(success=True, warnings=[])
        ctrl = make_ctrl(eng)

        resp1 = ctrl.generate(GenerationRequest(design_id=design_id, parameters=VALID_PARAMS))
        resp2 = ctrl.generate(GenerationRequest(design_id=design_id, parameters=VALID_PARAMS))

        assert resp1.revision_code == "A"
        assert resp2.revision_code == "B"

    def test_revision_persisted_in_db(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_success_engine(tmp_path))

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        with factory() as s:
            rev = s.get(Revision, response.revision_id)
        assert rev is not None
        assert rev.revision_code == "A"

    def test_validation_passed_flag_set(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_success_engine(tmp_path))

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        with factory() as s:
            rev = s.get(Revision, response.revision_id)
        assert rev.validation_passed == 1

    def test_output_paths_stored_in_db(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_success_engine(tmp_path))

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        with factory() as s:
            rev = s.get(Revision, response.revision_id)
        assert rev.fcstd_path is not None
        assert rev.step_path is not None

    def test_cad_engine_called_with_correct_args(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        eng = _success_engine(tmp_path)
        ctrl = make_ctrl(eng)

        ctrl.generate(GenerationRequest(design_id=design_id, parameters=VALID_PARAMS))

        kw = eng.generate.call_args.kwargs
        assert kw["piece_code"] == "base_plate"
        assert kw["parameters"] == VALID_PARAMS
        assert kw["revision_code"] == "A"


# ---------------------------------------------------------------------------
# Tests: CAD engine failure  (revision still created for traceability)
# ---------------------------------------------------------------------------

class TestGenerateCADFailure:

    def test_response_is_failure(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_failure_engine())

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        assert response.success is False

    def test_error_message_forwarded(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_failure_engine())

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        assert "Fallo simulado" in response.errors[0]

    def test_revision_still_created_for_traceability(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_failure_engine())

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        with factory() as s:
            rev = s.get(Revision, response.revision_id)
        assert rev is not None

    def test_output_paths_null_on_cad_failure(self, patched_controller, tmp_path):
        make_ctrl, factory = patched_controller
        design_id = _insert_design(factory)
        ctrl = make_ctrl(_failure_engine())

        response = ctrl.generate(
            GenerationRequest(design_id=design_id, parameters=VALID_PARAMS)
        )

        with factory() as s:
            rev = s.get(Revision, response.revision_id)
        assert rev.fcstd_path is None
        assert rev.step_path is None
