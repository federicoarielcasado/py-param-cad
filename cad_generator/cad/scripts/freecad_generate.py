"""
IMPORTANT: This script runs inside FreeCAD's bundled Python 3.11 interpreter.
           It CANNOT import from cad_generator/. It is fully standalone.

Invocation by FreeCADEngine (via environment variable):
    # FreeCADEngine sets FREECAD_PARAMS before launching:
    FREECAD_PARAMS=/tmp/params.json freecadcmd.exe freecad_generate.py

WHY env var instead of sys.argv?
    freecadcmd.exe treats every positional argument after the script as a
    document to open (it dispatches .json to importYamlJsonMesh, etc.).
    Passing the params file via an environment variable avoids that conflict.

Expected params JSON (written by FreeCADEngine to a temp file):
    {
        "piece_code": "base_plate",
        "parameters": { "largo": 300.0, "ancho": 200.0, ... },
        "output_dir": "C:/path/to/output",
        "revision_code": "A"
    }

Always writes result.json to output_dir (even on failure):
    {
        "success": true,
        "fcstd_path": "C:/path/to/output/base_plate_A.FCStd",
        "step_path": "C:/path/to/output/base_plate_A.step",
        "warnings": [],
        "error_message": null
    }
"""

import json
import os
import traceback
from pathlib import Path


def main():
    params_env = os.environ.get("FREECAD_PARAMS")
    if not params_env:
        raise RuntimeError(
            "Env var FREECAD_PARAMS no definida. "
            "El script debe ser invocado por FreeCADEngine."
        )

    params_path = Path(params_env)
    payload = json.loads(params_path.read_text(encoding="utf-8"))

    piece_code = payload["piece_code"]
    parameters = payload["parameters"]
    output_dir = Path(payload["output_dir"])
    revision_code = payload["revision_code"]

    result = {
        "success": False,
        "fcstd_path": None,
        "step_path": None,
        "warnings": [],
        "error_message": None,
    }

    try:
        # FreeCAD imports — only available inside FreeCAD's Python interpreter
        import FreeCAD  # noqa: F401
        import Part      # noqa: F401

        if piece_code == "base_plate":
            _generate_base_plate(FreeCAD, Part, parameters, output_dir, revision_code, result)
        else:
            result["error_message"] = f"piece_code desconocido: {piece_code!r}"

    except Exception as exc:
        result["error_message"] = (
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        )

    finally:
        result_path = output_dir / "result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Hole pattern helpers
# ---------------------------------------------------------------------------

def _hole_positions(patron: str, largo: float, ancho: float, margen: float) -> list:
    """
    Return (x, y) centre coordinates for holes given the pattern name.

    Coordinate system: origin at the bottom-left corner of the plate top face.
    X = largo direction, Y = ancho direction.
    """
    e, L, W = margen, largo, ancho

    if patron == "none":
        return []
    elif patron == "rectangular_4":
        # Four corners
        return [(e, e), (L - e, e), (e, W - e), (L - e, W - e)]
    elif patron == "rectangular_6":
        # Four corners + two mid-points on the long edges
        return [
            (e, e), (L - e, e),
            (e, W - e), (L - e, W - e),
            (L / 2, e), (L / 2, W - e),
        ]
    elif patron == "lineal_2":
        # Two holes along the longitudinal axis (centre line)
        return [(e, W / 2), (L - e, W / 2)]
    else:
        # "personalizado" and unknown patterns → fall back to rectangular_4
        return [(e, e), (L - e, e), (e, W - e), (L - e, W - e)]


# ---------------------------------------------------------------------------
# Base plate generator
# ---------------------------------------------------------------------------

def _generate_base_plate(FreeCAD, Part, params, output_dir, revision_code, result):
    """
    Generate a parametric base plate solid using FreeCAD Part workbench.

    Geometry:
        - Rectangular body: largo × ancho × espesor
        - Through-holes drilled perpendicular to the plate face (Z axis)
        - Optional adjustment slots on the two longitudinal edges (±Y)

    All boolean subtractions use a small overcut (0.5 mm on each side) to
    avoid coincident-face artefacts common in CSG kernels.
    """
    largo   = float(params["largo"])
    ancho   = float(params["ancho"])
    espesor = float(params["espesor"])
    patron  = str(params.get("patron_perforaciones", "rectangular_4"))
    d_hole  = float(params.get("diametro_perforacion", 18.0))
    margen  = float(params.get("margen_perforacion", 30.0))
    tiene_ranuras = bool(params.get("tiene_ranuras", False))
    ancho_ranura  = float(params.get("ancho_ranura", 12.0))
    largo_ranura  = float(params.get("largo_ranura", 40.0))

    OVERCUT = 0.5   # mm — prevents coincident-face issues in boolean ops
    warnings = []

    # ------------------------------------------------------------------
    # 1. Base body
    # ------------------------------------------------------------------
    plate = Part.makeBox(largo, ancho, espesor)

    # ------------------------------------------------------------------
    # 2. Holes — cylinder subtraction per pattern
    # ------------------------------------------------------------------
    hole_centers = _hole_positions(patron, largo, ancho, margen)
    radius = d_hole / 2.0

    for (x, y) in hole_centers:
        cyl = Part.makeCylinder(
            radius,
            espesor + 2 * OVERCUT,
            FreeCAD.Vector(x, y, -OVERCUT),
            FreeCAD.Vector(0, 0, 1),
        )
        plate = plate.cut(cyl)

    # ------------------------------------------------------------------
    # 3. Slots — box subtraction on longitudinal edges (Y = 0 and Y = W)
    # ------------------------------------------------------------------
    if tiene_ranuras:
        cx = largo / 2.0 - largo_ranura / 2.0   # centred on the plate length

        # Slot on -Y edge (opens toward Y = 0)
        slot_minus_y = Part.makeBox(
            largo_ranura,
            ancho_ranura,
            espesor + 2 * OVERCUT,
            FreeCAD.Vector(cx, -OVERCUT, -OVERCUT),
        )
        plate = plate.cut(slot_minus_y)

        # Slot on +Y edge (opens toward Y = ancho)
        slot_plus_y = Part.makeBox(
            largo_ranura,
            ancho_ranura,
            espesor + 2 * OVERCUT,
            FreeCAD.Vector(cx, ancho - ancho_ranura + OVERCUT, -OVERCUT),
        )
        plate = plate.cut(slot_plus_y)

        # Warn if slot length is longer than 60 % of plate length
        if largo_ranura > largo * 0.6:
            warnings.append(
                "El largo de ranura supera el 60 % del largo de placa. "
                "Verifique la rigidez residual."
            )

    # ------------------------------------------------------------------
    # 4. Geometry validity check
    # ------------------------------------------------------------------
    if not plate.isValid():
        result["error_message"] = (
            "La geometría generada no es válida. "
            "Verifique que las perforaciones y ranuras no se superpongan "
            "ni excedan los límites de la placa."
        )
        return

    # ------------------------------------------------------------------
    # 5. Export FCStd (FreeCAD native format, editable)
    # ------------------------------------------------------------------
    stem = f"base_plate_{revision_code}"
    fcstd_path = output_dir / f"{stem}.FCStd"
    step_path  = output_dir / f"{stem}.step"

    doc = FreeCAD.newDocument("BasePlate")
    obj = doc.addObject("Part::Feature", "BasePlate")
    obj.Shape = plate
    doc.recompute()
    doc.saveAs(str(fcstd_path))

    # ------------------------------------------------------------------
    # 6. Export STEP (universal exchange format)
    # ------------------------------------------------------------------
    plate.exportStep(str(step_path))

    # ------------------------------------------------------------------
    # 7. Write success result
    # ------------------------------------------------------------------
    result["success"]    = True
    result["fcstd_path"] = str(fcstd_path)
    result["step_path"]  = str(step_path)
    result["warnings"]   = warnings


# NOTE: freecadcmd.exe sets __name__ to the module name (e.g. "freecad_generate"),
# NOT to "__main__". The guard below is kept for completeness but the unconditional
# call ensures execution in both contexts.
if __name__ == "__main__":
    main()
else:
    main()
