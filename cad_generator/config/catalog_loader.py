"""
CatalogLoader — utility for reading and querying piece_catalog.json.

Provides typed access to piece definitions, parameter specs, and validation
rules without parsing JSON scattered across the application.

Usage:
    from cad_generator.config.catalog_loader import CatalogLoader
    loader = CatalogLoader()
    piece = loader.get_piece("base_plate")
    params = loader.get_parameters("base_plate")
    rules  = loader.get_validation_rules("base_plate")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from cad_generator.config.settings import settings


# ---------------------------------------------------------------------------
# Data classes for typed access to catalog data
# ---------------------------------------------------------------------------

@dataclass
class ParameterOption:
    value: str
    label: str


@dataclass
class ParameterSpec:
    name: str
    display_name: str
    unit: str
    type: str                           # "float" | "enum" | "bool"
    default: Any
    description: str
    schematic_image: Optional[str] = None
    # float-specific
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    # enum-specific
    options: list[ParameterOption] = field(default_factory=list)
    # conditional visibility
    depends_on: dict = field(default_factory=dict)   # e.g. {"tiene_ranuras": True}


@dataclass
class ValidationRule:
    rule_id: str
    description: str
    expression: str
    severity: str                       # "error" | "warning"
    message: str


@dataclass
class BOMTemplateItem:
    item_number: int
    part_code: str
    description: str
    quantity: float
    unit: str
    material_param: Optional[str]       # name of parameter that provides material
    standard: str
    observations: str


@dataclass
class PieceSpec:
    code: str
    display_name: str
    discipline: str
    category: str
    description: str
    parameters: list[ParameterSpec]
    validation_rules: list[ValidationRule]
    bom_template: list[BOMTemplateItem]
    cad_script: str
    drawing_views: list[str]

    def get_parameter(self, name: str) -> Optional[ParameterSpec]:
        return next((p for p in self.parameters if p.name == name), None)

    def get_defaults(self) -> dict:
        """Return a dict of {param_name: default_value} for all parameters."""
        return {p.name: p.default for p in self.parameters}


# ---------------------------------------------------------------------------
# Loader class
# ---------------------------------------------------------------------------

class CatalogLoader:
    """
    Loads and parses piece_catalog.json.
    The parsed catalog is cached in memory after the first load.
    """

    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        self._path = catalog_path or settings.catalog_path
        self._pieces: dict[str, PieceSpec] = {}
        self._raw: dict = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._raw = raw
        for piece_data in raw.get("pieces", []):
            self._pieces[piece_data["code"]] = self._parse_piece(piece_data)
        self._loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_pieces(self) -> list[PieceSpec]:
        self._ensure_loaded()
        return list(self._pieces.values())

    def get_piece(self, code: str) -> Optional[PieceSpec]:
        self._ensure_loaded()
        return self._pieces.get(code)

    def get_parameters(self, code: str) -> list[ParameterSpec]:
        piece = self.get_piece(code)
        return piece.parameters if piece else []

    def get_validation_rules(self, code: str) -> list[dict]:
        """Return validation rules as raw dicts (for ValidationEngine.validate())."""
        self._ensure_loaded()
        piece_data = next(
            (p for p in self._raw.get("pieces", []) if p["code"] == code), None
        )
        return piece_data.get("validation_rules", []) if piece_data else []

    def get_disciplines(self) -> list[str]:
        """Return sorted list of unique disciplines in the catalog."""
        self._ensure_loaded()
        return sorted({p.discipline for p in self._pieces.values()})

    def get_pieces_by_discipline(self, discipline: str) -> list[PieceSpec]:
        self._ensure_loaded()
        return [p for p in self._pieces.values() if p.discipline == discipline]

    def get_pieces_by_category(self, discipline: str, category: str) -> list[PieceSpec]:
        self._ensure_loaded()
        return [
            p for p in self._pieces.values()
            if p.discipline == discipline and p.category == category
        ]

    def get_schematic_path(self, piece_code: str, image_rel: str) -> Optional[Path]:
        """Resolve a schematic image relative path to an absolute asset path."""
        if not image_rel:
            return None
        assets_dir = self._path.parent.parent / "assets" / "schematics"
        full_path = assets_dir / image_rel
        return full_path if full_path.exists() else None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_piece(self, data: dict) -> PieceSpec:
        return PieceSpec(
            code=data["code"],
            display_name=data["display_name"],
            discipline=data["discipline"],
            category=data["category"],
            description=data.get("description", ""),
            parameters=[self._parse_param(p) for p in data.get("parameters", [])],
            validation_rules=[self._parse_rule(r) for r in data.get("validation_rules", [])],
            bom_template=[self._parse_bom_item(b) for b in data.get("bom_template", [])],
            cad_script=data.get("cad_script", ""),
            drawing_views=data.get("drawing_views", []),
        )

    @staticmethod
    def _parse_param(data: dict) -> ParameterSpec:
        options = [
            ParameterOption(value=o["value"], label=o["label"])
            for o in data.get("options", [])
        ]
        return ParameterSpec(
            name=data["name"],
            display_name=data["display_name"],
            unit=data.get("unit", ""),
            type=data["type"],
            default=data["default"],
            description=data.get("description", ""),
            schematic_image=data.get("schematic_image"),
            min=data.get("min"),
            max=data.get("max"),
            step=data.get("step"),
            options=options,
            depends_on=data.get("depends_on", {}),
        )

    @staticmethod
    def _parse_rule(data: dict) -> ValidationRule:
        return ValidationRule(
            rule_id=data["rule_id"],
            description=data.get("description", ""),
            expression=data["expression"],
            severity=data.get("severity", "error"),
            message=data["message"],
        )

    @staticmethod
    def _parse_bom_item(data: dict) -> BOMTemplateItem:
        return BOMTemplateItem(
            item_number=data.get("item_number", 1),
            part_code=data.get("part_code", ""),
            description=data.get("description", ""),
            quantity=data.get("quantity", 1),
            unit=data.get("unit", "UN"),
            material_param=data.get("material_param"),
            standard=data.get("standard", ""),
            observations=data.get("observations", ""),
        )


# Module-level singleton
catalog = CatalogLoader()
