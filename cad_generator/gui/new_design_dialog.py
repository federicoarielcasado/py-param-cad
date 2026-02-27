"""
NewDesignDialog — modal dialog for creating a new design.

Collects:
  - Design name (required)
  - Drawing number (optional, e.g. "PB-001")
  - Description (optional)

Returns the collected data via accepted() signal + get_data().
"""

from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class NewDesignDialog(QDialog):
    """Dialog for entering design metadata before creating a new design."""

    def __init__(self, piece_display_name: str, parent=None) -> None:
        super().__init__(parent)
        self._piece_display_name = piece_display_name
        self.setWindowTitle("Nuevo Diseño")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        header = QLabel(f"Nuevo diseño: {self._piece_display_name}")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(11)
        header.setFont(header_font)
        layout.addWidget(header)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #DDDDDD;")
        layout.addWidget(separator)

        # Form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Name field (required)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Ej: Placa base columna C1")
        self._name_edit.setMinimumWidth(260)
        self._name_error = QLabel("")
        self._name_error.setStyleSheet("color: #CC0000; font-size: 11px;")
        name_widget = QWidget()
        name_layout = QVBoxLayout(name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(2)
        name_layout.addWidget(self._name_edit)
        name_layout.addWidget(self._name_error)
        form.addRow("Nombre *:", name_widget)

        # Drawing number field (optional)
        self._drawing_edit = QLineEdit()
        self._drawing_edit.setPlaceholderText("Ej: PB-001  (opcional)")
        self._drawing_number_error = QLabel("")
        self._drawing_number_error.setStyleSheet("color: #CC0000; font-size: 11px;")
        drawing_widget = QWidget()
        drawing_layout = QVBoxLayout(drawing_widget)
        drawing_layout.setContentsMargins(0, 0, 0, 0)
        drawing_layout.setSpacing(2)
        drawing_layout.addWidget(self._drawing_edit)
        drawing_layout.addWidget(self._drawing_number_error)
        form.addRow("N° de plano:", drawing_widget)

        # Description field (optional)
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Descripción breve del diseño (opcional)")
        self._desc_edit.setFixedHeight(72)
        form.addRow("Descripción:", self._desc_edit)

        layout.addLayout(form)

        # Buttons
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Crear Diseño")
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        # Wire up live validation
        self._name_edit.textChanged.connect(self._validate_fields)
        self._drawing_edit.textChanged.connect(self._validate_fields)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_fields(self) -> None:
        ok = True

        name = self._name_edit.text().strip()
        if not name:
            self._name_error.setText("El nombre es obligatorio.")
            ok = False
        else:
            self._name_error.setText("")

        drawing = self._drawing_edit.text().strip()
        if drawing and not re.match(r"^[A-Za-z0-9\-_]+$", drawing):
            self._drawing_number_error.setText(
                "Solo letras, números, guiones y guiones bajos."
            )
            ok = False
        else:
            self._drawing_number_error.setText("")

        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok and bool(name))

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        self._validate_fields()
        name = self._name_edit.text().strip()
        if not name:
            return
        self.accept()

    def get_data(self) -> dict:
        """Return the collected form data as a dict."""
        drawing = self._drawing_edit.text().strip() or None
        desc = self._desc_edit.toPlainText().strip()
        return {
            "name": self._name_edit.text().strip(),
            "drawing_number": drawing,
            "description": desc,
        }
