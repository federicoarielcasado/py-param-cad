"""
SolidWorks CAD engine adapter — Phase 2 stub.

Will use win32com to drive SolidWorks COM API.
Requires SolidWorks license and win32com (pywin32) installed.

TODO Fase 2: Implement SolidWorks COM adapter.
"""

from __future__ import annotations

from pathlib import Path

from cad_generator.cad.base_engine import GenerationResult, ICADEngine


class SolidWorksEngine(ICADEngine):

    def generate(
        self,
        piece_code: str,
        parameters: dict,
        output_dir: Path,
        revision_code: str,
    ) -> GenerationResult:
        raise NotImplementedError(
            "Motor SolidWorks — implementar en Fase 2 con win32com COM API."
        )

    def is_available(self) -> bool:
        try:
            import win32com.client  # noqa: F401
            return True
        except ImportError:
            return False

    def get_engine_name(self) -> str:
        return "SolidWorks (Fase 2)"
