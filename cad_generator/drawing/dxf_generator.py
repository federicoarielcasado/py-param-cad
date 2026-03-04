"""
DXFDrawingGenerator — 2D technical drawing generation (Semana 10).

Generates DXF (R2010 / AutoCAD 2010) and PDF drawings for each piece:
  - Top view  (planta)  — footprint, hole pattern, slots, center lines
  - Front view (alzado) — profile with hidden hole projections
  - IRAM 4505 / ISO 128 compliant title block
  - Automatic sheet size: A4 → A3 → A2 (landscape)
  - Automatic scale:      1:1 → 1:2 → 1:5 → 1:10 → 1:20 → 1:50
  - Overall dimensions (largo, ancho, espesor) with real-unit text
  - PDF export via ezdxf drawing add-on (requires matplotlib)

Coordinate system: model-space mm, Y-up.  Sheet is placed at origin (0, 0).
Geometry is drawn at 1/scale_denom of real size inside model space.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf.enums import TextEntityAlignment


# ---------------------------------------------------------------------------
# Data classes — public API
# ---------------------------------------------------------------------------

@dataclass
class DrawingContext:
    """All metadata needed to fill the IRAM 4505 title block."""
    piece_code: str
    piece_display_name: str
    drawing_number: str
    revision_code: str
    author: str
    company_name: str
    material_label: str
    date_str: str = ""
    standard: str = "IRAM 4505 / ISO 128"
    eco_status: str = "draft"   # "draft" | "issued" | "obsolete"

    def __post_init__(self) -> None:
        if not self.date_str:
            self.date_str = date.today().strftime("%d/%m/%Y")

    @property
    def eco_status_label(self) -> str:
        """Human-readable ECO status for the title block."""
        return {
            "draft":    "BORRADOR",
            "issued":   "EMITIDO",
            "obsolete": "OBSOLETO",
        }.get(self.eco_status, self.eco_status.upper())


@dataclass
class DrawingResult:
    success: bool
    dxf_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    sheet_format: str = ""
    scale: str = ""
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

# Landscape sheet sizes (width × height, mm) — IRAM 4503 / ISO 5457
_SHEETS: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
}

_ML  = 25.0   # left binding margin (mm)
_MO  = 10.0   # right / top / bottom margins (mm)

_TB_W = 185.0  # title block width (mm)
_TB_H =  55.0  # title block height (mm)

# Preferred scale denominators — smallest denominator tried first
_SCALES = [1, 2, 5, 10, 20, 50]

# DXF dimension geometry
_DIM_ASZ    = 2.5   # arrow size (mm)
_DIM_EXT_O  = 2.0   # extension line offset from entity
_DIM_EXT_E  = 2.0   # extension line overshoot past dim line
_DIM_GAP    = 1.5   # gap from dim line to text
_DIM_OFF    = 12.0  # how far dim line sits from the view edge

# Text heights on paper (mm)
_TH_TITLE   = 5.0
_TH_BODY    = 3.5
_TH_SMALL   = 2.5

# Layer spec: name → (ACI color, linetype, lineweight in 1/100 mm)
_LAYER_SPEC: dict[str, tuple[int, str, int]] = {
    "VISIBLE":    (7,  "Continuous", 50),   # 0.50 mm — outlines
    "HIDDEN":     (1,  "DASHED_BP",  25),   # 0.25 mm — hidden edges
    "CENTER":     (5,  "CENTER_BP",  18),   # 0.18 mm — axes / symmetry
    "DIMENSION":  (3,  "Continuous", 18),   # 0.18 mm — dim lines + text
    "TITLEBLOCK": (7,  "Continuous", 70),   # 0.70 mm — border frame
    "TEXT_TB":    (7,  "Continuous", 18),   # 0.18 mm — title block text
}


# ---------------------------------------------------------------------------
# Internal: sheet & scale selection
# ---------------------------------------------------------------------------

def _pick_sheet_and_scale(largo: float, ancho: float, espesor: float) -> tuple[str, int]:
    """Return (sheet_name, scale_denominator) that fits top+front views."""
    dim_space = 15.0   # space reserved for dimension lines per side (mm)
    view_gap  = 15.0   # gap between top view and front view

    for sheet_name, (sw, sh) in _SHEETS.items():
        usable_w = sw - _ML - _MO
        usable_h = sh - _MO * 2 - _TB_H - _MO  # above title block strip

        for denom in _SCALES:
            s = 1.0 / denom
            # Top view footprint on paper + dimension space
            w_views = largo * s + 2 * dim_space
            h_top   = ancho  * s + dim_space
            h_front = max(espesor * s, 5.0) + dim_space  # min 5 mm visible
            h_total = h_top + view_gap + h_front

            if w_views <= usable_w and h_total <= usable_h:
                return sheet_name, denom

    return "A1", 50  # absolute fallback


# ---------------------------------------------------------------------------
# Internal: DXF document factory
# ---------------------------------------------------------------------------

def _build_doc():
    """Create an R2010 document with layers and custom linetypes."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # 4 = millimetres

    # Custom linetypes (pattern: [total_len, dash, -gap, ...])
    doc.linetypes.add("DASHED_BP",
                      pattern=[0.75, 0.5, -0.25],
                      description="Dashed — hidden lines")
    doc.linetypes.add("CENTER_BP",
                      pattern=[2.0, 1.25, -0.25, 0.25, -0.25],
                      description="Center — axes")

    for name, (color, lt, lw) in _LAYER_SPEC.items():
        layer = doc.layers.add(name)
        layer.color = color
        layer.linetype = lt if lt in doc.linetypes else "Continuous"
        layer.lineweight = lw

    return doc, doc.modelspace()


# ---------------------------------------------------------------------------
# Internal: primitive drawing helpers
# ---------------------------------------------------------------------------

def _rect(msp, x0: float, y0: float, x1: float, y1: float, layer: str) -> None:
    msp.add_lwpolyline(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        close=True, dxfattribs={"layer": layer},
    )


def _hline(msp, x0: float, x1: float, y: float, layer: str) -> None:
    msp.add_line((x0, y), (x1, y), dxfattribs={"layer": layer})


def _vline(msp, x: float, y0: float, y1: float, layer: str) -> None:
    msp.add_line((x, y0), (x, y1), dxfattribs={"layer": layer})


def _txt(msp, text: str, cx: float, cy: float, height: float,
         layer: str,
         align: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER) -> None:
    msp.add_text(
        text,
        dxfattribs={"layer": layer, "height": height},
    ).set_placement((cx, cy), align=align)


def _txt_left(msp, text: str, x: float, y: float, height: float, layer: str) -> None:
    msp.add_text(
        text,
        dxfattribs={"layer": layer, "height": height},
    ).set_placement((x, y), align=TextEntityAlignment.LEFT)


# ---------------------------------------------------------------------------
# Internal: sheet frame
# ---------------------------------------------------------------------------

def _draw_frame(msp, sw: float, sh: float) -> None:
    """Draw outer border and inner frame with binding margin."""
    # Outer border
    _rect(msp, 0, 0, sw, sh, "TITLEBLOCK")
    # Inner frame (binding margin)
    _rect(msp, _ML, _MO, sw - _MO, sh - _MO, "TITLEBLOCK")


# ---------------------------------------------------------------------------
# Internal: IRAM 4505 title block
# ---------------------------------------------------------------------------

def _draw_title_block(msp, sw: float, sh: float,
                      ctx: DrawingContext, scale_str: str) -> None:
    """
    Draw simplified IRAM 4505 title block at bottom-right of inner frame.

    Row structure (bottom→top):
      Row 1 (12 mm): ESCALA (35) | N°PLANO (55) | REV (25) | FECHA (70)
      Row 2 (13 mm): MATERIAL (35) | DIBUJÓ (60) | NORMA (90)
      Row 3 (15 mm): TÍTULO — full width
      Row 4 (15 mm): EMPRESA — full width
      Total: 55 mm = _TB_H ✓
    """
    x0 = sw - _MO - _TB_W
    y0 = _MO
    x1 = sw - _MO
    y1 = _MO + _TB_H

    r1h, r2h, r3h = 12.0, 13.0, 15.0
    r4h = _TB_H - r1h - r2h - r3h  # 15.0

    y_r1 = y0
    y_r2 = y0 + r1h
    y_r3 = y0 + r1h + r2h
    y_r4 = y0 + r1h + r2h + r3h

    # Outer border
    _rect(msp, x0, y0, x1, y1, "TITLEBLOCK")

    # Horizontal dividers
    for y_div in (y_r2, y_r3, y_r4):
        _hline(msp, x0, x1, y_div, "TITLEBLOCK")

    # Row 1 column separators: 35 | 55 | 25 | 45 | 25(ECO)
    c1 = x0 + 35.0
    c2 = c1 + 55.0
    c3 = c2 + 25.0
    c4 = c3 + 45.0   # FECHA | ESTADO separator
    for xc in (c1, c2, c3, c4):
        _vline(msp, xc, y_r1, y_r2, "TITLEBLOCK")

    # Row 2 column separators: 35 | 60 | remainder(90)
    d1 = x0 + 35.0
    d2 = d1 + 60.0
    _vline(msp, d1, y_r2, y_r3, "TITLEBLOCK")
    _vline(msp, d2, y_r2, y_r3, "TITLEBLOCK")

    # --- Label text (small, top-left of each cell) ---
    lbl_dx, lbl_dy = 1.2, -1.2

    def lbl(text: str, cell_x: float, cell_top_y: float) -> None:
        _txt_left(msp, text, cell_x + lbl_dx, cell_top_y + lbl_dy, _TH_SMALL, "TEXT_TB")

    def val(text: str, cell_cx: float, cell_cy: float, h: float = _TH_BODY) -> None:
        _txt(msp, text, cell_cx, cell_cy, h, "TEXT_TB")

    # Row 1 labels & values
    lbl("ESCALA:",   x0,  y_r2)
    lbl("N° PLANO:", c1,  y_r2)
    lbl("REV.:",     c2,  y_r2)
    lbl("FECHA:",    c3,  y_r2)
    lbl("ESTADO:",   c4,  y_r2)

    val(scale_str,                (x0 + c1) / 2, (y_r1 + y_r2) / 2)
    val(ctx.drawing_number,       (c1 + c2) / 2, (y_r1 + y_r2) / 2)
    val(ctx.revision_code,        (c2 + c3) / 2, (y_r1 + y_r2) / 2, _TH_TITLE)
    val(ctx.date_str,             (c3 + c4) / 2, (y_r1 + y_r2) / 2, _TH_SMALL)
    val(ctx.eco_status_label,     (c4 + x1) / 2, (y_r1 + y_r2) / 2, _TH_SMALL)

    # Row 2 labels & values
    lbl("MATERIAL:", x0,  y_r3)
    lbl("DIBUJÓ:",   d1,  y_r3)
    lbl("NORMA:",    d2,  y_r3)

    val(ctx.material_label,     (x0 + d1) / 2, (y_r2 + y_r3) / 2)
    val(ctx.author,             (d1 + d2) / 2, (y_r2 + y_r3) / 2)
    val(ctx.standard,           (d2 + x1) / 2, (y_r2 + y_r3) / 2, _TH_SMALL)

    # Row 3: Título
    lbl("TÍTULO:", x0, y_r4)
    val(ctx.piece_display_name, (x0 + x1) / 2, (y_r3 + y_r4) / 2, _TH_TITLE)

    # Row 4: Empresa
    lbl("EMPRESA:", x0, y1)
    val(ctx.company_name or "—", (x0 + x1) / 2, (y_r4 + y1) / 2, _TH_BODY)


# ---------------------------------------------------------------------------
# Internal: hole positions (matches freecad_generate.py logic)
# ---------------------------------------------------------------------------

def _hole_positions(patron: str, largo: float, ancho: float,
                    margen: float) -> list[tuple[float, float]]:
    e = margen
    L, W = largo, ancho
    if patron == "none":
        return []
    elif patron == "rectangular_4":
        return [(e, e), (L - e, e), (e, W - e), (L - e, W - e)]
    elif patron == "rectangular_6":
        return [(e, e), (L - e, e), (e, W - e), (L - e, W - e),
                (L / 2, e), (L / 2, W - e)]
    elif patron == "lineal_2":
        return [(e, W / 2), (L - e, W / 2)]
    else:  # personalizado → rectangular_4 fallback
        return [(e, e), (L - e, e), (e, W - e), (L - e, W - e)]


# ---------------------------------------------------------------------------
# Internal: top view (planta)
# ---------------------------------------------------------------------------

def _draw_top_view(msp, params: dict, x0: float, y0: float, s: float) -> None:
    """
    Draw planta (top view) of Placa Base.
    x0, y0: bottom-left corner in model space (mm on paper).
    s: scale factor (= 1/denom).
    """
    largo   = params["largo"]
    ancho   = params["ancho"]
    d       = params["diametro_perforacion"]
    margen  = params["margen_perforacion"]
    patron  = params["patron_perforaciones"]
    ranuras = params["tiene_ranuras"]
    ar      = params.get("ancho_ranura", 12.0)
    lr      = params.get("largo_ranura", 40.0)

    vl = largo * s   # view largo (paper mm)
    va = ancho * s   # view ancho (paper mm)
    vd = d * s       # hole diameter on paper
    vr = vd / 2.0    # hole radius on paper

    # Outer rectangle
    _rect(msp, x0, y0, x0 + vl, y0 + va, "VISIBLE")

    # Center lines through plate (cross at plate center)
    cx = x0 + vl / 2
    cy = y0 + va / 2
    ext = 5.0   # extension beyond border
    _hline(msp, x0 - ext, x0 + vl + ext, cy, "CENTER")
    _vline(msp, cx, y0 - ext, y0 + va + ext, "CENTER")

    # Holes
    holes = _hole_positions(patron, largo, ancho, margen)
    for hx, hy in holes:
        px = x0 + hx * s
        py = y0 + hy * s
        # Circle
        msp.add_circle((px, py), vr, dxfattribs={"layer": "VISIBLE"})
        # Crosshair (center lines)
        cl_ext = max(vr * 1.5, 3.0)
        _hline(msp, px - cl_ext, px + cl_ext, py, "CENTER")
        _vline(msp, px, py - cl_ext, py + cl_ext, "CENTER")

    # Slots (if enabled) — shown as cutout rectangles on front/back edges
    if ranuras:
        slot_x0 = x0 + (largo / 2 - lr / 2) * s
        slot_x1 = x0 + (largo / 2 + lr / 2) * s
        slot_y_bot_top = y0 + ar * s  # front slot top
        slot_y_bk_bot  = y0 + (ancho - ar) * s  # back slot bottom

        # Front slot (on bottom edge of plate)
        _rect(msp, slot_x0, y0, slot_x1, slot_y_bot_top, "VISIBLE")
        # Back slot (on top edge of plate)
        _rect(msp, slot_x0, slot_y_bk_bot, slot_x1, y0 + va, "VISIBLE")

    # Hole diameter annotation on first hole (if any)
    if holes:
        hx0, hy0 = holes[0]
        ann_x = x0 + hx0 * s + vr + 3.0
        ann_y = y0 + hy0 * s + vr + 3.0
        _txt(msp, f"\u00d8{d:.0f}", ann_x, ann_y, _TH_SMALL, "DIMENSION")


# ---------------------------------------------------------------------------
# Internal: front view (alzado)
# ---------------------------------------------------------------------------

def _draw_front_view(msp, params: dict, x0: float, y0: float, s: float) -> None:
    """
    Draw alzado (front view — looking along Y axis).
    x0, y0: bottom-left corner.
    s: scale factor.
    """
    largo   = params["largo"]
    espesor = params["espesor"]
    patron  = params["patron_perforaciones"]
    margen  = params["margen_perforacion"]
    ancho   = params["ancho"]

    vl  = largo   * s
    ve  = max(espesor * s, 3.0)   # minimum 3 mm visible on paper

    # Outer rectangle
    _rect(msp, x0, y0, x0 + vl, y0 + ve, "VISIBLE")

    # Project holes as hidden vertical lines (center of hole column)
    holes = _hole_positions(patron, largo, ancho, margen)
    projected_xs = sorted({hx for hx, _ in holes})
    for hx in projected_xs:
        px = x0 + hx * s
        _vline(msp, px, y0, y0 + ve, "HIDDEN")

    # Espesor label (vertical text on left edge)
    _txt(msp, f"e={espesor:.0f}", x0 - 8.0, y0 + ve / 2, _TH_SMALL, "DIMENSION")


# ---------------------------------------------------------------------------
# Internal: overall dimensions
# ---------------------------------------------------------------------------

def _add_dimensions(msp,
                    tv_x0: float, tv_y0: float, tv_x1: float, tv_y1: float,
                    fv_x0: float, fv_y0: float, fv_y1: float,
                    largo: float, ancho: float, espesor: float,
                    denom: int) -> None:
    """Add linear dimension entities for overall measurements."""
    lfac = float(denom)   # dimlfac: scales paper measurement → real value

    dim_ovr = {
        "dimlfac": lfac,
        "dimtxt":  _TH_BODY,
        "dimasz":  _DIM_ASZ,
        "dimexo":  _DIM_EXT_O,
        "dimexe":  _DIM_EXT_E,
        "dimgap":  _DIM_GAP,
        "dimlunit": 2,   # decimal units
        "dimdsep":  46,  # '.' as decimal separator (ASCII)
    }

    # Horizontal dim — Largo (above top view)
    y_dim_l = tv_y1 + _DIM_OFF
    d1 = msp.add_linear_dim(
        base=(0, y_dim_l),
        p1=(tv_x0, tv_y1),
        p2=(tv_x1, tv_y1),
        angle=0,
        override=dim_ovr,
        dxfattribs={"layer": "DIMENSION"},
    )
    d1.render()

    # Vertical dim — Ancho (left of top view)
    x_dim_a = tv_x0 - _DIM_OFF
    d2 = msp.add_linear_dim(
        base=(x_dim_a, 0),
        p1=(tv_x0, tv_y0),
        p2=(tv_x0, tv_y1),
        angle=90,
        override=dim_ovr,
        dxfattribs={"layer": "DIMENSION"},
    )
    d2.render()

    # Vertical dim — Espesor (left of front view)
    x_dim_e = fv_x0 - _DIM_OFF
    ovr_e = {**dim_ovr}
    d3 = msp.add_linear_dim(
        base=(x_dim_e, 0),
        p1=(fv_x0, fv_y0),
        p2=(fv_x0, fv_y1),
        angle=90,
        override=ovr_e,
        dxfattribs={"layer": "DIMENSION"},
    )
    d3.render()


# ---------------------------------------------------------------------------
# Internal: PDF export
# ---------------------------------------------------------------------------

def _export_pdf(doc, pdf_path: Path, sheet_name: str) -> tuple[bool, str]:
    """
    Render DXF to PDF using ezdxf drawing add-on + matplotlib.
    Returns (success, warning_or_error_message).
    """
    try:
        from matplotlib import pyplot as plt  # type: ignore[import]
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except ImportError:
        return False, "matplotlib no instalado — PDF no generado (solo DXF)."

    try:
        sw, sh = _SHEETS[sheet_name]
        fig_w = sw / 25.4   # mm → inches
        fig_h = sh / 25.4

        fig = plt.figure(figsize=(fig_w, fig_h), dpi=300)
        ax  = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()

        ctx     = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)

        fig.savefig(str(pdf_path), dpi=300, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
        return True, ""

    except Exception as exc:
        return False, f"Error al exportar PDF: {exc}"


# ---------------------------------------------------------------------------
# Public: DXFDrawingGenerator
# ---------------------------------------------------------------------------

class DXFDrawingGenerator:
    """
    Generates 2D DXF + PDF drawings for supported piece types.
    Currently supports: base_plate.
    """

    def generate(
        self,
        piece_code: str,
        parameters: dict,
        output_dir: Path,
        ctx: DrawingContext,
    ) -> DrawingResult:
        """Generate DXF and PDF for the given piece. Never raises."""
        try:
            if piece_code == "base_plate":
                return self._generate_base_plate(parameters, output_dir, ctx)
            return DrawingResult(
                success=False,
                error_message=f"Pieza '{piece_code}' no soportada en el generador DXF.",
            )
        except Exception as exc:
            return DrawingResult(success=False, error_message=str(exc))

    # ------------------------------------------------------------------
    # Base plate drawing
    # ------------------------------------------------------------------

    def _generate_base_plate(
        self, params: dict, output_dir: Path, ctx: DrawingContext
    ) -> DrawingResult:
        largo   = params["largo"]
        ancho   = params["ancho"]
        espesor = params["espesor"]

        sheet_name, denom = _pick_sheet_and_scale(largo, ancho, espesor)
        s = 1.0 / denom
        scale_str = f"1:{denom}" if denom > 1 else "1:1"

        sw, sh = _SHEETS[sheet_name]

        doc, msp = _build_doc()

        # 1 — Sheet frame
        _draw_frame(msp, sw, sh)

        # 2 — Title block
        _draw_title_block(msp, sw, sh, ctx, scale_str)

        # 3 — Compute view positions
        #  Available area: above title block strip, inside frame
        view_area_x0 = _ML + _DIM_OFF + 5.0
        view_area_y0 = _MO + _TB_H + _MO
        view_gap = 15.0

        vl = largo   * s
        va = ancho   * s
        ve = max(espesor * s, 3.0)

        # Front view (alzado) — bottom
        fv_x0 = view_area_x0
        fv_y0 = view_area_y0
        fv_y1 = fv_y0 + ve

        # Top view (planta) — above front view
        tv_x0 = fv_x0
        tv_y0 = fv_y1 + view_gap
        tv_x1 = tv_x0 + vl
        tv_y1 = tv_y0 + va

        # 4 — Draw views
        _draw_top_view(msp, params, tv_x0, tv_y0, s)
        _draw_front_view(msp, params, fv_x0, fv_y0, s)

        # View labels
        cx_views = fv_x0 + vl / 2
        _txt(msp, "PLANTA", cx_views, tv_y1 + 6.0, _TH_SMALL, "TEXT_TB")
        _txt(msp, "ALZADO", cx_views, fv_y0 - 5.0, _TH_SMALL, "TEXT_TB")

        # 5 — Dimensions
        _add_dimensions(
            msp,
            tv_x0, tv_y0, tv_x1, tv_y1,
            fv_x0, fv_y0, fv_y1,
            largo, ancho, espesor,
            denom,
        )

        # 6 — Save DXF
        stem = f"base_plate_{ctx.revision_code}"
        dxf_path = output_dir / f"{stem}.dxf"
        doc.saveas(str(dxf_path))

        # 7 — Export PDF
        warnings: list[str] = []
        pdf_path = output_dir / f"{stem}.pdf"
        ok, msg = _export_pdf(doc, pdf_path, sheet_name)
        if not ok:
            pdf_path = None  # type: ignore[assignment]
            warnings.append(msg)

        return DrawingResult(
            success=True,
            dxf_path=dxf_path,
            pdf_path=pdf_path,
            sheet_format=sheet_name,
            scale=scale_str,
            warnings=warnings,
        )
