"""
Tests for DXFDrawingGenerator — Semana 10.

Covers:
  - Sheet & scale selection logic
  - Hole position helpers
  - DrawingContext defaults
  - DXF file creation (integration, no FreeCAD needed)
  - PDF fallback warning when matplotlib is absent
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cad_generator.drawing.dxf_generator import (
    DrawingContext,
    DXFDrawingGenerator,
    _hole_positions,
    _pick_sheet_and_scale,
)


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

_PARAMS_SMALL: dict = {
    "largo":  200.0,
    "ancho":  150.0,
    "espesor": 12.0,
    "material": "a36",
    "patron_perforaciones": "rectangular_4",
    "diametro_perforacion": 18.0,
    "margen_perforacion":   30.0,
    "tiene_ranuras": False,
    "ancho_ranura":  12.0,
    "largo_ranura":  40.0,
}

_PARAMS_LARGE: dict = {
    **_PARAMS_SMALL,
    "largo": 1500.0,
    "ancho":  900.0,
}


def _ctx(**overrides) -> DrawingContext:
    defaults = dict(
        piece_code="base_plate",
        piece_display_name="Placa Base Estructural",
        drawing_number="PL-001",
        revision_code="A",
        author="Test",
        company_name="TestCo",
        material_label="Acero A36",
    )
    defaults.update(overrides)
    return DrawingContext(**defaults)


# ---------------------------------------------------------------------------
# Sheet & scale selection
# ---------------------------------------------------------------------------

class TestPickSheetAndScale:

    def test_small_plate_fits_a4_1to1(self):
        # 100×50×5 mm: w_views=130≤262, h_total=100≤125 → fits A4 1:1
        sheet, denom = _pick_sheet_and_scale(100.0, 50.0, 5.0)
        assert sheet == "A4"
        assert denom == 1

    def test_returns_valid_sheet_name(self):
        sheet, _ = _pick_sheet_and_scale(400.0, 300.0, 15.0)
        assert sheet in ("A4", "A3", "A2", "A1")

    def test_returns_valid_denominator(self):
        _, denom = _pick_sheet_and_scale(400.0, 300.0, 15.0)
        assert denom in (1, 2, 5, 10, 20, 50)

    def test_large_plate_uses_higher_denom_or_bigger_sheet(self):
        sheet, denom = _pick_sheet_and_scale(1500.0, 900.0, 15.0)
        # Must need scale-down or a larger sheet
        assert denom >= 5 or sheet in ("A2", "A1")

    def test_very_large_plate_fallback(self):
        sheet, denom = _pick_sheet_and_scale(5000.0, 3000.0, 50.0)
        assert denom <= 50  # never exceeds defined scale list


# ---------------------------------------------------------------------------
# Hole positions
# ---------------------------------------------------------------------------

class TestHolePositions:

    def test_none_returns_empty(self):
        assert _hole_positions("none", 300.0, 200.0, 30.0) == []

    def test_rectangular_4_gives_four_holes(self):
        holes = _hole_positions("rectangular_4", 300.0, 200.0, 30.0)
        assert len(holes) == 4

    def test_rectangular_6_gives_six_holes(self):
        holes = _hole_positions("rectangular_6", 300.0, 200.0, 30.0)
        assert len(holes) == 6

    def test_lineal_2_gives_two_holes(self):
        holes = _hole_positions("lineal_2", 300.0, 200.0, 30.0)
        assert len(holes) == 2

    def test_personalizado_fallback_four_holes(self):
        holes = _hole_positions("personalizado", 300.0, 200.0, 30.0)
        assert len(holes) == 4

    def test_rectangular_4_corner_positions(self):
        e = 30.0
        L, W = 300.0, 200.0
        holes = _hole_positions("rectangular_4", L, W, e)
        assert (e, e) in holes
        assert (L - e, e) in holes
        assert (e, W - e) in holes
        assert (L - e, W - e) in holes

    def test_lineal_2_centered_y(self):
        e = 30.0
        L, W = 300.0, 200.0
        holes = _hole_positions("lineal_2", L, W, e)
        for _, hy in holes:
            assert hy == pytest.approx(W / 2)


# ---------------------------------------------------------------------------
# DrawingContext defaults
# ---------------------------------------------------------------------------

class TestDrawingContext:

    def test_date_str_auto_filled_when_empty(self):
        ctx = DrawingContext(
            piece_code="base_plate",
            piece_display_name="Placa Base",
            drawing_number="PL-001",
            revision_code="A",
            author="Fede",
            company_name="",
            material_label="Acero",
        )
        assert ctx.date_str != ""

    def test_date_str_format_is_ddmmyyyy(self):
        ctx = _ctx()
        parts = ctx.date_str.split("/")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_custom_date_str_preserved(self):
        ctx = _ctx(date_str="15/06/2026")
        assert ctx.date_str == "15/06/2026"

    def test_standard_default(self):
        ctx = _ctx()
        assert "IRAM" in ctx.standard or "ISO" in ctx.standard


# ---------------------------------------------------------------------------
# DXF file generation (integration, no FreeCAD dependency)
# ---------------------------------------------------------------------------

class TestDXFGeneration:

    def test_base_plate_creates_dxf_file(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_PARAMS_SMALL,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success
        assert result.dxf_path is not None
        assert result.dxf_path.exists()
        assert result.dxf_path.suffix == ".dxf"

    def test_result_has_sheet_format(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_PARAMS_SMALL,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.sheet_format in ("A4", "A3", "A2", "A1")

    def test_result_has_scale_string(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_PARAMS_SMALL,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert ":" in result.scale  # e.g. "1:1", "1:5"

    def test_large_plate_generates_dxf(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_PARAMS_LARGE,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success
        assert result.dxf_path.exists()

    def test_no_holes_variant(self, tmp_path):
        params = {**_PARAMS_SMALL, "patron_perforaciones": "none"}
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=params,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success

    def test_with_slots(self, tmp_path):
        params = {**_PARAMS_SMALL, "tiene_ranuras": True}
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=params,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success

    def test_rectangular_6_holes(self, tmp_path):
        params = {**_PARAMS_SMALL, "patron_perforaciones": "rectangular_6"}
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=params,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success

    def test_lineal_2_holes(self, tmp_path):
        params = {**_PARAMS_SMALL, "patron_perforaciones": "lineal_2"}
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=params,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="A"),
        )
        assert result.success

    def test_revision_code_appears_in_filename(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_PARAMS_SMALL,
            output_dir=tmp_path,
            ctx=_ctx(revision_code="C"),
        )
        assert "C" in result.dxf_path.name

    def test_unsupported_piece_returns_failure(self, tmp_path):
        result = DXFDrawingGenerator().generate(
            piece_code="unknown_piece_xyz",
            parameters=_PARAMS_SMALL,
            output_dir=tmp_path,
            ctx=_ctx(piece_code="unknown_piece_xyz"),
        )
        assert not result.success
        assert result.error_message is not None

    def test_pdf_warning_when_matplotlib_absent(self, tmp_path):
        """
        When matplotlib cannot be imported the DXF must still succeed,
        pdf_path must be None, and at least one warning must be issued.
        """
        # Block matplotlib so _export_pdf hits the ImportError branch
        mock_modules = {
            "matplotlib": None,
            "matplotlib.pyplot": None,
            "ezdxf.addons.drawing.matplotlib": None,
        }
        with patch.dict(sys.modules, mock_modules):
            result = DXFDrawingGenerator().generate(
                piece_code="base_plate",
                parameters=_PARAMS_SMALL,
                output_dir=tmp_path,
                ctx=_ctx(revision_code="A"),
            )

        assert result.success                        # DXF must succeed
        assert result.dxf_path is not None
        assert result.dxf_path.exists()
        assert result.pdf_path is None               # PDF skipped
        assert len(result.warnings) > 0             # warning issued
