"""The example data behind the CI page previews must match what the app loads."""

from pathlib import Path

import pytest

from tamarack.brand import Brand

ROOT = Path(__file__).resolve().parents[1]


def test_demo_refresh_labels_exist_in_backend() -> None:
    pytest.importorskip("PySide6")
    from tamarack.ui import demo

    source = (ROOT / "src/tamarack/ui/backend.py").read_text(encoding="utf-8")
    for label in demo.REFRESHES:
        assert f'"{label}' in source, f"Backend has no refresh labelled {label!r}"


def test_install_and_preview_accept_javascript_values(brand: Brand, tmp_path: Path) -> None:
    """QML passes arrays and objects as QJSValue; the slots must accept them."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine

    from tamarack.ui import demo

    # A JavaScript engine needs an application object (Qt aborts otherwise).
    _app = QCoreApplication.instance() or QCoreApplication([])  # kept alive for the test
    engine = QJSEngine()
    backend = demo.DemoBackend(brand, tmp_path, tmp_path)
    backend.installApps(engine.evaluate('["org.kde.kate", "org.kde.filelight"]'))
    assert backend.requests == ["Installing 2 apps from Flathub"]
    preview = backend.previewCustom(engine.evaluate('({"base": "clean-modern", "name": "Mine", "fontSize": 11})'))
    assert preview.endswith(".svg")


def test_demo_backend_builds_every_page(brand: Brand, tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from tamarack.ui import demo

    backend = demo.DemoBackend(brand, tmp_path, tmp_path)
    backend.refreshDoctor()
    backend.refreshBundles()
    backend.refreshPrivacy()
    backend.refreshPresets()
    assert backend.doctor["problems"]
    assert {b["id"] for b in backend.bundles} >= {"gaming", "office"}
    assert all(app["name"] != app["app_id"] for app in backend.privacy["apps"])
    assert any(p["current"] for p in backend.presets)
    assert backend.searchResults and backend.searchQuery == "tux"
