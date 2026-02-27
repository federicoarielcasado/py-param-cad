"""
Application-wide configuration via pydantic-settings.

All paths are resolved at load time to absolute Path objects.
Override any setting via environment variable prefixed with CAD_
e.g., set CAD_DB_ECHO=true to enable SQLAlchemy query logging.

The project root is the directory containing the cad_generator/ package.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used for paths that must be resolved at runtime.
# Path("") becomes "." on Windows, so we use None instead.
_UNSET: Path = Path("__UNSET__")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CAD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application metadata ---
    app_name: str = "Parametric CAD Generator"
    app_version: str = "0.1.0"
    default_author: str = "Fede"

    # --- Paths (resolved in model_post_init) ---
    project_root: Path = Path(__file__).resolve().parent.parent.parent

    # --- Database ---
    db_path: Optional[Path] = None    # resolved in model_post_init
    db_echo: bool = False             # set True to log all SQL queries

    # --- FreeCAD subprocess ---
    freecad_bin: Path = Path(r"C:/Program Files/FreeCAD 1.0/bin/freecadcmd.exe")
    freecad_script: Optional[Path] = None   # resolved in model_post_init
    freecad_timeout_seconds: int = 60

    # --- Output directories ---
    outputs_dir: Optional[Path] = None      # resolved in model_post_init

    # --- Catalog ---
    catalog_path: Optional[Path] = None     # resolved in model_post_init

    # --- Drawing standards ---
    drawing_standard: str = "IRAM4505"   # "IRAM4505" | "ISO128" | "ASME_Y14.5"
    company_name: str = ""
    company_logo_path: Optional[Path] = None

    # --- DXF/Drawing defaults ---
    default_line_weight: float = 0.25     # mm
    default_text_height: float = 3.5      # mm
    default_scale: str = "1:1"

    # --- BOM defaults ---
    default_bom_unit: str = "UN"

    def model_post_init(self, __context) -> None:
        """Resolve all None paths to absolute paths derived from project_root."""
        root = self.project_root

        if self.db_path is None:
            object.__setattr__(self, "db_path", root / "cad_generator.db")
        if self.outputs_dir is None:
            object.__setattr__(self, "outputs_dir", root / "outputs")
        if self.catalog_path is None:
            object.__setattr__(
                self, "catalog_path",
                root / "cad_generator" / "config" / "piece_catalog.json",
            )
        if self.freecad_script is None:
            object.__setattr__(
                self, "freecad_script",
                root / "cad_generator" / "cad" / "scripts" / "freecad_generate.py",
            )

        # Ensure output directory exists at settings load time
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton. Import this object; never instantiate Settings directly.
settings = Settings()
