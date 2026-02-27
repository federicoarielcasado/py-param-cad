"""
SchematicViewer — parameter schematic display.

Shows a parametric 2D diagram of the selected piece, highlighting the
currently focused parameter with colored annotations (arrows + labels).

Priority:
  1. If a PNG file exists at assets/schematics/<piece_code>/<param_name>.png
     → display that static image (user-provided professional illustration).
  2. Otherwise → render a dynamic QPainter diagram.

Currently implemented dynamic diagrams:
  - base_plate: top-view with holes, slots, dimension annotations.

Usage:
    viewer = SchematicViewer()
    viewer.set_parameter("base_plate", "largo", {"largo": 300.0, "ancho": 200.0, ...})
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from cad_generator.config.catalog_loader import catalog
from cad_generator.config.settings import settings

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
_C_PLATE     = QColor("#CFD8DC")
_C_PLATE_OUT = QColor("#546E7A")
_C_HOLE      = QColor("#FFFFFF")
_C_HOLE_OUT  = QColor("#37474F")
_C_SLOT      = QColor("#B0BEC5")
_C_SLOT_OUT  = QColor("#546E7A")
_C_ANNOT     = QColor("#E65100")     # active parameter annotations
_C_DIM       = QColor("#1565C0")     # dimension arrows
_C_BG        = QColor("#FAFAFA")


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _arrowhead(
    painter: QPainter,
    x: float, y: float,
    angle: float,
    color: QColor,
    size: float = 7,
) -> None:
    spread = 0.38
    p1 = QPointF(x - size * math.cos(angle - spread), y - size * math.sin(angle - spread))
    p2 = QPointF(x - size * math.cos(angle + spread), y - size * math.sin(angle + spread))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPolygon(QPolygonF([QPointF(x, y), p1, p2]))


def _dim_arrow(
    painter: QPainter,
    x1: float, y1: float,
    x2: float, y2: float,
    label: str,
    color: QColor = _C_DIM,
    offset: float = 0.0,
    font_size: int = 9,
) -> None:
    """Double-headed dimension arrow with centered label box."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 2:
        return
    nx, ny = -dy / length, dx / length
    ax1, ay1 = x1 + nx * offset, y1 + ny * offset
    ax2, ay2 = x2 + nx * offset, y2 + ny * offset

    painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QLineF(ax1, ay1, ax2, ay2))
    angle = math.atan2(ay2 - ay1, ax2 - ax1)
    _arrowhead(painter, ax2, ay2, angle, color)
    _arrowhead(painter, ax1, ay1, angle + math.pi, color)

    mx, my = (ax1 + ax2) / 2, (ay1 + ay2) / 2
    f = QFont()
    f.setPointSize(font_size)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    tw, th = fm.horizontalAdvance(label) + 6, fm.height() + 2
    rect = QRectF(mx - tw / 2, my - th / 2, tw, th)
    painter.fillRect(rect, QColor(250, 250, 250, 210))
    painter.setPen(QPen(color, 0.8))
    painter.drawRect(rect)
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


def _callout(
    painter: QPainter,
    tip_x: float, tip_y: float,
    label: str,
    color: QColor = _C_ANNOT,
    dx: float = 28.0, dy: float = -18.0,
    font_size: int = 9,
) -> None:
    """Leader line from tip to label box."""
    lx, ly = tip_x + dx, tip_y + dy
    painter.setPen(QPen(color, 1.2))
    painter.drawLine(QLineF(tip_x, tip_y, lx, ly))
    _arrowhead(painter, tip_x, tip_y, math.atan2(tip_y - ly, tip_x - lx), color, size=6)

    f = QFont()
    f.setPointSize(font_size)
    f.setBold(True)
    painter.setFont(f)
    fm = painter.fontMetrics()
    tw, th = fm.horizontalAdvance(label) + 8, fm.height() + 4
    bx = lx + 2 if dx >= 0 else lx - tw - 2
    by = ly - th / 2
    rect = QRectF(bx, by, tw, th)
    painter.fillRect(rect, QColor(255, 250, 230, 230))
    painter.setPen(QPen(color, 0.8))
    painter.drawRect(rect)
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


# ---------------------------------------------------------------------------
# Dynamic diagram: Placa Base top view
# ---------------------------------------------------------------------------

class _BasePlateDiagram(QWidget):
    """QPainter-based top-view diagram of the Placa Base."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: dict = {}
        self._active: Optional[str] = None
        self.setMinimumSize(260, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def update_state(self, active: Optional[str], values: dict) -> None:
        self._active = active
        self._values = values
        self.update()

    # -------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._values:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint(painter)
        painter.end()

    def _paint(self, painter: QPainter) -> None:
        W, H = self.width(), self.height()
        largo = float(self._values.get("largo", 300))
        ancho = float(self._values.get("ancho", 200))

        pad = 52
        scale = min((W - 2 * pad) / largo, (H - 2 * pad) / ancho)
        pw = largo * scale
        ph = ancho * scale
        px = (W - pw) / 2
        py = (H - ph) / 2

        painter.fillRect(0, 0, W, H, _C_BG)

        # Plate
        painter.setBrush(QBrush(_C_PLATE))
        painter.setPen(QPen(_C_PLATE_OUT, 2.0))
        painter.drawRect(QRectF(px, py, pw, ph))

        # Slots (if active)
        tiene = bool(self._values.get("tiene_ranuras", False))
        if tiene:
            self._paint_slots(painter, px, py, pw, ph, scale, largo, ancho)

        # Holes
        patron = self._values.get("patron_perforaciones", "none")
        if patron != "none":
            self._paint_holes(painter, px, py, scale, largo, ancho, patron)

        # Active annotation
        if self._active:
            self._paint_annotation(painter, px, py, pw, ph, scale, largo, ancho)

        # Passive dimensions (always shown, lighter)
        self._paint_passive(painter, px, py, pw, ph, largo, ancho)

    # ---- Hole positions (model coords) ----

    def _hole_pos(self, patron, largo, ancho, e, d):
        if patron == "rectangular_4":
            return [(e, e), (largo - e, e), (e, ancho - e), (largo - e, ancho - e)]
        if patron == "rectangular_6":
            return [(e, e), (largo - e, e), (e, ancho - e), (largo - e, ancho - e),
                    (largo / 2, e), (largo / 2, ancho - e)]
        if patron == "lineal_2":
            return [(e, ancho / 2), (largo - e, ancho / 2)]
        # personalizado fallback
        return [(e, e), (largo - e, e), (e, ancho - e), (largo - e, ancho - e)]

    # ---- Slots ----

    def _paint_slots(self, painter, px, py, pw, ph, scale, largo, ancho):
        aw = float(self._values.get("ancho_ranura", 12))
        lr = float(self._values.get("largo_ranura", 40))
        active = self._active

        if active in ("tiene_ranuras", "ancho_ranura", "largo_ranura"):
            fill = QColor("#FFF3E0")
            pen  = QPen(_C_ANNOT, 1.8)
        else:
            fill = _C_SLOT
            pen  = QPen(_C_SLOT_OUT, 1.2)

        painter.setBrush(QBrush(fill))
        painter.setPen(pen)
        sx = px + (largo - lr) / 2 * scale
        for sy in [py, py + ph - aw * scale]:
            painter.drawRect(QRectF(sx, sy, lr * scale, aw * scale))

    # ---- Holes ----

    def _paint_holes(self, painter, px, py, scale, largo, ancho, patron):
        e = float(self._values.get("margen_perforacion", 30))
        d = float(self._values.get("diametro_perforacion", 18))
        r = d / 2 * scale
        active = self._active

        if active in ("diametro_perforacion", "patron_perforaciones"):
            fill = QColor("#FFF9C4");  pen = QPen(_C_ANNOT, 1.8)
        elif active == "margen_perforacion":
            fill = QColor("#E3F2FD");  pen = QPen(_C_DIM, 1.5)
        else:
            fill = _C_HOLE;            pen = QPen(_C_HOLE_OUT, 1.2)

        painter.setBrush(QBrush(fill))
        painter.setPen(pen)
        for cx_m, cy_m in self._hole_pos(patron, largo, ancho, e, d):
            painter.drawEllipse(QPointF(px + cx_m * scale, py + cy_m * scale), r, r)

    # ---- Active annotation ----

    def _paint_annotation(self, painter, px, py, pw, ph, scale, largo, ancho):
        v = self._values
        p = self._active
        painter.save()

        if p == "largo":
            val = float(v.get("largo", 300))
            _dim_arrow(painter, px, py + ph + 26, px + pw, py + ph + 26,
                       f"L = {val:.0f} mm", _C_ANNOT, font_size=10)
            painter.setPen(QPen(_C_ANNOT, 2.5, Qt.PenStyle.DashLine))
            painter.drawLine(QLineF(px, py, px + pw, py))
            painter.drawLine(QLineF(px, py + ph, px + pw, py + ph))

        elif p == "ancho":
            val = float(v.get("ancho", 200))
            _dim_arrow(painter, px - 26, py, px - 26, py + ph,
                       f"W = {val:.0f} mm", _C_ANNOT, font_size=10)
            painter.setPen(QPen(_C_ANNOT, 2.5, Qt.PenStyle.DashLine))
            painter.drawLine(QLineF(px, py, px, py + ph))
            painter.drawLine(QLineF(px + pw, py, px + pw, py + ph))

        elif p == "espesor":
            t = float(v.get("espesor", 12))
            # Corner cross-section hint
            inset = 16
            ex, ey = px + pw, py
            painter.setPen(QPen(_C_ANNOT, 2.0))
            painter.drawLine(QLineF(ex - inset, ey, ex + 12, ey - 12))
            painter.drawLine(QLineF(ex + 12, ey - 12, ex + 12, ey - 12 - t * scale * 0.4))
            _callout(painter, ex + 12, ey - 12, f"t = {t:.0f} mm",
                     _C_ANNOT, dx=14, dy=-8)

        elif p == "diametro_perforacion":
            patron = v.get("patron_perforaciones", "none")
            if patron != "none":
                e = float(v.get("margen_perforacion", 30))
                d = float(v.get("diametro_perforacion", 18))
                r = d / 2 * scale
                pos = self._hole_pos(patron, largo, ancho, e, d)
                if pos:
                    cx = px + pos[0][0] * scale
                    cy = py + pos[0][1] * scale
                    _dim_arrow(painter, cx - r, cy, cx + r, cy,
                                f"d = {d:.0f} mm", _C_ANNOT, offset=-(r + 10))

        elif p == "margen_perforacion":
            patron = v.get("patron_perforaciones", "none")
            if patron != "none":
                e = float(v.get("margen_perforacion", 30))
                d = float(v.get("diametro_perforacion", 18))
                pos = self._hole_pos(patron, largo, ancho, e, d)
                if pos:
                    cx = px + pos[0][0] * scale
                    cy = py + pos[0][1] * scale
                    # Arrow from left edge to hole center
                    _dim_arrow(painter, px, cy, cx, cy,
                                f"e = {e:.0f} mm", _C_ANNOT)

        elif p == "patron_perforaciones":
            labels = {"none": "Sin agujeros", "rectangular_4": "4 agujeros",
                      "rectangular_6": "6 agujeros", "lineal_2": "2 agujeros",
                      "personalizado": "Personalizado"}
            val = labels.get(str(v.get("patron_perforaciones", "none")), "?")
            self._center_badge(painter, px, py, pw, ph, f"Patrón: {val}")

        elif p == "tiene_ranuras":
            tiene = bool(v.get("tiene_ranuras", False))
            self._center_badge(painter, px, py, pw, ph,
                               "Ranuras: SÍ" if tiene else "Ranuras: NO")

        elif p == "ancho_ranura":
            tiene = bool(v.get("tiene_ranuras", False))
            if tiene:
                aw = float(v.get("ancho_ranura", 12))
                lr = float(v.get("largo_ranura", 40))
                sx = px + (largo - lr) / 2 * scale
                _dim_arrow(painter, sx - 16, py, sx - 16, py + aw * scale,
                           f"ar = {aw:.0f} mm", _C_ANNOT)

        elif p == "largo_ranura":
            tiene = bool(v.get("tiene_ranuras", False))
            if tiene:
                lr = float(v.get("largo_ranura", 40))
                sx = px + (largo - lr) / 2 * scale
                _dim_arrow(painter, sx, py - 16, sx + lr * scale, py - 16,
                           f"lr = {lr:.0f} mm", _C_ANNOT)

        elif p in ("material", "acabado_superficial"):
            label_map = {
                "ASTM_A36": "ASTM A36", "ASTM_A572_G50": "A572 Gr.50",
                "SS304": "AISI 304", "SS316": "AISI 316", "AL6061T6": "AL 6061-T6",
                "laminado_caliente": "HR", "laminado_frio": "CR",
                "granallado": "Sa 2.5", "pintado": "Pintado",
            }
            raw = str(v.get(p, ""))
            friendly = label_map.get(raw, raw.replace("_", " "))
            prefix = "Mat:" if p == "material" else "Acab:"
            self._center_badge(painter, px, py, pw, ph, f"{prefix} {friendly}")

        painter.restore()

    @staticmethod
    def _center_badge(painter, px, py, pw, ph, text, font_size=10):
        f = QFont()
        f.setPointSize(font_size)
        f.setBold(True)
        painter.setFont(f)
        fm = painter.fontMetrics()
        tw, th = fm.horizontalAdvance(text) + 14, fm.height() + 8
        rect = QRectF(px + pw / 2 - tw / 2, py + ph / 2 - th / 2, tw, th)
        painter.fillRect(rect, QColor(255, 248, 220, 220))
        painter.setPen(QPen(_C_ANNOT, 1.0))
        painter.drawRect(rect)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    # ---- Passive dimension labels ----

    def _paint_passive(self, painter, px, py, pw, ph, largo, ancho):
        painter.setPen(QColor("#90A4AE"))
        f = QFont()
        f.setPointSize(8)
        painter.setFont(f)
        if self._active != "largo":
            painter.drawText(
                QRectF(px, py + ph + 4, pw, 16),
                Qt.AlignmentFlag.AlignCenter,
                f"L = {largo:.0f} mm",
            )
        if self._active != "ancho":
            painter.save()
            painter.translate(px - 12, py + ph / 2)
            painter.rotate(-90)
            painter.drawText(
                QRectF(-36, -8, 72, 16),
                Qt.AlignmentFlag.AlignCenter,
                f"W = {ancho:.0f} mm",
            )
            painter.restore()


# ---------------------------------------------------------------------------
# SchematicViewer — public widget
# ---------------------------------------------------------------------------

class SchematicViewer(QWidget):
    """
    Schematic viewer for parametric input.
    Bind to ParameterForm.param_focused and ParameterForm.values_changed.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._piece_code: Optional[str] = None
        self._active_param: Optional[str] = None
        self._values: dict = {}
        self._build_ui()
        self.setMinimumWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #FAFAFA; border-left: 1px solid #DDD;")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_parameter(
        self, piece_code: str, param_name: Optional[str], values: dict
    ) -> None:
        self._piece_code = piece_code
        self._active_param = param_name
        self._values = values
        self._refresh()

    def set_values(self, values: dict) -> None:
        """Refresh diagram with updated values, keeping active param."""
        self._values = values
        if self._piece_code:
            self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title_lbl = QLabel("Esquema")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        self._title_lbl.setFont(f)
        self._title_lbl.setContentsMargins(10, 7, 10, 5)
        self._title_lbl.setStyleSheet(
            "background-color: #ECEFF1; border-bottom: 1px solid #CFD8DC;"
        )
        layout.addWidget(self._title_lbl)

        # Diagram: either static image or dynamic widget
        self._static_lbl = QLabel()
        self._static_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._static_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._diagram = _BasePlateDiagram()

        layout.addWidget(self._diagram)
        layout.addWidget(self._static_lbl)
        layout.setStretchFactor(self._diagram, 1)
        layout.setStretchFactor(self._static_lbl, 1)
        self._static_lbl.hide()

        # Info bar
        self._info_lbl = QLabel()
        self._info_lbl.setContentsMargins(10, 3, 10, 5)
        self._info_lbl.setStyleSheet(
            "color: #546E7A; font-size: 10px; "
            "background-color: #ECEFF1; border-top: 1px solid #CFD8DC;"
        )
        self._info_lbl.setWordWrap(True)
        layout.addWidget(self._info_lbl)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        # Update title
        piece = catalog.get_piece(self._piece_code) if self._piece_code else None
        param_spec = next(
            (p for p in (piece.parameters if piece else [])
             if p.name == self._active_param),
            None,
        )
        if param_spec:
            unit = f"  [{param_spec.unit}]" if param_spec.unit else ""
            self._title_lbl.setText(f"{param_spec.display_name}{unit}")
            self._info_lbl.setText(self._format_info(param_spec, self._values))
        elif piece:
            self._title_lbl.setText(piece.display_name)
            self._info_lbl.setText("")
        else:
            self._title_lbl.setText("Esquema")
            self._info_lbl.setText("")

        # Static image override?
        static = self._find_static_image()
        if static:
            pix = QPixmap(str(static))
            self._static_lbl.setPixmap(
                pix.scaled(self._static_lbl.size(),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
            self._diagram.hide()
            self._static_lbl.show()
        else:
            self._static_lbl.hide()
            if self._piece_code == "base_plate":
                self._diagram.update_state(self._active_param, self._values)
                self._diagram.show()
            else:
                self._diagram.hide()

    def _find_static_image(self) -> Optional[Path]:
        if not self._piece_code or not self._active_param:
            return None
        assets = (
            settings.project_root / "cad_generator" / "assets" / "schematics"
        )
        for ext in (".png", ".jpg", ".jpeg"):
            p = assets / self._piece_code / f"{self._active_param}{ext}"
            if p.exists():
                return p
        return None

    @staticmethod
    def _format_info(spec, values: dict) -> str:
        """Build a one-line info string for the info bar."""
        val = values.get(spec.name, spec.default)
        parts = []
        if spec.type == "float":
            if spec.min is not None and spec.max is not None:
                parts.append(f"Rango: {spec.min:.0f}–{spec.max:.0f} {spec.unit}")
            if spec.step:
                parts.append(f"Paso: {spec.step:.0f}")
            parts.append(f"Actual: {val}")
        elif spec.type == "enum":
            opt = next((o for o in spec.options if o.value == val), None)
            if opt:
                parts.append(f"Sel: {opt.label}")
        elif spec.type == "bool":
            parts.append("Activo" if val else "Inactivo")
        return "  |  ".join(parts)
