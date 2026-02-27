"""
CatalogWidget — Piece type catalog browser.

Displays available piece types in a QTreeWidget organized by:
  Discipline (e.g., "Estructural")
    └─ Category (e.g., "Base")
         └─ Piece (e.g., "Placa Base Estructural")

Emits piece_selected(piece_code) when the user double-clicks a piece.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cad_generator.config.catalog_loader import catalog

# Human-readable labels for discipline codes
_DISCIPLINE_LABELS: dict[str, str] = {
    "structural": "Estructural",
    "mechanical": "Mecánica",
    "electrical": "Eléctrica",
    "civil":      "Civil",
}

# Human-readable labels for category codes
_CATEGORY_LABELS: dict[str, str] = {
    "base":    "Bases",
    "frame":   "Marcos",
    "bracket": "Soportes",
    "fitting": "Accesorios",
}


class CatalogWidget(QWidget):
    """
    Sidebar catalog browser.
    Signal piece_selected emits the piece code (str) on double-click.
    """

    piece_selected = pyqtSignal(str)   # emits piece_code

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._populate()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("Catálogo de Piezas")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title.setFont(title_font)
        title.setContentsMargins(8, 8, 8, 4)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setMinimumWidth(200)
        self._tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                background-color: #F5F5F5;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px 6px;
            }
            QTreeWidget::item:selected {
                background-color: #0070C0;
                color: white;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #DDEEFF;
            }
        """)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(title)
        layout.addWidget(self._tree)

    def _populate(self) -> None:
        """Load pieces from the catalog and populate the tree."""
        self._tree.clear()

        # Organize pieces: discipline → category → [pieces]
        organized: dict[str, dict[str, list]] = {}
        for piece in catalog.get_all_pieces():
            disc = organized.setdefault(piece.discipline, {})
            disc.setdefault(piece.category, []).append(piece)

        for discipline, categories in sorted(organized.items()):
            disc_label = _DISCIPLINE_LABELS.get(discipline, discipline.title())
            disc_item = QTreeWidgetItem([f"📐  {disc_label}"])
            disc_item.setData(0, Qt.ItemDataRole.UserRole, None)
            disc_font = QFont()
            disc_font.setBold(True)
            disc_item.setFont(0, disc_font)
            self._tree.addTopLevelItem(disc_item)

            for category, pieces in sorted(categories.items()):
                cat_label = _CATEGORY_LABELS.get(category, category.title())
                cat_item = QTreeWidgetItem([f"  {cat_label}"])
                cat_item.setData(0, Qt.ItemDataRole.UserRole, None)
                disc_item.addChild(cat_item)

                for piece in sorted(pieces, key=lambda p: p.display_name):
                    piece_item = QTreeWidgetItem([f"    {piece.display_name}"])
                    piece_item.setData(0, Qt.ItemDataRole.UserRole, piece.code)
                    piece_item.setToolTip(0, piece.description)
                    cat_item.addChild(piece_item)

            disc_item.setExpanded(True)

        # Expand all category items
        self._tree.expandAll()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        piece_code = item.data(0, Qt.ItemDataRole.UserRole)
        if piece_code:
            self.piece_selected.emit(piece_code)
