"""
Tests for the repository layer.
All tests use the in-memory database fixtures from conftest.py.
"""

import pytest

from cad_generator.data.repositories import (
    BOMRepository,
    DesignRepository,
    PieceTypeRepository,
    RevisionRepository,
    _increment_revision_code,
)


# ---------------------------------------------------------------------------
# _increment_revision_code unit tests
# ---------------------------------------------------------------------------

class TestIncrementRevisionCode:

    def test_single_letter(self):
        assert _increment_revision_code("A") == "B"
        assert _increment_revision_code("Y") == "Z"

    def test_wrap_z_to_aa(self):
        assert _increment_revision_code("Z") == "AA"

    def test_double_letter(self):
        assert _increment_revision_code("AA") == "AB"
        assert _increment_revision_code("AZ") == "BA"

    def test_double_z_wrap(self):
        assert _increment_revision_code("ZZ") == "AAA"

    def test_case_insensitive(self):
        assert _increment_revision_code("a") == "B"


# ---------------------------------------------------------------------------
# PieceTypeRepository tests
# ---------------------------------------------------------------------------

class TestPieceTypeRepository:

    def test_get_all_active_returns_seeded_piece(self, seeded_session):
        repo = PieceTypeRepository(seeded_session)
        results = repo.get_all_active()
        assert len(results) == 1
        assert results[0].code == "base_plate"

    def test_get_by_code_found(self, seeded_session):
        repo = PieceTypeRepository(seeded_session)
        pt = repo.get_by_code("base_plate")
        assert pt is not None
        assert pt.display_name == "Placa Base Estructural"

    def test_get_by_code_not_found(self, seeded_session):
        repo = PieceTypeRepository(seeded_session)
        pt = repo.get_by_code("nonexistent")
        assert pt is None

    def test_get_by_discipline(self, seeded_session):
        repo = PieceTypeRepository(seeded_session)
        results = repo.get_by_discipline("structural")
        assert len(results) == 1
        results_empty = repo.get_by_discipline("electrical")
        assert len(results_empty) == 0


# ---------------------------------------------------------------------------
# DesignRepository tests
# ---------------------------------------------------------------------------

class TestDesignRepository:

    def test_create_and_retrieve(self, seeded_session):
        pt = PieceTypeRepository(seeded_session).get_by_code("base_plate")
        repo = DesignRepository(seeded_session)
        design = repo.create(piece_type_id=pt.id, name="Test Design", drawing_number="PB-001")
        seeded_session.commit()

        retrieved = repo.get_by_id(design.id)
        assert retrieved is not None
        assert retrieved.name == "Test Design"
        assert retrieved.drawing_number == "PB-001"

    def test_get_all_returns_created(self, seeded_session):
        pt = PieceTypeRepository(seeded_session).get_by_code("base_plate")
        repo = DesignRepository(seeded_session)
        repo.create(piece_type_id=pt.id, name="Design A")
        repo.create(piece_type_id=pt.id, name="Design B")
        seeded_session.commit()
        assert len(repo.get_all()) == 2

    def test_get_by_id_not_found(self, seeded_session):
        repo = DesignRepository(seeded_session)
        assert repo.get_by_id(9999) is None

    def test_update_name(self, seeded_session):
        pt = PieceTypeRepository(seeded_session).get_by_code("base_plate")
        repo = DesignRepository(seeded_session)
        design = repo.create(piece_type_id=pt.id, name="Original")
        seeded_session.commit()

        repo.update_name(design.id, "Updated")
        seeded_session.commit()
        assert repo.get_by_id(design.id).name == "Updated"

    def test_delete(self, seeded_session):
        pt = PieceTypeRepository(seeded_session).get_by_code("base_plate")
        repo = DesignRepository(seeded_session)
        design = repo.create(piece_type_id=pt.id, name="To Delete")
        seeded_session.commit()

        result = repo.delete(design.id)
        seeded_session.commit()
        assert result is True
        assert repo.get_by_id(design.id) is None


# ---------------------------------------------------------------------------
# RevisionRepository tests
# ---------------------------------------------------------------------------

class TestRevisionRepository:

    def _create_design(self, session):
        pt = PieceTypeRepository(session).get_by_code("base_plate")
        repo = DesignRepository(session)
        design = repo.create(piece_type_id=pt.id, name="Rev Test Design")
        session.commit()
        return design

    def test_revision_codes_increment_sequentially(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)

        rev_a = r_repo.create(design.id, {"largo": 300.0}, description="Initial")
        seeded_session.commit()
        assert rev_a.revision_code == "A"

        rev_b = r_repo.create(design.id, {"largo": 350.0}, description="Updated")
        seeded_session.commit()
        assert rev_b.revision_code == "B"

    def test_parameters_serialized_correctly(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)
        params = {"largo": 300.0, "ancho": 200.0, "espesor": 12.0}
        rev = r_repo.create(design.id, params)
        seeded_session.commit()

        retrieved = r_repo.get_by_id(rev.id)
        assert retrieved.parameters == params

    def test_get_latest_for_design(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)
        r_repo.create(design.id, {"largo": 100.0})
        seeded_session.commit()
        r_repo.create(design.id, {"largo": 200.0})
        seeded_session.commit()

        latest = r_repo.get_latest_for_design(design.id)
        assert latest is not None
        assert latest.revision_code == "B"

    def test_update_eco_status_valid(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)
        rev = r_repo.create(design.id, {"largo": 300.0})
        seeded_session.commit()

        r_repo.update_eco_status(rev.id, "issued", eco_number="ECO-001", eco_reason="Primera emisi\u00f3n.")
        seeded_session.commit()

        updated = r_repo.get_by_id(rev.id)
        assert updated.eco_status == "issued"
        assert updated.eco_number == "ECO-001"

    def test_update_eco_status_invalid_raises(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)
        rev = r_repo.create(design.id, {"largo": 300.0})
        seeded_session.commit()

        with pytest.raises(ValueError, match="eco_status"):
            r_repo.update_eco_status(rev.id, "invalid_status")

    def test_update_output_paths(self, seeded_session):
        design = self._create_design(seeded_session)
        r_repo = RevisionRepository(seeded_session)
        rev = r_repo.create(design.id, {"largo": 300.0})
        seeded_session.commit()

        paths = {
            "fcstd": "/outputs/PB_A.FCStd",
            "step": "/outputs/PB_A.step",
        }
        r_repo.update_output_paths(rev.id, paths)
        seeded_session.commit()

        updated = r_repo.get_by_id(rev.id)
        assert updated.fcstd_path == "/outputs/PB_A.FCStd"
        assert updated.step_path == "/outputs/PB_A.step"
        assert updated.dxf_path is None


# ---------------------------------------------------------------------------
# BOMRepository tests
# ---------------------------------------------------------------------------

class TestBOMRepository:

    def test_create_and_retrieve_items(self, seeded_session):
        pt = PieceTypeRepository(seeded_session).get_by_code("base_plate")
        design = DesignRepository(seeded_session).create(pt.id, "BOM Test")
        seeded_session.commit()

        r_repo = RevisionRepository(seeded_session)
        rev = r_repo.create(design.id, {"largo": 300.0})
        seeded_session.commit()

        bom_repo = BOMRepository(seeded_session)
        items_data = [
            {"description": "Placa Base", "quantity": 1, "material": "ASTM A36"},
            {"description": "Perno M20", "quantity": 4, "unit": "UN"},
        ]
        created = bom_repo.create_items(rev.id, items_data)
        seeded_session.commit()

        assert len(created) == 2
        assert created[0].item_number == 1
        assert created[1].item_number == 2

        retrieved = bom_repo.get_by_revision(rev.id)
        assert len(retrieved) == 2
        assert retrieved[0].description == "Placa Base"
        assert retrieved[1].description == "Perno M20"
