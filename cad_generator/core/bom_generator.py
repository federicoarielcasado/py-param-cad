"""
BOMGenerator — Bill of Materials generation from revision data.

TODO Week 11: Implement Excel (.xlsx) and PDF export.
"""

from __future__ import annotations


class BOMGenerator:
    """Generates BOM exports from revision data. Stub for Week 11."""

    def generate_xlsx(self, revision_id: int, output_path) -> bool:
        """Export BOM to Excel. Returns True on success."""
        raise NotImplementedError("BOM Excel export — implementar en Semana 11.")

    def generate_pdf(self, revision_id: int, output_path) -> bool:
        """Export BOM to PDF. Returns True on success."""
        raise NotImplementedError("BOM PDF export — implementar en Semana 11.")
