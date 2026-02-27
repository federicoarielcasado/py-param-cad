"""
PieceController — Application layer facade/orchestrator.

Coordinates between:
  - Data layer (repositories)
  - Validation engine
  - CAD engine adapter
  - BOM generator
  - Revision manager

The GUI layer calls only PieceController, never repositories or engines directly.
This enforces the layered architecture and keeps GUI tests simple.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cad_generator.config.settings import settings
from cad_generator.data.database import get_session
from cad_generator.data.models import Design, PieceType, Revision
from cad_generator.data.repositories import (
    BOMRepository,
    DesignRepository,
    PieceTypeRepository,
    RevisionRepository,
)


@dataclass
class GenerationRequest:
    design_id: int
    parameters: dict
    description: str = ""


@dataclass
class GenerationResponse:
    success: bool
    revision_id: Optional[int] = None
    revision_code: Optional[str] = None
    output_dir: Optional[Path] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class PieceController:
    """
    Facade for all piece-related operations.
    Instantiate once and reuse; it is stateless between calls.
    """

    def __init__(self) -> None:
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from cad_generator.cad.freecad_engine import FreeCADEngine
            self._engine = FreeCADEngine()
        return self._engine

    def get_all_piece_types(self) -> list:
        with get_session() as session:
            repo = PieceTypeRepository(session)
            results = repo.get_all_active()
            for pt in results:
                session.expunge(pt)
            return results

    def get_piece_type_by_code(self, code: str):
        with get_session() as session:
            repo = PieceTypeRepository(session)
            pt = repo.get_by_code(code)
            if pt:
                session.expunge(pt)
            return pt

    def create_design(
        self,
        piece_type_code: str,
        name: str,
        description: str = "",
        drawing_number: Optional[str] = None,
    ) -> Optional[Design]:
        with get_session() as session:
            pt_repo = PieceTypeRepository(session)
            piece_type = pt_repo.get_by_code(piece_type_code)
            if not piece_type:
                return None
            d_repo = DesignRepository(session)
            design = d_repo.create(
                piece_type_id=piece_type.id,
                name=name,
                description=description,
                drawing_number=drawing_number,
            )
            session.commit()
            session.expunge(design)
            return design

    def get_all_designs(self) -> list[Design]:
        with get_session() as session:
            repo = DesignRepository(session)
            designs = repo.get_all()
            for d in designs:
                session.expunge(d)
            return designs

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """
        Full generation pipeline:
        1. Resolve design → piece_type → piece_code
        2. Validate parameters (abort on errors)
        3. Create revision record in DB (stores validation snapshot)
        4. Run CAD engine subprocess
        5. Update revision with output file paths
        6. Return GenerationResponse
        """
        from cad_generator.config.catalog_loader import catalog
        from cad_generator.core.validation_engine import ValidationEngine

        # ------------------------------------------------------------------
        # Step 1 — resolve design and piece type
        # ------------------------------------------------------------------
        with get_session() as session:
            design = DesignRepository(session).get_by_id(request.design_id)
            if design is None:
                return GenerationResponse(
                    success=False, errors=["Diseño no encontrado."]
                )
            piece_type = session.get(PieceType, design.piece_type_id)
            if piece_type is None:
                return GenerationResponse(
                    success=False, errors=["Tipo de pieza no encontrado."]
                )
            piece_code  = piece_type.code
            design_name = design.name
            session.expunge(design)
            session.expunge(piece_type)

        # ------------------------------------------------------------------
        # Step 2 — validate parameters (no side-effects)
        # ------------------------------------------------------------------
        rules      = catalog.get_validation_rules(piece_code)
        validation = ValidationEngine().validate(request.parameters, rules)

        if not validation.is_valid:
            return GenerationResponse(
                success=False,
                errors=[m.message for m in validation.errors],
                warnings=[m.message for m in validation.warnings],
            )

        warning_msgs = [m.message for m in validation.warnings]

        # ------------------------------------------------------------------
        # Step 3 — create revision record (code is assigned here: A, B, …)
        # ------------------------------------------------------------------
        with get_session() as session:
            rev_repo = RevisionRepository(session)
            rev = rev_repo.create(
                design_id=request.design_id,
                parameters=request.parameters,
                description=request.description,
            )
            rev.validation_passed = 1
            rev.validation_warnings_json = (
                json.dumps(warning_msgs) if warning_msgs else None
            )
            session.commit()
            revision_id   = rev.id
            revision_code = rev.revision_code
            session.expunge(rev)

        # ------------------------------------------------------------------
        # Step 4 — build output directory and run CAD engine
        # ------------------------------------------------------------------
        safe_name  = re.sub(r"[^\w\-]", "_", design_name)
        output_dir = settings.outputs_dir / piece_code / safe_name / revision_code
        output_dir.mkdir(parents=True, exist_ok=True)

        cad_result = self.engine.generate(
            piece_code=piece_code,
            parameters=request.parameters,
            output_dir=output_dir,
            revision_code=revision_code,
        )

        # ------------------------------------------------------------------
        # Step 5 — persist output paths (even on partial success)
        # ------------------------------------------------------------------
        with get_session() as session:
            rev_repo = RevisionRepository(session)
            if cad_result.success:
                rev_repo.update_output_paths(
                    revision_id,
                    {
                        "fcstd": str(cad_result.fcstd_path) if cad_result.fcstd_path else None,
                        "step":  str(cad_result.step_path)  if cad_result.step_path  else None,
                    },
                )
            session.commit()

        # ------------------------------------------------------------------
        # Step 6 — return result
        # ------------------------------------------------------------------
        all_warnings = warning_msgs + cad_result.warnings

        if cad_result.success:
            return GenerationResponse(
                success=True,
                revision_id=revision_id,
                revision_code=revision_code,
                output_dir=output_dir,
                warnings=all_warnings,
                elapsed_seconds=cad_result.elapsed_seconds,
            )
        else:
            return GenerationResponse(
                success=False,
                revision_id=revision_id,
                revision_code=revision_code,
                output_dir=output_dir,
                errors=[cad_result.error_message or "Error desconocido en el motor CAD."],
                warnings=all_warnings,
                elapsed_seconds=cad_result.elapsed_seconds,
            )

    def get_revisions_for_design(self, design_id: int) -> list[Revision]:
        with get_session() as session:
            repo = RevisionRepository(session)
            revisions = repo.get_by_design(design_id)
            for rev in revisions:
                session.expunge(rev)
            return revisions
