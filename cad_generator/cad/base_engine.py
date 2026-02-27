"""
Abstract base class (interface) for CAD engine adapters.

New CAD engines (SolidWorks, Inventor) implement this interface.
The application layer (PieceController) calls only this interface,
never engine-specific methods, keeping the GUI/logic decoupled from
the specific CAD tool in use.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GenerationResult:
    """Outcome of a CAD generation run."""
    success: bool
    fcstd_path: Optional[Path] = None
    step_path: Optional[Path] = None
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class ICADEngine(abc.ABC):
    """
    Interface for CAD generation engines.
    All implementations must be stateless between calls.
    """

    @abc.abstractmethod
    def generate(
        self,
        piece_code: str,
        parameters: dict,
        output_dir: Path,
        revision_code: str,
    ) -> GenerationResult:
        """
        Generate a 3D model from piece_code and parameters.

        Args:
            piece_code: Identifier matching piece_catalog.json code field.
            parameters: Dict of parameter name -> value (already validated).
            output_dir: Directory where output files will be written.
            revision_code: Used to build output filenames (e.g., "A", "B").

        Returns:
            GenerationResult with paths to generated files.
        """
        ...

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying CAD engine is installed and reachable."""
        ...

    @abc.abstractmethod
    def get_engine_name(self) -> str:
        """Return human-readable engine name, e.g., 'FreeCAD 1.0'."""
        ...
