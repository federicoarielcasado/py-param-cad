"""
SettingsDialog — persistent application settings editor (Semana 12).

Allows the user to configure:
  - company_name    (shown in all title blocks and BOM headers)
  - default_author  (shown in title blocks and BOM)
  - freecad_bin     (path to freecadcmd.exe)
  - outputs_dir     (folder where generated files are saved)

Changes are persisted to a .env file at the project root so they
survive application restarts (pydantic-settings reads it at import).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cad_generator.config.settings import settings


class SettingsDialog(QDialog):
    """
    Modal dialog for editing persistent application settings.
    Writes to <project_root>/.env on Save.
    Settings take effect after application restart.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de la aplicación")
        self.setMinimumWidth(540)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # ── Empresa y autor ───────────────────────────────────────────
        company_group = QGroupBox("Empresa y autor")
        form = QFormLayout(company_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._company_edit = QLineEdit(settings.company_name)
        self._company_edit.setPlaceholderText("Nombre de la empresa o estudio")
        form.addRow("Nombre de empresa:", self._company_edit)

        self._author_edit = QLineEdit(settings.default_author)
        self._author_edit.setPlaceholderText("Nombre del autor / responsable técnico")
        form.addRow("Autor por defecto:", self._author_edit)

        main_layout.addWidget(company_group)

        # ── Rutas del sistema ─────────────────────────────────────────
        paths_group = QGroupBox("Rutas del sistema")
        paths_form = QFormLayout(paths_group)
        paths_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        paths_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # FreeCAD binary
        freecad_row = QWidget()
        fc_rl = QHBoxLayout(freecad_row)
        fc_rl.setContentsMargins(0, 0, 0, 0)
        fc_rl.setSpacing(4)
        self._freecad_edit = QLineEdit(str(settings.freecad_bin))
        btn_fc = QPushButton("…")
        btn_fc.setFixedWidth(30)
        btn_fc.setToolTip("Seleccionar freecadcmd.exe")
        btn_fc.clicked.connect(self._browse_freecad)
        fc_rl.addWidget(self._freecad_edit)
        fc_rl.addWidget(btn_fc)
        paths_form.addRow("FreeCAD (freecadcmd.exe):", freecad_row)

        # Outputs directory
        out_row = QWidget()
        out_rl = QHBoxLayout(out_row)
        out_rl.setContentsMargins(0, 0, 0, 0)
        out_rl.setSpacing(4)
        self._outputs_edit = QLineEdit(str(settings.outputs_dir))
        btn_out = QPushButton("…")
        btn_out.setFixedWidth(30)
        btn_out.setToolTip("Seleccionar carpeta de salida")
        btn_out.clicked.connect(self._browse_outputs)
        out_rl.addWidget(self._outputs_edit)
        out_rl.addWidget(btn_out)
        paths_form.addRow("Carpeta de salida:", out_row)

        main_layout.addWidget(paths_group)

        # ── Info note ─────────────────────────────────────────────────
        info = QLabel(
            "Los cambios se guardan en <tt>.env</tt> en la carpeta del proyecto "
            "y se aplican al <b>reiniciar la aplicación</b>."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding: 4px 0;")
        main_layout.addWidget(info)

        # ── Dialog buttons ────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _browse_freecad(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar freecadcmd.exe",
            str(Path(self._freecad_edit.text()).parent),
            "Ejecutables (*.exe);;Todos los archivos (*)",
        )
        if path:
            self._freecad_edit.setText(path)

    def _browse_outputs(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de salida",
            self._outputs_edit.text(),
        )
        if path:
            self._outputs_edit.setText(path)

    def _save(self) -> None:
        """Write changed settings to project_root/.env and accept dialog."""
        env_path = settings.project_root / ".env"

        # Read existing .env to preserve unrelated keys
        existing: dict[str, str] = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, _, val = stripped.partition("=")
                    existing[key.strip()] = val.strip()

        # Apply user edits
        existing["CAD_COMPANY_NAME"]   = self._company_edit.text().strip()
        existing["CAD_DEFAULT_AUTHOR"] = self._author_edit.text().strip()
        existing["CAD_FREECAD_BIN"]    = self._freecad_edit.text().strip()
        existing["CAD_OUTPUTS_DIR"]    = self._outputs_edit.text().strip()

        lines = [f"{k}={v}" for k, v in existing.items()]
        try:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Error al guardar",
                f"No se pudo escribir el archivo .env:\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Configuración guardada",
            "Los cambios se aplicarán al reiniciar la aplicación.",
        )
        self.accept()
