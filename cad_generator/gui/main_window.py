"""
MainWindow — top-level application window.

Layout:
  ┌─ Sidebar ──────┐ ┌─ Content (QStackedWidget) ──────────────────────────┐
  │ CatalogWidget  │ │ Page 0: Welcome screen                              │
  │                │ │ Page 1: ┌─ ParameterForm ─┐ ┌─ SchematicViewer ──┐  │
  │                │ │         │ (scrollable)    │ │ (dynamic diagram) │  │
  │                │ │         └─────────────────┘ └────────────────────┘  │
  │                │ │ Action bar: [Crear Diseño] [⚙ Generar CAD]          │
  └────────────────┘ └─────────────────────────────────────────────────────┘
  └─ Status bar ────────────────────────────────────────────────────────────┘

Flujo de trabajo:
  1. Doble clic en pieza del catálogo
  2. Page 1 carga ParameterForm + SchematicViewer
  3. Foco en un parámetro → SchematicViewer resalta esa dimensión en el diagrama
  4. Click "Crear Diseño" → NewDesignDialog → design creado en DB
  5. Click "Generar" → _GenerateWorker (QThread) → PieceController.generate() → result dialog
"""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from cad_generator.config.settings import settings
from cad_generator.core.piece_controller import (
    GenerationRequest,
    GenerationResponse,
    PieceController,
)
from cad_generator.gui.catalog_widget import CatalogWidget
from cad_generator.gui.new_design_dialog import NewDesignDialog
from cad_generator.gui.parameter_form import ParameterForm
from cad_generator.gui.schematic_viewer import SchematicViewer


# ---------------------------------------------------------------------------
# Result panel — persistent display after generation (replaces QMessageBox)
# ---------------------------------------------------------------------------

class _ResultPanel(QFrame):
    """
    Shown below the action bar after each generation attempt.
    Displays status, elapsed time, file buttons, and any warnings/errors.
    """

    _STYLE_SUCCESS = (
        "QFrame { background: #F0FFF0; border: 1px solid #4CAF50; "
        "border-radius: 4px; }"
    )
    _STYLE_FAILURE = (
        "QFrame { background: #FFF0F0; border: 1px solid #F44336; "
        "border-radius: 4px; }"
    )

    def __init__(self, controller: "PieceController", parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._fcstd_path: Optional[Path] = None
        self._step_path: Optional[Path] = None
        self._dxf_path: Optional[Path] = None
        self._pdf_path: Optional[Path] = None
        self._bom_xlsx_path: Optional[Path] = None
        self._bom_pdf_path: Optional[Path] = None
        self._output_dir: Optional[Path] = None
        self._design_id: Optional[int] = None
        self._design_name: str = ""
        self._revision_code: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # --- Header row: status text + elapsed time ---
        header_row = QWidget()
        hl = QHBoxLayout(header_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")

        self._elapsed_lbl = QLabel()
        self._elapsed_lbl.setStyleSheet("color: #666; font-size: 11px;")

        hl.addWidget(self._status_lbl)
        hl.addStretch()
        hl.addWidget(self._elapsed_lbl)
        layout.addWidget(header_row)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #CCC;")
        layout.addWidget(sep)

        # --- File buttons row (success only) ---
        self._btn_row = QWidget()
        bl = QHBoxLayout(self._btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        self._btn_fcstd    = QPushButton("📄  FCStd")
        self._btn_step     = QPushButton("📐  STEP")
        self._btn_dxf      = QPushButton("📋  DXF")
        self._btn_pdf      = QPushButton("📑  PDF")
        self._btn_bom_xlsx = QPushButton("📊  BOM Excel")
        self._btn_bom_pdf  = QPushButton("📋  BOM PDF")
        self._btn_folder   = QPushButton("📂  Abrir carpeta")
        self._btn_freecad  = QPushButton("🔧  Abrir en FreeCAD")
        self._btn_zip      = QPushButton("📦  Exportar ZIP")
        self._btn_history  = QPushButton("🕐  Historial")

        for btn in (self._btn_fcstd, self._btn_step, self._btn_dxf,
                    self._btn_pdf, self._btn_bom_xlsx, self._btn_bom_pdf,
                    self._btn_folder, self._btn_freecad,
                    self._btn_zip, self._btn_history):
            btn.setEnabled(False)
            bl.addWidget(btn)
        bl.addStretch()
        layout.addWidget(self._btn_row)

        # --- Messages (warnings or error text) ---
        self._msg_lbl = QLabel()
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setStyleSheet("font-size: 11px;")
        self._msg_lbl.hide()
        layout.addWidget(self._msg_lbl)

        # Wire buttons
        self._btn_fcstd.clicked.connect(
            lambda: os.startfile(str(self._fcstd_path))
            if self._fcstd_path else None
        )
        self._btn_step.clicked.connect(
            lambda: os.startfile(str(self._step_path))
            if self._step_path else None
        )
        self._btn_dxf.clicked.connect(
            lambda: os.startfile(str(self._dxf_path))
            if self._dxf_path else None
        )
        self._btn_pdf.clicked.connect(
            lambda: os.startfile(str(self._pdf_path))
            if self._pdf_path else None
        )
        self._btn_bom_xlsx.clicked.connect(
            lambda: os.startfile(str(self._bom_xlsx_path))
            if self._bom_xlsx_path else None
        )
        self._btn_bom_pdf.clicked.connect(
            lambda: os.startfile(str(self._bom_pdf_path))
            if self._bom_pdf_path else None
        )
        self._btn_folder.clicked.connect(
            lambda: os.startfile(str(self._output_dir))
            if self._output_dir else None
        )
        self._btn_freecad.clicked.connect(self._open_in_freecad)
        self._btn_zip.clicked.connect(self._export_zip)
        self._btn_history.clicked.connect(self._open_history)

        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_result(
        self,
        response: GenerationResponse,
        design_id: Optional[int] = None,
        design_name: str = "",
    ) -> None:
        """Populate with a GenerationResponse and make the panel visible."""
        self._fcstd_path = response.fcstd_path
        self._step_path  = response.step_path
        self._dxf_path      = response.dxf_path
        self._pdf_path      = response.pdf_path
        self._bom_xlsx_path = response.bom_xlsx_path
        self._bom_pdf_path  = response.bom_pdf_path
        self._output_dir    = response.output_dir
        self._design_id     = design_id
        self._design_name   = design_name
        self._revision_code = response.revision_code or ""

        if response.success:
            self.setStyleSheet(self._STYLE_SUCCESS)
            self._status_lbl.setText(
                f"✅  Revisión <b>{response.revision_code}</b> generada correctamente."
            )
            self._status_lbl.setStyleSheet(
                "font-weight: bold; font-size: 12px; color: #2E7D32;"
            )
        else:
            self.setStyleSheet(self._STYLE_FAILURE)
            self._status_lbl.setText("❌  Error en la generación del modelo.")
            self._status_lbl.setStyleSheet(
                "font-weight: bold; font-size: 12px; color: #CC0000;"
            )

        # Elapsed time
        if response.elapsed_seconds:
            self._elapsed_lbl.setText(f"⏱  {response.elapsed_seconds:.1f} s")
        else:
            self._elapsed_lbl.clear()

        # File buttons — only shown on success; enabled when file exists
        self._btn_row.setVisible(response.success)
        if response.success:
            self._btn_fcstd.setEnabled(
                bool(self._fcstd_path and Path(self._fcstd_path).exists())
            )
            self._btn_step.setEnabled(
                bool(self._step_path and Path(self._step_path).exists())
            )
            self._btn_dxf.setEnabled(
                bool(self._dxf_path and Path(self._dxf_path).exists())
            )
            self._btn_pdf.setEnabled(
                bool(self._pdf_path and Path(self._pdf_path).exists())
            )
            self._btn_bom_xlsx.setEnabled(
                bool(self._bom_xlsx_path and Path(self._bom_xlsx_path).exists())
            )
            self._btn_bom_pdf.setEnabled(
                bool(self._bom_pdf_path and Path(self._bom_pdf_path).exists())
            )
            self._btn_folder.setEnabled(
                bool(self._output_dir and Path(self._output_dir).exists())
            )
            self._btn_freecad.setEnabled(
                bool(self._fcstd_path and Path(self._fcstd_path).exists())
            )
            self._btn_zip.setEnabled(bool(self._output_dir))
            self._btn_history.setEnabled(bool(self._design_id is not None))

        # Messages
        msgs: list[str] = []
        if response.success and response.warnings:
            msgs = [f"⚠  {w}" for w in response.warnings]
            self._msg_lbl.setStyleSheet("font-size: 11px; color: #B8600A;")
        elif not response.success:
            msgs = response.errors or ["Error desconocido."]
            self._msg_lbl.setStyleSheet("font-size: 11px; color: #CC0000;")

        if msgs:
            self._msg_lbl.setText("\n".join(msgs))
            self._msg_lbl.show()
        else:
            self._msg_lbl.hide()

        self.show()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _open_in_freecad(self) -> None:
        if not self._fcstd_path:
            return
        freecad_exe = settings.freecad_bin.parent / "FreeCAD.exe"
        if freecad_exe.exists():
            subprocess.Popen([str(freecad_exe), str(self._fcstd_path)])
        else:
            # Fallback: open with default file association
            os.startfile(str(self._fcstd_path))

    def _export_zip(self) -> None:
        """Package all generated output files into a single ZIP archive."""
        files: list[Path] = []
        for p in (self._fcstd_path, self._step_path, self._dxf_path,
                  self._pdf_path, self._bom_xlsx_path, self._bom_pdf_path):
            if p and Path(p).exists():
                files.append(Path(p))

        if not files:
            QMessageBox.information(self, "Exportar ZIP", "No hay archivos para exportar.")
            return

        rev_suffix = f"_rev{self._revision_code}" if self._revision_code else ""
        default_name = f"paquete{rev_suffix}.zip"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar paquete ZIP",
            str(self._output_dir / default_name) if self._output_dir else default_name,
            "Archivo ZIP (*.zip)",
        )
        if not dest:
            return

        try:
            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, f.name)
            QMessageBox.information(
                self, "Exportar ZIP",
                f"Paquete exportado correctamente:\n{dest}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar ZIP", str(exc))

    def _open_history(self) -> None:
        """Open RevisionPanel for the current design."""
        if self._design_id is None:
            return
        from cad_generator.gui.revision_panel import RevisionPanel
        dlg = RevisionPanel(
            design_id=self._design_id,
            design_name=self._design_name,
            controller=self._controller,
            parent=self,
        )
        dlg.exec()


# ---------------------------------------------------------------------------
# Background worker for CAD generation (keeps GUI responsive)
# ---------------------------------------------------------------------------

class _GenerateWorker(QThread):
    """Runs PieceController.generate() in a background thread."""

    finished = pyqtSignal(object)   # emits GenerationResponse

    def __init__(self, controller: PieceController, request: GenerationRequest) -> None:
        super().__init__()
        self._controller = controller
        self._request    = request

    def run(self) -> None:
        response = self._controller.generate(self._request)
        self.finished.emit(response)


# ---------------------------------------------------------------------------
# Welcome page
# ---------------------------------------------------------------------------

class _WelcomePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        icon_lbl = QLabel("📐")
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_lbl.setFont(icon_font)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(settings.app_name)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(18)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "Seleccioná una pieza del catálogo para comenzar."
        )
        subtitle.setStyleSheet("color: #666; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(
            "Doble clic sobre una pieza del árbol lateral → "
            "se cargan sus parámetros aquí."
        )
        hint.setStyleSheet(
            "color: #999; font-size: 12px; "
            "background: #F0F4FF; border-radius: 6px; padding: 10px 16px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        hint.setMaximumWidth(480)

        layout.addWidget(icon_lbl)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(hint)


# ---------------------------------------------------------------------------
# Parameter page (form + action buttons)
# ---------------------------------------------------------------------------

class _ParameterPage(QWidget):
    def __init__(self, controller: PieceController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._current_piece_code: str | None = None
        self._current_design_id: int | None = None
        self._current_design_name: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Horizontal QSplitter: ParameterForm (left) + SchematicViewer (right)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("QSplitter::handle { background-color: #DDD; }")

        self._form = ParameterForm()
        self._form.validation_result_changed.connect(self._on_validation_changed)
        self._form.param_focused.connect(self._on_param_focused)
        self._form.values_changed.connect(self._on_values_changed)
        self._form.setMinimumWidth(300)
        content_splitter.addWidget(self._form)

        self._viewer = SchematicViewer()
        self._viewer.setMinimumWidth(240)
        content_splitter.addWidget(self._viewer)

        content_splitter.setSizes([380, 400])
        content_splitter.setCollapsible(0, False)
        content_splitter.setCollapsible(1, False)
        layout.addWidget(content_splitter)

        # Action bar at bottom
        action_bar = QWidget()
        action_bar.setStyleSheet(
            "background-color: #F7F7F7; border-top: 1px solid #DDD;"
        )
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(16, 8, 16, 8)
        action_layout.setSpacing(8)

        self._design_status_lbl = QLabel("Sin diseño activo")
        self._design_status_lbl.setStyleSheet("color: #888; font-size: 11px;")

        self._btn_new_design = QPushButton("Crear Diseño…")
        self._btn_new_design.setEnabled(False)
        self._btn_new_design.setMinimumWidth(140)
        self._btn_new_design.setToolTip(
            "Crea un nuevo diseño en la base de datos con los parámetros actuales."
        )

        self._btn_generate = QPushButton("⚙  Generar CAD")
        self._btn_generate.setEnabled(False)
        self._btn_generate.setMinimumWidth(140)
        self._btn_generate.setStyleSheet(
            "QPushButton:enabled { background-color: #0070C0; color: white; "
            "border-radius: 4px; font-weight: bold; padding: 6px 12px; } "
            "QPushButton:disabled { background-color: #CCC; color: #888; "
            "border-radius: 4px; padding: 6px 12px; }"
        )
        self._btn_generate.setToolTip("Semana 7+: genera modelo 3D y planos 2D.")

        action_layout.addWidget(self._design_status_lbl)
        action_layout.addStretch()
        action_layout.addWidget(self._btn_new_design)
        action_layout.addWidget(self._btn_generate)
        layout.addWidget(action_bar)

        # Result panel (hidden until first generation)
        self._result_panel = _ResultPanel(controller=self._controller)
        self._result_panel.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._result_panel)

        # Wire signals
        self._btn_new_design.clicked.connect(self._on_create_design)
        self._btn_generate.clicked.connect(self._on_generate)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_piece(self, piece_code: str) -> None:
        self._current_piece_code = piece_code
        self._current_design_id = None
        self._form.load_piece(piece_code)   # auto-emits param_focused for first param
        self._btn_new_design.setEnabled(True)
        self._btn_generate.setEnabled(False)
        self._design_status_lbl.setText("Sin diseño activo")
        # Set explicit initial viewer state in case param_focused fires before
        # the viewer is wired (first load edge-case).
        from cad_generator.config.catalog_loader import catalog as cat
        piece = cat.get_piece(piece_code)
        if piece and piece.parameters:
            self._viewer.set_parameter(
                piece_code, piece.parameters[0].name, self._form.get_values()
            )

    def get_form(self) -> ParameterForm:
        return self._form

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_validation_changed(self, result) -> None:
        """Enable/disable buttons based on validation state."""
        has_piece  = self._current_piece_code is not None
        has_design = self._current_design_id is not None

        self._btn_new_design.setEnabled(has_piece and result.is_valid)

        # Generate requires an active design AND valid parameters
        self._btn_generate.setEnabled(has_design and result.is_valid)

        # Tooltip on Generate shows active warnings when applicable
        if has_design and result.warnings:
            warn_lines = "\n".join(f"⚠  {w.message}" for w in result.warnings)
            self._btn_generate.setToolTip(
                f"Generar modelo 3D — diseño ID {self._current_design_id}\n\n"
                f"Advertencias activas:\n{warn_lines}"
            )
        elif has_design:
            self._btn_generate.setToolTip(
                f"Generar modelo 3D para diseño ID {self._current_design_id}."
            )
        else:
            self._btn_generate.setToolTip(
                "Creá un diseño antes de generar el modelo."
            )

    def _on_param_focused(self, param_name: str) -> None:
        """Relay focus change to SchematicViewer so it highlights that dimension."""
        if self._current_piece_code:
            self._viewer.set_parameter(
                self._current_piece_code, param_name, self._form.get_values()
            )

    def _on_values_changed(self, values: dict) -> None:
        """Keep SchematicViewer geometry in sync when any value changes."""
        self._viewer.set_values(values)

    def _on_create_design(self) -> None:
        if not self._current_piece_code:
            return
        from cad_generator.config.catalog_loader import catalog as cat
        piece = cat.get_piece(self._current_piece_code)
        display_name = piece.display_name if piece else self._current_piece_code

        dlg = NewDesignDialog(piece_display_name=display_name, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        data = dlg.get_data()
        design = self._controller.create_design(
            piece_type_code=self._current_piece_code,
            name=data["name"],
            description=data.get("description", ""),
            drawing_number=data.get("drawing_number"),
        )
        if design is None:
            QMessageBox.critical(
                self, "Error",
                "No se pudo crear el diseño. "
                "Verificá que el número de plano no esté duplicado.",
            )
            return

        self._current_design_id   = design.id
        self._current_design_name = design.name
        drawing_info = (
            f"  [{design.drawing_number}]"
            if design.drawing_number
            else ""
        )
        self._design_status_lbl.setText(
            f"✓  Diseño: {design.name}{drawing_info}"
        )
        self._design_status_lbl.setStyleSheet(
            "color: #2E7D32; font-size: 11px; font-weight: bold;"
        )
        self._btn_generate.setEnabled(True)
        self._btn_generate.setToolTip(
            f"Generar modelo 3D para diseño ID {design.id}."
        )

    def _on_generate(self) -> None:
        if not self._current_design_id:
            return

        request = GenerationRequest(
            design_id=self._current_design_id,
            parameters=self._form.get_values(),
            description="Generado desde GUI",
        )

        # Progress dialog — stays open until the worker emits finished
        progress = QProgressDialog(
            "Generando modelo 3D...", None, 0, 0, self
        )
        progress.setWindowTitle("Generación CAD")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        self._worker = _GenerateWorker(self._controller, request)
        self._worker.finished.connect(
            lambda resp: self._on_generation_finished(resp, progress,
                                                      self._current_design_id,
                                                      self._current_design_name)
        )
        self._worker.start()

    def _on_generation_finished(
        self,
        response: GenerationResponse,
        progress: QProgressDialog,
        design_id: Optional[int] = None,
        design_name: str = "",
    ) -> None:
        progress.close()

        # Show result in the persistent panel (no QMessageBox for generation)
        self._result_panel.show_result(
            response, design_id=design_id, design_name=design_name
        )

        if response.success:
            self._design_status_lbl.setText(
                f"✓  Rev. {response.revision_code} generada"
                + (f"  [{response.elapsed_seconds:.1f}s]" if response.elapsed_seconds else "")
            )
            self._design_status_lbl.setStyleSheet("color: #2E7D32; font-weight: bold;")


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._controller = PieceController()
        self.setWindowTitle(settings.app_name)
        self.setMinimumSize(1100, 720)
        self._build_ui()
        self._build_menu()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central widget with a QSplitter
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #DDDDDD; }")
        root_layout.addWidget(splitter)

        # Left: catalog sidebar
        self._catalog = CatalogWidget()
        self._catalog.setMaximumWidth(280)
        self._catalog.setMinimumWidth(180)
        self._catalog.setStyleSheet("background-color: #F5F5F5;")
        self._catalog.piece_selected.connect(self._on_piece_selected)
        splitter.addWidget(self._catalog)

        # Right: QStackedWidget
        self._stack = QStackedWidget()
        splitter.addWidget(self._stack)

        # Page 0: Welcome
        self._welcome_page = _WelcomePage()
        self._stack.addWidget(self._welcome_page)

        # Page 1: Parameter form
        self._param_page = _ParameterPage(self._controller)
        self._stack.addWidget(self._param_page)

        splitter.setSizes([220, 880])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Listo. Seleccioná una pieza del catálogo para comenzar.")

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # Archivo
        file_menu = menu_bar.addMenu("&Archivo")

        act_new = QAction("&Nuevo diseño…", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.setStatusTip("Crear un nuevo diseño paramétrico.")
        act_new.triggered.connect(self._on_menu_new)
        file_menu.addAction(act_new)

        file_menu.addSeparator()

        act_settings = QAction("⚙  &Configuración…", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.setStatusTip("Configurar empresa, autor y rutas del sistema.")
        act_settings.triggered.connect(self._on_settings)
        file_menu.addAction(act_settings)

        file_menu.addSeparator()

        act_quit = QAction("&Salir", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Vista
        view_menu = menu_bar.addMenu("&Vista")
        act_expand = QAction("Expandir catálogo", self)
        act_expand.triggered.connect(self._catalog._tree.expandAll)
        view_menu.addAction(act_expand)

        act_collapse = QAction("Contraer catálogo", self)
        act_collapse.triggered.connect(self._catalog._tree.collapseAll)
        view_menu.addAction(act_collapse)

        # Ayuda
        help_menu = menu_bar.addMenu("A&yuda")
        act_about = QAction("&Acerca de…", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_piece_selected(self, piece_code: str) -> None:
        from cad_generator.config.catalog_loader import catalog as cat
        piece = cat.get_piece(piece_code)
        display = piece.display_name if piece else piece_code

        self._param_page.load_piece(piece_code)
        self._stack.setCurrentIndex(1)
        self._status_bar.showMessage(
            f"Pieza seleccionada: {display}  —  "
            "Ajustá los parámetros y hacé clic en 'Crear Diseño'."
        )

    def _on_menu_new(self) -> None:
        """Jump to welcome screen so user picks a piece first."""
        self._stack.setCurrentIndex(0)
        self._status_bar.showMessage(
            "Seleccioná una pieza del catálogo para crear un nuevo diseño."
        )

    def _on_settings(self) -> None:
        """Open the application settings dialog."""
        from cad_generator.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"Acerca de {settings.app_name}",
            f"<b>{settings.app_name}</b><br>"
            f"Versión {settings.app_version}<br><br>"
            "Generador paramétrico de modelos CAD 3D y planos 2D.<br>"
            "Motor CAD: FreeCAD 1.0<br>"
            "Estándar de planos: IRAM 4505 / ISO 128<br><br>"
            f"Autor: {settings.default_author}",
        )
