"""
Tests for SQLAlchemy ORM models.
Verifies model properties, serialization, and constraints.
"""

import json

import pytest

from cad_generator.data.models import BOMItem, Design, PieceType, Revision


class TestRevisionParametersProperty:

    def test_parameters_setter_serializes_to_json(self, db_session):
        now = "2026-01-01T00:00:00+00:00"
        pt = PieceType(
            code="test_piece",
            display_name="Test",
            discipline="structural",
            category="base",
            catalog_version="1.0",
            created_at=now,
            updated_at=now,
        )
        db_session.add(pt)
        db_session.flush()

        design = Design(
            piece_type_id=pt.id,
            name="Test Design",
            created_at=now,
            updated_at=now,
        )
        db_session.add(design)
        db_session.flush()

        rev = Revision(
            design_id=design.id,
            revision_code="A",
            generated_at=now,
            generated_by="Fede",
        )
        params = {"largo": 300.0, "ancho": 200.0, "tiene_ranuras": False}
        rev.parameters = params
        db_session.add(rev)
        db_session.commit()

        retrieved = db_session.get(Revision, rev.id)
        assert retrieved.parameters == params
        # Verify JSON is actually stored as text
        assert isinstance(retrieved.parameters_json, str)
        assert json.loads(retrieved.parameters_json) == params

    def test_validation_warnings_empty_list_when_null(self, db_session):
        now = "2026-01-01T00:00:00+00:00"
        pt = PieceType(
            code="test_piece2",
            display_name="Test2",
            discipline="structural",
            category="base",
            catalog_version="1.0",
            created_at=now,
            updated_at=now,
        )
        db_session.add(pt)
        design = Design(
            piece_type_id=None,
            name="x",
            created_at=now,
            updated_at=now,
        )
        # Just test the property directly without persisting
        rev = Revision(
            design_id=1,
            revision_code="A",
            parameters_json="{}",
            generated_at=now,
            generated_by="Fede",
            validation_warnings_json=None,
        )
        assert rev.validation_warnings == []


class TestBOMItemTotalWeight:

    def test_total_weight_computed_correctly(self):
        item = BOMItem(
            revision_id=1,
            item_number=1,
            description="Placa",
            quantity=2.0,
            unit_weight_kg=5.5,
        )
        assert item.total_weight_kg == pytest.approx(11.0)

    def test_total_weight_none_when_unit_weight_missing(self):
        item = BOMItem(
            revision_id=1,
            item_number=1,
            description="Perno",
            quantity=4.0,
            unit_weight_kg=None,
        )
        assert item.total_weight_kg is None
