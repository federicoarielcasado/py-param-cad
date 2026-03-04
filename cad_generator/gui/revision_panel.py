"""
RevisionPanel — displays full revision history for a design (Semana 12).

Shows a table of all revisions with their codes, timestamps, ECO status,
weight, file links and description.  Allows the user to advance ECO
status (draft → issued → obsolete) via an in-table combo box.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from cad_generator.core.piece_controller import PieceController


# ECO status display labels and allowed forward transitions
_ECO_LABELS: dict[str, str] = {
    "draft":    "Borrador",
    "issued":   "Emitido",
    "obsolete": "Obsoleto",
}

_ECO_NEXT: dict[str, list[str]] = {
    "draft":    ["draft", "issued"],
    "issued":   ["issued", "obsolete"],
    "obsolete": ["obsolete"],
}

_ECO_STYLE: dict[str, str] = {
    "draft":    "color: #555;",
    "issued":   "color: #1565C0; font-weight: bold;",
    "obsolete": "color: #B71C1C;",
}


class RevisionPanel(QDialog):
    """
    Modal dialog showing the full revision history for one design.

    Usage:
        dlg = RevisionPanel(design_id, design_name, controller, parent)
        dlg.exec()
    """

    def __init__(
        self,
        design_id: int,
        design_name: str,
        controller: PieceController,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._design_id  = design_id
        self._controller = controller
        self.setWindowTitle(f"Historial de revisiones — {design_name}")
        self.setMinimumSize(900, 400)
        self.resize(960, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Header ───────────────────────────────────────────────────
        header_lbl = QLabel(
            f"<b>Diseño:</b> {design_name}"
            "  |  doble clic en una fila para ver sus parámetros."
        )
        header_lbl.setStyleSheet("font-size: 11px; color: #333; padding: 2px 0;")
        layout.addWidget(header_lbl)

        # ── Table ────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Rev.",
            "Fecha generación",
            "Generado por",
            "Estado ECO",
            "Peso total (kg)",
            "Archivos",
            "Descripción",
            "Notas",
        ])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)

        # Fixed column widths (last column stretches)
        col_widths = [42, 148, 90, 110, 105, 220, 120]
        for col, w in enumerate(col_widths):
            self._table.setColumnWidth(col, w)

        layout.addWidget(self._table)

        # ── Footer ───────────────────────────────────────────────────
        footer = QHBoxLayout()
        info_lbl = QLabel(
            "💡  El estado ECO solo puede avanzar: "
            "<b>Borrador</b> → <b>Emitido</b> → <b>Obsoleto</b>."
        )
        info_lbl.setStyleSheet("color: #666; font-size: 11px;")
        footer.addWidget(info_lbl)
        footer.addStretch()

        btn_refresh = QPushButton("🔄  Actualizar")
        btn_refresh.clicked.connect(self.refresh)
        footer.addWidget(btn_refresh)

        btn_close = QPushButton("Cerrar")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload revision data from DB and repopulate the table."""
        revisions = self._controller.get_revisions_for_design(self._design_id)
        self._table.setRowCount(len(revisions))

        for row, rev in enumerate(revisions):

            # Col 0 — Rev. code
            item_rev = QTableWidgetItem(rev.revision_code)
            item_rev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rev.setData(Qt.ItemDataRole.UserRole, rev.id)
            self._table.setItem(row, 0, item_rev)

            # Col 1 — Fecha generación (ISO → readable)
            dt_raw = rev.generated_at or ""
            dt_str = dt_raw[:19].replace("T", "  ") if len(dt_raw) >= 19 else dt_raw
            self._table.setItem(row, 1, QTableWidgetItem(dt_str))

            # Col 2 — Generado por
            self._table.setItem(row, 2, QTableWidgetItem(rev.generated_by or "—"))

            # Col 3 — Estado ECO (combo with allowed transitions)
            combo = self._build_eco_combo(rev.id, rev.eco_status)
            self._table.setCellWidget(row, 3, combo)

            # Col 4 — Peso total
            peso_str = self._get_peso_str(rev.id)
            item_peso = QTableWidgetItem(peso_str)
            item_peso.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 4, item_peso)

            # Col 5 — Archivos (compact open buttons)
            self._table.setCellWidget(row, 5, self._build_file_buttons(rev))

            # Col 6 — Descripción
            self._table.setItem(row, 6, QTableWidgetItem(rev.description or ""))

            # Col 7 — ECO notas
            eco_note = ""
            if rev.eco_number:
                eco_note += f"ECO #{rev.eco_number}"
            if rev.eco_reason:
                sep = " · " if eco_note else ""
                eco_note += sep + rev.eco_reason
            self._table.setItem(row, 7, QTableWidgetItem(eco_note))

        self._table.resizeRowsToContents()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_eco_combo(self, revision_id: int, current_status: str) -> QComboBox:
        """Return a QComboBox pre-populated with allowed forward ECO transitions."""
        combo = QComboBox()
        allowed = _ECO_NEXT.get(current_status, [current_status])
        for status in allowed:
            combo.addItem(_ECO_LABELS.get(status, status), status)
        # Select the current value
        idx = combo.findData(current_status)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setStyleSheet(_ECO_STYLE.get(current_status, ""))

        def _on_change(_index: int, rid: int = revision_id, cb: QComboBox = combo) -> None:
            new_status = cb.currentData()
            if new_status != current_status:
                self._apply_eco_change(rid, new_status, cb)

        combo.currentIndexChanged.connect(_on_change)
        return combo

    def _apply_eco_change(
        self, revision_id: int, new_status: str, combo: QComboBox
    ) -> None:
        """Persist ECO status change to DB."""
        from cad_generator.data.database import get_session
        from cad_generator.data.repositories import RevisionRepository

        try:
            with get_session() as session:
                RevisionRepository(session).update_eco_status(revision_id, new_status)
                session.commit()
            combo.setStyleSheet(_ECO_STYLE.get(new_status, ""))
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Error ECO",
                f"No se pudo actualizar el estado ECO:\n{exc}",
            )

    def _get_peso_str(self, revision_id: int) -> str:
        """Return total weight string from BOM items for this revision."""
        from cad_generator.data.database import get_session
        from cad_generator.data.repositories import BOMRepository

        try:
            with get_session() as session:
                items = BOMRepository(session).get_by_revision(revision_id)
                total = sum(
                    (it.unit_weight_kg or 0.0) * it.quantity
                    for it in items
                    if it.unit_weight_kg is not None
                )
                if total > 0:
                    return f"{total:.3f}"
        except Exception:
            pass
        return "—"

    def _build_file_buttons(self, rev) -> QWidget:
        """Build a compact row of file-open buttons for available output files."""
        container = QWidget()
        hl = QHBoxLayout(container)
        hl.setContentsMargins(2, 1, 2, 1)
        hl.setSpacing(2)

        def _add(label: str, path_str: Optional[str]) -> None:
            if not path_str:
                return
            p = Path(path_str)
            if p.exists():
                btn = QPushButton(label)
                btn.setFixedWidth(44)
                btn.setFixedHeight(20)
                btn.setToolTip(str(p))
                btn.setStyleSheet("font-size: 10px; padding: 1px 2px;")
                btn.clicked.connect(lambda _c=False, _p=p: os.startfile(str(_p)))
                hl.addWidget(btn)

        _add("FCStd", rev.fcstd_path)
        _add("STEP",  rev.step_path)
        _add("DXF",   rev.dxf_path)
        _add("PDF",   rev.pdf_path)
        _add("BOM",   rev.bom_xlsx_path)
        hl.addStretch()
        return container
