"""
DXFGenerator — 2D drawing generation using ezdxf.

Generates DXF files with standard views (top, front, side, isometric),
IRAM 4505 title block, dimensions, tolerances, and technical notes.

TODO Semana 10: Implement DXF generation and PDF export.
"""

from __future__ import annotations

from pathlib import Path


class DXFGenerator:
    """Generates 2D DXF drawings from revision data. Stub for Semana 10."""

    def generate(
        self,
        revision_id: int,
        parameters: dict,
        output_path: Path,
        drawing_number: str = "",
        revision_code: str = "A",
    ) -> bool:
        """
        Generate a DXF drawing file.

        Returns True on success.
        TODO Semana 10: implement with ezdxf + IRAM 4505 title block.
        """
        raise NotImplementedError(
            "Generaci\u00f3n DXF — implementar en Semana 10 con ezdxf."
        )

    def export_pdf(self, dxf_path: Path, pdf_path: Path) -> bool:
        """Convert a DXF to PDF. Returns True on success."""
        raise NotImplementedError(
            "Exportaci\u00f3n PDF — implementar en Semana 10."
        )
