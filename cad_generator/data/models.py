"""
SQLAlchemy ORM models for py-param-cad.

Uses SQLAlchemy 2.0 declarative style with Mapped[] type annotations.
All timestamps are stored as UTC strings in ISO-8601 format.
Parameters are serialized to JSON text columns.

Relationships:
    piece_types (1) ──< designs (1) ──< revisions (1) ──< bom_items
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow_str() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class PieceType(Base):
    """
    Canonical piece type definitions.
    Populated at DB initialization from piece_catalog.json.
    Treated as read-only during normal application operation.
    """
    __tablename__ = "piece_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catalog_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_utcnow_str)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_utcnow_str)

    designs: Mapped[list[Design]] = relationship("Design", back_populates="piece_type")

    def __repr__(self) -> str:
        return f"<PieceType code={self.code!r} name={self.display_name!r}>"


class Design(Base):
    """
    A user-created design project, associated with one piece type.
    Analogous to a "file" or "project" in the user's workspace.
    """
    __tablename__ = "designs"
    __table_args__ = (
        UniqueConstraint("drawing_number", name="uq_designs_drawing_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    piece_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("piece_types.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drawing_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_utcnow_str)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_utcnow_str)

    piece_type: Mapped[PieceType] = relationship("PieceType", back_populates="designs")
    revisions: Mapped[list[Revision]] = relationship(
        "Revision", back_populates="design", order_by="Revision.generated_at"
    )

    @property
    def latest_revision(self) -> Optional[Revision]:
        """Returns the most recently generated revision, or None."""
        return self.revisions[-1] if self.revisions else None

    def __repr__(self) -> str:
        return f"<Design id={self.id} name={self.name!r} drawing={self.drawing_number!r}>"


class Revision(Base):
    """
    An immutable snapshot of a generated model.
    Created once per generation run; never mutated (only eco_status changes).
    """
    __tablename__ = "revisions"
    __table_args__ = (
        UniqueConstraint("design_id", "revision_code", name="uq_revisions_design_rev"),
        CheckConstraint(
            "eco_status IN ('draft', 'issued', 'obsolete')",
            name="ck_revisions_eco_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    design_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("designs.id"), nullable=False
    )
    revision_code: Mapped[str] = mapped_column(String(8), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_utcnow_str)
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="Fede")
    # Output file paths (relative to outputs/ dir)
    fcstd_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    step_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    dxf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    bom_xlsx_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    bom_pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # ECO fields
    eco_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    eco_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eco_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    # Validation snapshot
    validation_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    design: Mapped[Design] = relationship("Design", back_populates="revisions")
    bom_items: Mapped[list[BOMItem]] = relationship(
        "BOMItem", back_populates="revision", order_by="BOMItem.item_number"
    )

    @property
    def parameters(self) -> dict:
        """Deserialize parameters JSON to dict."""
        return json.loads(self.parameters_json)

    @parameters.setter
    def parameters(self, value: dict) -> None:
        """Serialize parameters dict to JSON."""
        self.parameters_json = json.dumps(value, ensure_ascii=False)

    @property
    def validation_warnings(self) -> list[str]:
        """Deserialize warnings JSON to list."""
        if not self.validation_warnings_json:
            return []
        return json.loads(self.validation_warnings_json)

    def __repr__(self) -> str:
        return (
            f"<Revision id={self.id} design_id={self.design_id} "
            f"rev={self.revision_code!r} eco_status={self.eco_status!r}>"
        )


class BOMItem(Base):
    """
    A single line item in a Bill of Materials, belonging to one Revision.
    Stored as structured rows (not JSON) for direct query and export capability.
    """
    __tablename__ = "bom_items"
    __table_args__ = (
        UniqueConstraint("revision_id", "item_number", name="uq_bom_item_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("revisions.id"), nullable=False
    )
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    part_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[float] = mapped_column(nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="UN")
    material: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    standard: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    unit_weight_kg: Mapped[Optional[float]] = mapped_column(nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    revision: Mapped[Revision] = relationship("Revision", back_populates="bom_items")

    @property
    def total_weight_kg(self) -> Optional[float]:
        if self.unit_weight_kg is not None:
            return self.unit_weight_kg * self.quantity
        return None

    def __repr__(self) -> str:
        return (
            f"<BOMItem item={self.item_number} qty={self.quantity} "
            f"desc={self.description[:30]!r}>"
        )


# Explicit index definitions (SQLAlchemy emits CREATE INDEX on create_all)
Index("idx_revisions_design_id", Revision.design_id)
Index("idx_revisions_eco_status", Revision.eco_status)
Index("idx_bom_items_revision_id", BOMItem.revision_id)
Index("idx_designs_piece_type_id", Design.piece_type_id)
