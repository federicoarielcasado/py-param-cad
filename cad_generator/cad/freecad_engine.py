"""
FreeCAD CAD engine adapter.

Calls FreeCAD as a subprocess using freecadcmd.exe.

Communication protocol:
  1. Write parameters to a temp JSON file.
  2. Invoke: freecadcmd.exe <freecad_generate.py> <params.json>
  3. Read result.json written by the script to output_dir.
  4. Clean up the temp params file.

This subprocess isolation is REQUIRED because FreeCAD 1.0 bundles its own
Python 3.11 interpreter, which conflicts with the project's Python 3.12.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from cad_generator.cad.base_engine import GenerationResult, ICADEngine
from cad_generator.config.settings import settings


class FreeCADEngine(ICADEngine):

    def generate(
        self,
        piece_code: str,
        parameters: dict,
        output_dir: Path,
        revision_code: str,
    ) -> GenerationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()

        # Write parameters to a temporary JSON file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(
                {
                    "piece_code": piece_code,
                    "parameters": parameters,
                    "output_dir": str(output_dir),
                    "revision_code": revision_code,
                },
                tmp,
                ensure_ascii=False,
            )
            params_file = Path(tmp.name)

        try:
            # Pass the params path via env var — NOT as a positional argument.
            # freecadcmd.exe treats positional args as documents to open and
            # dispatches .json files to FEM importers, causing failures.
            env = os.environ.copy()
            env["FREECAD_PARAMS"] = str(params_file)

            proc = subprocess.run(
                [
                    str(settings.freecad_bin),
                    str(settings.freecad_script),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=settings.freecad_timeout_seconds,
            )

            elapsed = time.monotonic() - start
            result_file = output_dir / "result.json"

            if proc.returncode != 0 or not result_file.exists():
                return GenerationResult(
                    success=False,
                    error_message=(
                        f"FreeCAD subprocess fall\u00f3 (returncode={proc.returncode}).\n"
                        f"stderr: {proc.stderr[:500]}"
                    ),
                    elapsed_seconds=elapsed,
                )

            result_data = json.loads(result_file.read_text(encoding="utf-8"))
            return GenerationResult(
                success=result_data.get("success", False),
                fcstd_path=(
                    Path(result_data["fcstd_path"])
                    if result_data.get("fcstd_path")
                    else None
                ),
                step_path=(
                    Path(result_data["step_path"])
                    if result_data.get("step_path")
                    else None
                ),
                error_message=result_data.get("error_message"),
                warnings=result_data.get("warnings", []),
                elapsed_seconds=elapsed,
            )

        except subprocess.TimeoutExpired:
            return GenerationResult(
                success=False,
                error_message=(
                    f"FreeCAD agot\u00f3 el tiempo l\u00edmite "
                    f"({settings.freecad_timeout_seconds}s)."
                ),
                elapsed_seconds=float(settings.freecad_timeout_seconds),
            )
        finally:
            params_file.unlink(missing_ok=True)

    def is_available(self) -> bool:
        return settings.freecad_bin.exists()

    def get_engine_name(self) -> str:
        return "FreeCAD 1.0"
