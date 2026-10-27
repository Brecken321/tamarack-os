from pathlib import Path

import pytest

from tamarack import apps
from tamarack.system import FakeRunner

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "system_files/usr/share/tamarack/flatpaks/bundles.toml"
BASE_LIST = ROOT / "system_files/usr/share/tamarack/flatpaks/base.list"
MISSING = Path("/nonexistent/appstream")


def test_shipped_bundles_are_valid() -> None:
    bundles = apps.load_bundles(BUNDLES)
    ids = [b.id for b in bundles]
    assert {"gaming", "communication", "office", "creator", "media", "browsers", "development", "utilities"} <= set(ids)
    all_apps = [a for b in bundles for a in b.apps]
    assert len(all_apps) == len(set(all_apps)), "an app appears in two bundles"
    # Steam and Lutris are system packages; Bazzite blocks their Flatpaks.
    assert "com.valvesoftware.Steam" not in all_apps and "net.lutris.Lutris" not in all_apps


def test_base_list_is_small_and_valid() -> None:
    entries = [
        line.strip()
        for line in BASE_LIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert entries[0] == "org.mozilla.firefox"
    assert len(entries) <= 8, "the default install must stay minimal"
    for entry in entries:
        assert apps._APP_ID.match(entry), entry


@pytest.mark.parametrize("bad", ["firefox", "org.mozilla", "org.mozilla.firefox; rm -rf /", "-org.x.y"])
def test_install_rejects_invalid_ids(bad: str) -> None:
    with pytest.raises(ValueError):
        apps.install(FakeRunner(), [bad])


def test_bundle_state_and_install_command() -> None:
    runner = FakeRunner()
    runner.add(["flatpak", "list"], "org.libreoffice.LibreOffice\tLibreOffice\n")
    runner.add(["flatpak", "install"])
    state = {b["id"]: b for b in apps.bundles_with_state(runner, BUNDLES, MISSING)}
    assert state["office"]["installed_count"] == 1
    apps.install(runner, ["org.keepassxc.KeePassXC"])
    assert list(runner.calls[-1]) == [
        "flatpak",
        "install",
        "--system",
        "--noninteractive",
        "--or-update",
        "flathub",
        "org.keepassxc.KeePassXC",
    ]


def test_parse_rejects_bad_bundles() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        apps.parse_bundles({"bundle": [{"id": "a", "apps": ["org.a.b"]}, {"id": "a", "apps": ["org.c.d"]}]})
    with pytest.raises(ValueError, match="non-empty"):
        apps.parse_bundles({"bundle": [{"id": "a", "apps": []}]})


def test_apps_have_display_names() -> None:
    for bundle in apps.load_bundles(BUNDLES):
        for app_id in bundle.apps:
            assert bundle.name_of(app_id) != app_id, f"{app_id} needs a display name"
    runner = FakeRunner()
    runner.add(["flatpak", "list"], "")
    office = next(b for b in apps.bundles_with_state(runner, BUNDLES, MISSING) if b["id"] == "office")
    assert office["apps"][0] == {
        "id": "org.libreoffice.LibreOffice",
        "name": "LibreOffice",
        "installed": False,
        "icon": "",
    }


def test_bare_ids_are_still_accepted() -> None:
    (bundle,) = apps.parse_bundles({"bundle": [{"id": "x", "apps": ["org.a.b"]}]})
    assert bundle.apps == ("org.a.b",) and bundle.name_of("org.a.b") == "org.a.b"


# ``flatpak search --columns=application,name,description,remotes`` output: tab-separated.
SEARCH_OUTPUT = "".join(
    "\t".join(row) + "\n"
    for row in (
        ("org.supertuxproject.SuperTux", "SuperTux", "A jump-and-run game starring Tux the Penguin", "flathub"),
        ("org.kde.filelight", "Filelight", "View disk usage information", "flathub,kdeapps"),
        ("org.example.Local", "Local", "Only on another remote", "kdeapps"),
        ("org.supertuxproject.SuperTux", "SuperTux", "duplicate row", "flathub"),
        ("not an id", "Broken", "", "flathub"),
    )
)


def test_parse_search_keeps_valid_flathub_apps_once() -> None:
    results = apps.parse_search(SEARCH_OUTPUT + "No matches found\n")
    assert [r.id for r in results] == ["org.supertuxproject.SuperTux", "org.kde.filelight"]
    assert results[0].name == "SuperTux" and results[0].summary.startswith("A jump-and-run")


def test_search_marks_installed_apps_and_finds_icons(tmp_path: Path) -> None:
    icons = tmp_path / "icons/128x128"
    icons.mkdir(parents=True)
    (icons / "org.kde.filelight.png").write_bytes(b"png")
    runner = FakeRunner()
    runner.add(["flatpak", "search"], SEARCH_OUTPUT)
    runner.add(["flatpak", "list"], "org.kde.filelight\tFilelight\n")
    found = apps.search(runner, "  tux  ", appstream=tmp_path)
    assert runner.calls[0][-1] == "tux"
    assert [(a["id"], a["installed"]) for a in found] == [
        ("org.supertuxproject.SuperTux", False),
        ("org.kde.filelight", True),
    ]
    assert found[1]["icon"] == str(icons / "org.kde.filelight.png") and found[0]["icon"] == ""


def test_search_downloads_the_catalog_when_missing() -> None:
    runner = FakeRunner()
    runner.add(["flatpak", "update"])
    runner.add(["flatpak", "search"], "")
    runner.add(["flatpak", "list"], "")
    assert apps.search(runner, "anything", appstream=MISSING) == []
    assert runner.calls[0][:3] == ("flatpak", "update", "--appstream")
    assert apps.search(FakeRunner(), "   ") == []


def test_search_failure_is_reported(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.add(["flatpak", "search"], returncode=1, stderr="error: no appstream data")
    with pytest.raises(RuntimeError, match="no appstream data"):
        apps.search(runner, "x", appstream=tmp_path)


def test_installed_names_fall_back_to_the_id() -> None:
    runner = FakeRunner()
    runner.add(["flatpak", "list"], "org.mozilla.firefox\tFirefox\norg.kde.kcalc\n\n")
    assert apps.installed_names(runner) == {"org.mozilla.firefox": "Firefox", "org.kde.kcalc": "org.kde.kcalc"}
