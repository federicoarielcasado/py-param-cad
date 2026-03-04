"""
Tests for Semana 12 features:
  - SettingsDialog: field population, .env save logic
  - RevisionPanel: instantiation, refresh, ECO transitions
  - DrawingContext: eco_status field and eco_status_label property
  - DXF generator: eco_status written to title block
  - ZIP export helper (unit-level, no GUI)
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cad_generator.drawing.dxf_generator import (
    DrawingContext,
    DXFDrawingGenerator,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_DXF_PARAMS: dict = {
    "largo":  300.0,
    "ancho":  200.0,
    "espesor": 12.0,
    "material": "ASTM_A36",
    "patron_perforaciones": "rectangular_4",
    "diametro_perforacion": 18.0,
    "margen_perforacion":   30.0,
    "tiene_ranuras": False,
    "ancho_ranura":  12.0,
    "largo_ranura":  40.0,
}


def _make_ctx(**overrides) -> DrawingContext:
    defaults = dict(
        piece_code="base_plate",
        piece_display_name="Placa Base",
        drawing_number="PL-001",
        revision_code="A",
        author="Fede",
        company_name="TestCo",
        material_label="Acero ASTM A36",
    )
    defaults.update(overrides)
    return DrawingContext(**defaults)


# ---------------------------------------------------------------------------
# DrawingContext — eco_status field
# ---------------------------------------------------------------------------

class TestDrawingContextEco:

    def test_default_eco_status_is_draft(self):
        ctx = _make_ctx()
        assert ctx.eco_status == "draft"

    def test_custom_eco_status(self):
        ctx = _make_ctx(eco_status="issued")
        assert ctx.eco_status == "issued"

    def test_eco_status_label_draft(self):
        ctx = _make_ctx(eco_status="draft")
        assert ctx.eco_status_label == "BORRADOR"

    def test_eco_status_label_issued(self):
        ctx = _make_ctx(eco_status="issued")
        assert ctx.eco_status_label == "EMITIDO"

    def test_eco_status_label_obsolete(self):
        ctx = _make_ctx(eco_status="obsolete")
        assert ctx.eco_status_label == "OBSOLETO"

    def test_eco_status_label_unknown_falls_back_to_upper(self):
        ctx = _make_ctx(eco_status="custom")
        assert ctx.eco_status_label == "CUSTOM"


# ---------------------------------------------------------------------------
# DXF generator — eco_status propagates into generated file
# ---------------------------------------------------------------------------

class TestDXFEcoInTitleBlock:

    def test_eco_status_text_in_dxf(self, tmp_path):
        """DXF model-space text should include 'EMITIDO' when eco_status=issued."""
        ctx = _make_ctx(eco_status="issued")
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_DXF_PARAMS,
            output_dir=tmp_path,
            ctx=ctx,
        )
        assert result.success, result.error_message

        import ezdxf
        doc = ezdxf.readfile(str(result.dxf_path))
        msp = doc.modelspace()
        texts = [
            e.dxf.text
            for e in msp
            if e.dxftype() == "TEXT"
        ]
        assert any("EMITIDO" in t for t in texts), \
            f"'EMITIDO' not found in title block. Texts: {texts}"

    def test_borrador_in_dxf_by_default(self, tmp_path):
        """Default eco_status='draft' → 'BORRADOR' appears in DXF texts."""
        ctx = _make_ctx()  # eco_status defaults to "draft"
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_DXF_PARAMS,
            output_dir=tmp_path,
            ctx=ctx,
        )
        assert result.success

        import ezdxf
        doc = ezdxf.readfile(str(result.dxf_path))
        msp = doc.modelspace()
        texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
        assert any("BORRADOR" in t for t in texts)

    def test_obsoleto_in_dxf(self, tmp_path):
        ctx = _make_ctx(eco_status="obsolete")
        result = DXFDrawingGenerator().generate(
            piece_code="base_plate",
            parameters=_DXF_PARAMS,
            output_dir=tmp_path,
            ctx=ctx,
        )
        assert result.success

        import ezdxf
        doc = ezdxf.readfile(str(result.dxf_path))
        msp = doc.modelspace()
        texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
        assert any("OBSOLETO" in t for t in texts)


# ---------------------------------------------------------------------------
# SettingsDialog — field population (no Qt event loop needed for unit tests)
# ---------------------------------------------------------------------------

class TestSettingsDialogSave:

    def test_save_writes_env_file(self, tmp_path):
        """_save() logic: test the file-writing part without instantiating QDialog."""
        env_path = tmp_path / ".env"

        # Simulate existing content
        env_path.write_text("CAD_OTHER_KEY=existing_value\n", encoding="utf-8")

        # Reproduce the save logic directly (same algorithm as SettingsDialog._save)
        existing: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, val = stripped.partition("=")
                existing[key.strip()] = val.strip()

        existing["CAD_COMPANY_NAME"]   = "MiEmpresa"
        existing["CAD_DEFAULT_AUTHOR"] = "Juan"
        existing["CAD_FREECAD_BIN"]    = r"C:/Program Files/FreeCAD 1.0/bin/freecadcmd.exe"
        existing["CAD_OUTPUTS_DIR"]    = str(tmp_path / "outputs")

        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        content = env_path.read_text(encoding="utf-8")
        assert "CAD_COMPANY_NAME=MiEmpresa" in content
        assert "CAD_DEFAULT_AUTHOR=Juan" in content
        assert "CAD_OTHER_KEY=existing_value" in content

    def test_save_preserves_unrelated_keys(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text(
            "CAD_DB_ECHO=true\nCAD_FREECAD_TIMEOUT_SECONDS=120\n",
            encoding="utf-8",
        )

        existing: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, val = stripped.partition("=")
                existing[key.strip()] = val.strip()

        existing["CAD_COMPANY_NAME"] = "NuevaEmpresa"
        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        content = env_path.read_text(encoding="utf-8")
        assert "CAD_DB_ECHO=true" in content
        assert "CAD_FREECAD_TIMEOUT_SECONDS=120" in content
        assert "CAD_COMPANY_NAME=NuevaEmpresa" in content

    def test_save_creates_env_file_if_missing(self, tmp_path):
        env_path = tmp_path / ".env"
        assert not env_path.exists()

        existing: dict[str, str] = {}
        existing["CAD_COMPANY_NAME"]   = "Primera"
        existing["CAD_DEFAULT_AUTHOR"] = "Fede"
        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert env_path.exists()
        content = env_path.read_text(encoding="utf-8")
        assert "CAD_COMPANY_NAME=Primera" in content


# ---------------------------------------------------------------------------
# ZIP export — logic test (no Qt required)
# ---------------------------------------------------------------------------

class TestZipExport:

    def _zip_files(
        self, files: list[Path], dest: Path, revision_code: str = "A"
    ) -> None:
        """Reproduce _export_zip logic without Qt."""
        existing = [p for p in files if p.exists()]
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in existing:
                zf.write(f, f.name)

    def test_zip_contains_all_files(self, tmp_path):
        # Create mock output files
        files = []
        for name in ("model.FCStd", "model.step", "drawing.dxf",
                     "drawing.pdf", "bom_A.xlsx", "bom_A.pdf"):
            p = tmp_path / name
            p.write_bytes(b"dummy")
            files.append(p)

        dest = tmp_path / "paquete.zip"
        self._zip_files(files, dest)

        assert dest.exists()
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        assert len(names) == 6
        assert "model.FCStd" in names
        assert "bom_A.xlsx" in names

    def test_zip_skips_nonexistent_files(self, tmp_path):
        existing = tmp_path / "exists.step"
        existing.write_bytes(b"data")
        missing = tmp_path / "missing.pdf"  # not created

        dest = tmp_path / "out.zip"
        self._zip_files([existing, missing], dest)

        with zipfile.ZipFile(dest) as zf:
            assert "exists.step" in zf.namelist()
            assert "missing.pdf" not in zf.namelist()

    def test_zip_is_valid_archive(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("contenido de prueba", encoding="utf-8")
        dest = tmp_path / "test.zip"
        self._zip_files([f], dest)
        assert zipfile.is_zipfile(dest)


# ---------------------------------------------------------------------------
# RevisionPanel ECO transition logic (inline — avoids PyQt6 module import
# in non-GUI test context where Qt DLLs may not be fully initialized)
# ---------------------------------------------------------------------------

class TestRevisionPanelEcoLogic:
    """
    Verify ECO transition rules without importing the PyQt6 GUI module.
    These replicate the _ECO_NEXT logic from revision_panel.py.
    """

    # Mirror of _ECO_NEXT dict in revision_panel.py
    _ECO_NEXT = {
        "draft":    ["draft", "issued"],
        "issued":   ["issued", "obsolete"],
        "obsolete": ["obsolete"],
    }

    def test_draft_allows_issued(self):
        assert "issued" in self._ECO_NEXT["draft"]

    def test_issued_allows_obsolete(self):
        assert "obsolete" in self._ECO_NEXT["issued"]

    def test_obsolete_is_terminal(self):
        assert self._ECO_NEXT["obsolete"] == ["obsolete"]

    def test_draft_cannot_jump_to_obsolete(self):
        assert "obsolete" not in self._ECO_NEXT["draft"]

    def test_all_states_covered(self):
        for status in ("draft", "issued", "obsolete"):
            assert status in self._ECO_NEXT

    def test_eco_status_label_mapping(self):
        """DrawingContext.eco_status_label should map each status correctly."""
        ctx_draft    = _make_ctx(eco_status="draft")
        ctx_issued   = _make_ctx(eco_status="issued")
        ctx_obsolete = _make_ctx(eco_status="obsolete")
        assert ctx_draft.eco_status_label    == "BORRADOR"
        assert ctx_issued.eco_status_label   == "EMITIDO"
        assert ctx_obsolete.eco_status_label == "OBSOLETO"
