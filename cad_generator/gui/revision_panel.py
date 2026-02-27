"""
RevisionPanel — displays revision history for a design.

Shows a table of all revisions with their codes, timestamps, ECO status,
and generated file links. Allows the user to view parameters of past revisions
and change ECO status (draft → issued → obsolete).

TODO Semana 12: Implement revision history table and ECO controls.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget


class RevisionPanel(QWidget):
    """Revision history panel. Stub for Semana 12."""

    def __init__(self, design_id: int, parent=None) -> None:
        super().__init__(parent)
        self.design_id = design_id
        # TODO: Load revisions from PieceController and display in QTableWidget

    def refresh(self) -> None:
        """Reload revision data from the database."""
        raise NotImplementedError("RevisionPanel — implementar en Semana 12.")
