"""Tamarack Center entry point.

Usage:
  tamarack-center                    open the control center
  tamarack-center --welcome          open the first-run welcome flow
  tamarack-center --welcome --first-run-only
                                     only show it if it was never completed
  tamarack-center --page NAME        open a page (appearance, apps, gaming,
                                     hardware, privacy, updates, help)
  tamarack-center --self-test        load every QML file and exit (CI)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .. import logs
from ..brand import RUNTIME_BRAND_JSON, Brand, load_brand_toml, load_runtime_brand
from ..system import SubprocessRunner

QML_DIR = Path(__file__).with_name("qml")
PAGES = ("home", "appearance", "apps", "gaming", "hardware", "privacy", "updates", "help", "welcome")
log = logging.getLogger("tamarack.ui")


def _brand() -> Brand:
    if RUNTIME_BRAND_JSON.exists():
        return load_runtime_brand()
    # Development checkout (and CI): read the source configuration.
    return load_brand_toml(Path(__file__).resolve().parents[3] / "branding" / "brand.toml")


def welcome_done() -> bool:
    return (logs.state_dir() / "welcome-done").exists()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tamarack-center", description="Tamarack Center")
    parser.add_argument("--welcome", action="store_true", help="show the first-run welcome flow")
    parser.add_argument("--first-run-only", action="store_true", help="with --welcome: skip if already completed")
    parser.add_argument("--page", choices=PAGES, default="home")
    parser.add_argument("--self-test", action="store_true", help="load all QML files and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    # Qt adds its own arguments (e.g. -platform); ignore what we don't know.
    args, _unknown = parser.parse_known_args(argv[1:])
    return args


def self_test(engine: object, backend: object) -> int:
    """Compile and instantiate every page so QML errors fail CI, not users."""
    from PySide6.QtQml import QQmlComponent

    failures = 0
    for qml in sorted(QML_DIR.rglob("*.qml")):
        component = QQmlComponent(engine, str(qml))  # type: ignore[call-overload]
        if component.isError():
            failures += 1
            for error in component.errors():
                print(f"FAIL {qml.relative_to(QML_DIR)}: {error.toString()}")
            continue
        obj = component.create()
        if obj is None:
            failures += 1
            for error in component.errors():
                print(f"FAIL {qml.relative_to(QML_DIR)} (create): {error.toString()}")
            continue
        print(f"ok   {qml.relative_to(QML_DIR)}")
        obj.deleteLater()
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = parse_args(argv)
    logs.setup(verbose=args.verbose, log_file=None if args.self_test else logs.state_dir() / "tamarack-center.log")
    if args.welcome and args.first_run_only and welcome_done():
        return 0

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication

    from .backend import Backend

    brand = _brand()
    app = QApplication(argv)
    app.setApplicationName("tamarack-center")
    app.setApplicationDisplayName(f"{brand.short_name} Center")
    app.setOrganizationName(brand.short_name)
    app.setOrganizationDomain(".".join(reversed(brand.reverse_dns.split(".")[:3])))
    app.setDesktopFileName(brand.center_app_id)
    app.setWindowIcon(QIcon.fromTheme(brand.center_app_id, QIcon.fromTheme(brand.logo_icon)))
    if not QQuickStyle.name():
        QQuickStyle.setStyle("org.kde.desktop")
        QQuickStyle.setFallbackStyle("Fusion")

    backend = Backend(brand, SubprocessRunner(), welcome=args.welcome, dry_run=args.self_test)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("initialPage", "welcome" if args.welcome else args.page)

    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))

    if args.self_test:
        code = self_test(engine, backend)
        for warning in warnings:
            print(f"WARN {warning}")
        return code

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        for warning in warnings:
            log.error("QML error", extra={"detail": warning})
        print("Tamarack Center could not start; see ~/.local/state/tamarack/tamarack-center.log", file=sys.stderr)
        return 1
    backend.welcomeFinished.connect(lambda: app.quit() if args.welcome else None)
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
