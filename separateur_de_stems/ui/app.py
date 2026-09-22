"""Application entry point for the PySide6 desktop interface."""

import argparse
import sys

from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.settings import Settings

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="separateur-de-stems-ui",
        description="Desktop stem separator.",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Audio file to open at launch.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    settings = Settings()
    i18n.install_translators(app, settings.language)
    window = MainWindow(settings=settings)
    window.show()

    if args.file:
        window.open_file(args.file)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
