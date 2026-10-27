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
