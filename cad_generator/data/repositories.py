"""
Repository classes for data access.

Each repository operates on a single aggregate root.
All methods accept an explicit Session argument — the caller (typically
PieceController in core/) is responsible for session lifecycle.

Example:
    with get_session() as session:
        repo = DesignRepository(session)
        design = repo.get_by_id(1)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from cad_generator.data.models import BOMItem, Design, PieceType, Revision


class PieceTypeRepository:
    """Read-only access to piece type catalog."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all_active(self) -> list[PieceType]:
        return (
            self._session.query(PieceType)
            .filter(PieceType.is_active == 1)
            .order_by(PieceType.discipline, PieceType.category, PieceType.display_name)
            .all()
        )

    def get_by_code(self, code: str) -> Optional[PieceType]:
        return (
            self._session.query(PieceType)
            .filter(PieceType.code == code)
            .first()
        )

    def get_by_discipline(self, discipline: str) -> list[PieceType]:
        return (
            self._session.query(PieceType)
            .filter(PieceType.discipline == discipline, PieceType.is_active == 1)
            .order_by(PieceType.category, PieceType.display_name)
            .all()
        )


class DesignRepository:
    """CRUD operations for Design entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, design_id: int) -> Optional[Design]:
        return self._session.get(Design, design_id)

    def get_all(self) -> list[Design]:
        return (
            self._session.query(Design)
            .order_by(Design.updated_at.desc())
            .all()
        )

    def get_by_piece_type(self, piece_type_id: int) -> list[Design]:
        return (
            self._session.query(Design)
            .filter(Design.piece_type_id == piece_type_id)
            .order_by(Design.updated_at.desc())
            .all()
        )

    def create(
        self,
        piece_type_id: int,
        name: str,
        description: str = "",
        drawing_number: Optional[str] = None,
    ) -> Design:
        design = Design(
            piece_type_id=piece_type_id,
            name=name,
            description=description,
            drawing_number=drawing_number,
        )
        self._session.add(design)
        self._session.flush()  # populate id without committing
        return design

    def update_name(self, design_id: int, name: str) -> Optional[Design]:
        design = self.get_by_id(design_id)
        if design:
            design.name = name
            design.updated_at = datetime.now(timezone.utc).isoformat()
        return design

    def delete(self, design_id: int) -> bool:
        design = self.get_by_id(design_id)
        if design:
            self._session.delete(design)
            return True
        return False


class RevisionRepository:
    """Append-only access to Revision entities (create + read; no arbitrary updates)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, revision_id: int) -> Optional[Revision]:
        return self._session.get(Revision, revision_id)

    def get_by_design(self, design_id: int) -> list[Revision]:
        return (
            self._session.query(Revision)
            .filter(Revision.design_id == design_id)
            .order_by(Revision.generated_at.asc())
            .all()
        )

    def get_latest_for_design(self, design_id: int) -> Optional[Revision]:
        # Order by id (monotonically increasing autoincrement) — safer than
        # generated_at which can collide when two revisions are created within
        # the same millisecond (common in tests and fast bulk operations).
        return (
            self._session.query(Revision)
            .filter(Revision.design_id == design_id)
            .order_by(Revision.id.desc())
            .first()
        )

    def get_next_revision_code(self, design_id: int) -> str:
        """Generate the next alphabetic revision code for a design (A, B, ... Z, AA, ...)."""
        revisions = self.get_by_design(design_id)
        if not revisions:
            return "A"
        return _increment_revision_code(revisions[-1].revision_code)

    def create(
        self,
        design_id: int,
        parameters: dict,
        description: str = "",
        generated_by: str = "Fede",
    ) -> Revision:
        revision_code = self.get_next_revision_code(design_id)
        rev = Revision(
            design_id=design_id,
            revision_code=revision_code,
            description=description,
            generated_by=generated_by,
        )
        rev.parameters = parameters  # uses the property setter to serialize JSON
        self._session.add(rev)
        self._session.flush()
        return rev

    def update_eco_status(
        self,
        revision_id: int,
        status: str,
        eco_number: Optional[str] = None,
        eco_reason: Optional[str] = None,
    ) -> Optional[Revision]:
        """The ONLY permitted mutation on a Revision: changing its ECO lifecycle status."""
        allowed = {"draft", "issued", "obsolete"}
        if status not in allowed:
            raise ValueError(f"eco_status must be one of {allowed}, got {status!r}")
        rev = self.get_by_id(revision_id)
        if rev:
            rev.eco_status = status
            if eco_number is not None:
                rev.eco_number = eco_number
            if eco_reason is not None:
                rev.eco_reason = eco_reason
        return rev

    def update_output_paths(self, revision_id: int, paths: dict) -> Optional[Revision]:
        """
        Set file output paths after CAD generation completes.

        Args:
            paths: dict with optional keys: 'fcstd', 'step', 'dxf', 'pdf',
                   'bom_xlsx', 'bom_pdf'. Values are path strings.
        """
        rev = self.get_by_id(revision_id)
        if rev:
            rev.fcstd_path = paths.get("fcstd")
            rev.step_path = paths.get("step")
            rev.dxf_path = paths.get("dxf")
            rev.pdf_path = paths.get("pdf")
            rev.bom_xlsx_path = paths.get("bom_xlsx")
            rev.bom_pdf_path = paths.get("bom_pdf")
        return rev


class BOMRepository:
    """Access to BOM line items."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_revision(self, revision_id: int) -> list[BOMItem]:
        return (
            self._session.query(BOMItem)
            .filter(BOMItem.revision_id == revision_id)
            .order_by(BOMItem.item_number.asc())
            .all()
        )

    def create_items(self, revision_id: int, items: list[dict]) -> list[BOMItem]:
        """
        Bulk-create BOM items for a revision.

        Args:
            items: list of dicts with keys matching BOMItem columns.
                   item_number is auto-assigned based on list order (1-based).
        """
        created = []
        for idx, item_data in enumerate(items, start=1):
            bom_item = BOMItem(
                revision_id=revision_id,
                item_number=idx,
                description=item_data["description"],
                quantity=item_data.get("quantity", 1.0),
                unit=item_data.get("unit", "UN"),
                part_code=item_data.get("part_code"),
                material=item_data.get("material"),
                standard=item_data.get("standard"),
                unit_weight_kg=item_data.get("unit_weight_kg"),
                observations=item_data.get("observations"),
            )
            self._session.add(bom_item)
            created.append(bom_item)
        self._session.flush()
        return created


def _increment_revision_code(code: str) -> str:
    """
    Increment an alphabetic revision code.

    Examples:
        'A'  -> 'B'
        'Z'  -> 'AA'
        'AA' -> 'AB'
        'AZ' -> 'BA'
        'ZZ' -> 'AAA'
    """
    chars = list(code.upper())
    carry = True
    idx = len(chars) - 1
    while carry and idx >= 0:
        if chars[idx] == "Z":
            chars[idx] = "A"
            idx -= 1
        else:
            chars[idx] = chr(ord(chars[idx]) + 1)
            carry = False
    if carry:
        chars.insert(0, "A")
    return "".join(chars)
