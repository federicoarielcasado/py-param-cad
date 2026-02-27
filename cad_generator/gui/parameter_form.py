"""
ParameterForm — dynamic parametric input form.

Builds a QScrollArea with a QFormLayout populated entirely from the
piece_catalog.json parameter definitions for a given piece_code.

Widget types per parameter type:
  float → QDoubleSpinBox  (min / max / step from catalog)
  enum  → QComboBox       (options list from catalog)
  bool  → QCheckBox

Conditional visibility:
  Parameters with a depends_on dict are shown/hidden when the controlling
  parameter changes value.

Real-time validation:
  On every widget change, ValidationEngine is called and the result is
  rendered below the form as colored messages (errors red, warnings orange).

Signals:
  values_changed(dict)             — emitted on any parameter change
  validation_result_changed(object)— emitted with ValidationResult
  param_focused(str)               — emitted with param_name when a widget
                                     receives focus (drives SchematicViewer)
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cad_generator.config.catalog_loader import ParameterSpec, catalog
from cad_generator.core.validation_engine import ValidationEngine, ValidationResult


# ---------------------------------------------------------------------------
# Styled validation message label
# ---------------------------------------------------------------------------

_STYLE_ERROR   = "color: #CC0000; font-size: 11px; padding: 2px 0;"
_STYLE_WARNING = "color: #B8600A; font-size: 11px; padding: 2px 0;"
_STYLE_OK      = "color: #2E7D32; font-size: 11px; padding: 2px 0;"


class _ValidationPanel(QWidget):
    """Displays a list of validation messages below the form."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 0)
        self._layout.setSpacing(2)
        self._labels: list[QLabel] = []

    def update(self, result: Optional[ValidationResult]) -> None:  # type: ignore[override]
        for lbl in self._labels:
            self._layout.removeWidget(lbl)
            lbl.deleteLater()
        self._labels.clear()

        if result is None:
            return

        if result.is_valid and not result.warnings:
            lbl = QLabel("✓  Todos los parámetros son válidos.")
            lbl.setStyleSheet(_STYLE_OK)
            self._layout.addWidget(lbl)
            self._labels.append(lbl)
            return

        for msg in result.errors:
            lbl = QLabel(f"✗  {msg.message}")
            lbl.setStyleSheet(_STYLE_ERROR)
            lbl.setWordWrap(True)
            self._layout.addWidget(lbl)
            self._labels.append(lbl)

        for msg in result.warnings:
            lbl = QLabel(f"⚠  {msg.message}")
            lbl.setStyleSheet(_STYLE_WARNING)
            lbl.setWordWrap(True)
            self._layout.addWidget(lbl)
            self._labels.append(lbl)


# ---------------------------------------------------------------------------
# Main ParameterForm widget
# ---------------------------------------------------------------------------

class ParameterForm(QWidget):
    """
    Parametric input form for a single piece type.
    Load a new piece with load_piece(piece_code).
    """

    values_changed           = pyqtSignal(dict)
    validation_result_changed = pyqtSignal(object)   # ValidationResult
    param_focused            = pyqtSignal(str)        # param_name when focused

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._piece_code: Optional[str] = None
        self._params: list[ParameterSpec] = []
        self._widgets: dict[str, QWidget] = {}       # param_name → input widget
        self._row_widgets: dict[str, QWidget] = {}   # param_name → row container
        self._focused_param: Optional[str] = None
        self._validation_engine = ValidationEngine()
        self._last_result: Optional[ValidationResult] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_piece(self, piece_code: str) -> None:
        """Load parameter form for the given piece code."""
        self._piece_code = piece_code
        self._params = catalog.get_parameters(piece_code)
        self._rebuild_form()

    def get_values(self) -> dict:
        """Return current parameter values as {name: value}."""
        values = {}
        for spec in self._params:
            widget = self._widgets.get(spec.name)
            if widget is None:
                values[spec.name] = spec.default
            elif spec.type == "float":
                values[spec.name] = widget.value()
            elif spec.type == "enum":
                values[spec.name] = widget.currentData()
            elif spec.type == "bool":
                values[spec.name] = widget.isChecked()
        return values

    def set_values(self, values: dict) -> None:
        """Populate form from a dict of {param_name: value}."""
        self._block_signals(True)
        for name, value in values.items():
            widget = self._widgets.get(name)
            if widget is None:
                continue
            spec = self._get_spec(name)
            if spec is None:
                continue
            if spec.type == "float":
                widget.setValue(float(value))
            elif spec.type == "enum":
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif spec.type == "bool":
                widget.setChecked(bool(value))
        self._block_signals(False)
        self._on_any_change()

    def get_focused_param(self) -> Optional[str]:
        return self._focused_param

    def get_last_validation_result(self) -> Optional[ValidationResult]:
        return self._last_result

    # ------------------------------------------------------------------
    # Event filter — detects focus on any input widget
    # ------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            for name, widget in self._widgets.items():
                if widget is watched:
                    self._focused_param = name
                    self.param_focused.emit(name)
                    break
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._form_container = QWidget()
        self._form_layout = QFormLayout(self._form_container)
        self._form_layout.setSpacing(10)
        self._form_layout.setContentsMargins(16, 12, 16, 12)
        self._form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self._scroll.setWidget(self._form_container)
        outer.addWidget(self._scroll)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #DDDDDD;")
        outer.addWidget(sep)
        self._sep = sep

        self._val_panel = _ValidationPanel()
        self._val_panel.setContentsMargins(16, 0, 16, 8)
        outer.addWidget(self._val_panel)

        self._placeholder = QLabel(
            "Seleccioná una pieza del catálogo\npara ver sus parámetros."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #999; font-size: 14px;")
        outer.addWidget(self._placeholder)

        self._scroll.hide()
        sep.hide()
        self._val_panel.hide()

    def _rebuild_form(self) -> None:
        """Clear and repopulate the form for the current piece."""
        while self._form_layout.rowCount() > 0:
            self._form_layout.removeRow(0)
        self._widgets.clear()
        self._row_widgets.clear()
        self._focused_param = None

        if not self._params:
            return

        # Title
        piece = catalog.get_piece(self._piece_code)
        if piece:
            title_lbl = QLabel(piece.display_name)
            f = QFont()
            f.setBold(True)
            f.setPointSize(12)
            title_lbl.setFont(f)
            self._form_layout.addRow(title_lbl)

        # One row per parameter
        first_widget: Optional[QWidget] = None
        for spec in self._params:
            widget = self._create_widget(spec)
            self._widgets[spec.name] = widget
            widget.installEventFilter(self)   # focus tracking

            label_text = spec.display_name + (f"  [{spec.unit}]" if spec.unit else "")
            label = QLabel(label_text + ":")
            label.setToolTip(spec.description)

            row_container = QWidget()
            rl = QVBoxLayout(row_container)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(2)
            rl.addWidget(widget)
            if spec.description:
                desc_lbl = QLabel(spec.description)
                desc_lbl.setStyleSheet("color: #666; font-size: 10px;")
                desc_lbl.setWordWrap(True)
                rl.addWidget(desc_lbl)

            self._form_layout.addRow(label, row_container)
            self._row_widgets[spec.name] = row_container

            # Change signals
            if spec.type == "float":
                widget.valueChanged.connect(self._on_any_change)
            elif spec.type == "enum":
                widget.currentIndexChanged.connect(self._on_any_change)
            elif spec.type == "bool":
                widget.stateChanged.connect(self._on_any_change)

            if first_widget is None:
                first_widget = widget

        # Show form
        self._placeholder.hide()
        self._scroll.show()
        self._sep.show()
        self._val_panel.show()

        # Initial pass
        self._on_any_change()
        self._update_depends_on_visibility()

        # Auto-focus first parameter → drives initial schematic view
        if first_widget is not None:
            first_widget.setFocus()
            first_param = self._params[0].name if self._params else None
            if first_param:
                self._focused_param = first_param
                self.param_focused.emit(first_param)

    def _create_widget(self, spec: ParameterSpec) -> QWidget:
        if spec.type == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(1)
            if spec.min is not None:
                spin.setMinimum(spec.min)
            if spec.max is not None:
                spin.setMaximum(spec.max)
            if spec.step is not None:
                spin.setSingleStep(spec.step)
            spin.setValue(spec.default if spec.default is not None else 0.0)
            spin.setSuffix(f"  {spec.unit}" if spec.unit else "")
            spin.setMinimumWidth(160)
            return spin

        elif spec.type == "enum":
            combo = QComboBox()
            for opt in spec.options:
                combo.addItem(opt.label, userData=opt.value)
            default_idx = combo.findData(spec.default)
            if default_idx >= 0:
                combo.setCurrentIndex(default_idx)
            combo.setMinimumWidth(220)
            return combo

        elif spec.type == "bool":
            check = QCheckBox()
            check.setChecked(bool(spec.default))
            return check

        else:
            lbl = QLabel(str(spec.default))
            lbl.setStyleSheet("color: #888;")
            return lbl

    # ------------------------------------------------------------------
    # Change handling & validation
    # ------------------------------------------------------------------

    def _on_any_change(self) -> None:
        values = self.get_values()
        self._update_depends_on_visibility()

        if self._piece_code:
            rules = catalog.get_validation_rules(self._piece_code)
            self._last_result = self._validation_engine.validate(values, rules)
            self._val_panel.update(self._last_result)
            self.validation_result_changed.emit(self._last_result)

        self.values_changed.emit(values)

    def _update_depends_on_visibility(self) -> None:
        current_values = self.get_values()
        for spec in self._params:
            if not spec.depends_on:
                continue
            row_container = self._row_widgets.get(spec.name)
            if row_container is None:
                continue
            visible = all(
                current_values.get(key) == required_value
                for key, required_value in spec.depends_on.items()
            )
            row_container.setVisible(visible)
            self._set_label_visibility(spec.name, visible)

    def _set_label_visibility(self, param_name: str, visible: bool) -> None:
        for i in range(self._form_layout.rowCount()):
            field_item = self._form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            label_item = self._form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if field_item and field_item.widget() is self._row_widgets.get(param_name):
                if label_item and label_item.widget():
                    label_item.widget().setVisible(visible)
                break

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_spec(self, name: str) -> Optional[ParameterSpec]:
        return next((s for s in self._params if s.name == name), None)

    def _block_signals(self, block: bool) -> None:
        for widget in self._widgets.values():
            widget.blockSignals(block)
