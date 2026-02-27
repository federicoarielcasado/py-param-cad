"""
Application entry point.

Responsibilities:
  1. Initialize the database (create tables, seed piece catalog).
  2. Create and show the main window.
  3. Start the Qt event loop.

Keep this file minimal. All initialization logic belongs in its respective module.
"""

import sys

from PyQt6.QtWidgets import QApplication

from cad_generator.config.settings import settings
from cad_generator.data.database import init_db
from cad_generator.gui.main_window import MainWindow


def main() -> int:
    # Initialize database before creating the GUI
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.app_version)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
