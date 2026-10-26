import json
from pathlib import Path

import pytest

from tamarack import appearance
from tamarack import presets as p
from tamarack.brand import Brand
from tamarack.system import CommandResult, FakeRunner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    config = tmp_path / ".config"
    config.mkdir()
    (config / "kdeglobals").write_text("[General]\nColorScheme=Mine\n", encoding="utf-8")
    (config / "kwinrc").write_text("[Plugins]\nblurEnabled=true\n", encoding="utf-8")
    (config / "unrelatedrc").write_text("[Keep]\nme=1\n", encoding="utf-8")
    return tmp_path


def _kde_runner() -> FakeRunner:
    runner = FakeRunner()
    for cmd in ("plasma-apply-lookandfeel", "kwriteconfig6", "systemctl"):
        runner.add([cmd])
    runner.add(["qdbus6", "org.kde.plasmashell"])
    runner.add(["qdbus6", "org.kde.KWin", "/KWin"])
    runner.add(["qdbus6", "org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager.count"], "1\n")
    runner.add(["qdbus6", "org.kde.KWin", "/VirtualDesktopManager"])
    return runner


def _preset(presets: list[p.Preset], preset_id: str) -> p.Preset:
    return next(x for x in presets if x.id == preset_id)


def test_apply_runs_every_step_and_backs_up(home: Path, brand: Brand, presets: list[p.Preset]) -> None:
    runner = _kde_runner()
    paths = appearance.Paths(home)
    result = appearance.apply(_preset(presets, "productivity"), brand, runner, paths)
    assert result.ok, result.to_dict()
    calls = [list(c) for c in runner.calls]
    assert ["plasma-apply-lookandfeel", "--apply", f"{brand.reverse_dns}.light.desktop"] in calls
    assert any(c[:1] == ["kwriteconfig6"] and "AnimationDurationFactor" in c for c in calls)
    script_call = next(c for c in calls if c[:2] == ["qdbus6", "org.kde.plasmashell"])
    assert '"org.kde.plasma.taskmanager"' in script_call[-1]  # labels-style task manager
    creates = [c for c in calls if "org.kde.KWin.VirtualDesktopManager.createDesktop" in c]
    assert len(creates) == 3  # 1 -> 4 desktops
    backup = Path(result.backup)
    assert (backup / "kdeglobals").read_text(encoding="utf-8") == "[General]\nColorScheme=Mine\n"
    assert not (backup / "unrelatedrc").exists()  # only appearance files are touched
    assert appearance.current_preset(paths) == "productivity"


def test_auto_mode_keeps_automatic_switching(home: Path, brand: Brand, presets: list[p.Preset]) -> None:
    runner = _kde_runner()
    appearance.apply(p.default_preset(presets), brand, runner, appearance.Paths(home))
    lnf = next(list(c) for c in runner.calls if c[0] == "plasma-apply-lookandfeel")
    assert lnf[-1] == "-k"


def test_failed_step_is_reported_not_hidden(home: Path, brand: Brand, presets: list[p.Preset]) -> None:
    runner = _kde_runner()
    runner.responses[("plasma-apply-lookandfeel",)] = CommandResult(
        ("plasma-apply-lookandfeel",), 1, "", "Could not find package\n"
    )
    result = appearance.apply(_preset(presets, "gaming"), brand, runner, appearance.Paths(home))
    assert not result.ok
    failed = [s for s in result.steps if not s.ok]
    assert failed[0].step.startswith("apply global theme") and "Could not find package" in failed[0].detail
    assert any(s.step == "rebuild panel and wallpaper" and s.ok for s in result.steps)


def test_steam_autostart_follows_preset(
    home: Path, brand: Brand, presets: list[p.Preset], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desktop = tmp_path / "steam.desktop"
    desktop.write_text("[Desktop Entry]\nName=Steam\nExec=/usr/bin/steam %U\n", encoding="utf-8")
    monkeypatch.setattr(appearance, "STEAM_DESKTOP", desktop)
    paths = appearance.Paths(home)
    appearance.apply(_preset(presets, "gaming"), brand, _kde_runner(), paths)
    autostart = paths.autostart / "steam.desktop"
    assert "Exec=/usr/bin/steam -silent %U" in autostart.read_text(encoding="utf-8")
    appearance.apply(_preset(presets, "classic-desktop"), brand, _kde_runner(), paths)
    assert not autostart.exists()


def test_undo_restores_previous_files(home: Path, brand: Brand, presets: list[p.Preset]) -> None:
    paths = appearance.Paths(home)
    appearance.apply(_preset(presets, "gaming"), brand, _kde_runner(), paths)
    # Simulate KDE having written new settings during the apply.
    (paths.config / "kdeglobals").write_text("[General]\nColorScheme=TamarackDark\n", encoding="utf-8")
    (paths.config / "plasmarc").write_text("[Theme]\nname=x\n", encoding="utf-8")
    runner = _kde_runner()
    result = appearance.restore(paths, runner)
    assert result.ok
    assert (paths.config / "kdeglobals").read_text(encoding="utf-8") == "[General]\nColorScheme=Mine\n"
    assert not (paths.config / "plasmarc").exists()  # did not exist before the change
    assert (paths.config / "unrelatedrc").exists()
    assert ["systemctl", "--user", "restart", "plasma-plasmashell.service"] in [list(c) for c in runner.calls]


def test_undo_without_backup(home: Path) -> None:
    with pytest.raises(FileNotFoundError):
        appearance.restore(appearance.Paths(home), FakeRunner())


def test_backups_are_pruned(home: Path) -> None:
    paths = appearance.Paths(home)
    for i in range(appearance.MAX_BACKUPS + 3):
        appearance.backup(paths, f"test{i}")
    assert len(appearance.list_backups(paths)) == appearance.MAX_BACKUPS


def test_export_import_roundtrip(home: Path, presets: list[p.Preset]) -> None:
    paths = appearance.Paths(home)
    original = _preset(presets, "creator")
    data = json.loads(json.dumps(appearance.export_preset_data(original)))
    data["preset"]["id"] = "my-creator"
    data["preset"]["name"] = "My Creator"
    imported = appearance.import_preset_data(data)
    assert imported.panel == original.panel and not imported.default
    appearance.save_user_preset(paths, imported)
    found = appearance.all_presets(paths, ROOT / "branding/presets")
    assert "my-creator" in [x.id for x in found]
    appearance.delete_user_preset(paths, "my-creator")
    assert "my-creator" not in [x.id for x in appearance.all_presets(paths, ROOT / "branding/presets")]


def test_import_rejects_foreign_files() -> None:
    with pytest.raises(ValueError, match="not a Tamarack desktop preset"):
        appearance.import_preset_data({"format": "something-else", "version": 1})
    with pytest.raises(p.PresetError):
        appearance.import_preset_data({"format": appearance.EXPORT_FORMAT, "version": 1, "preset": {"id": "x"}})


def test_invalid_user_preset_files_are_ignored(home: Path) -> None:
    paths = appearance.Paths(home)
    paths.user_presets.mkdir(parents=True)
    (paths.user_presets / "broken.json").write_text("{not json", encoding="utf-8")
    found = appearance.all_presets(paths, ROOT / "branding/presets")
    assert len(found) == 7


def test_pins_for_missing_apps_are_dropped(home: Path, presets: list[p.Preset]) -> None:
    paths = appearance.Paths(home)
    apps = paths.data / "applications"
    apps.mkdir(parents=True)
    (apps / "org.kde.krita.desktop").write_text("[Desktop Entry]\n", encoding="utf-8")
    pins = appearance.available_pins(_preset(presets, "creator"), paths)
    assert "applications:org.kde.krita.desktop" in pins
    assert "preferred://filemanager" in pins
    assert (
        "applications:org.blender.Blender.desktop" not in pins
        or Path("/usr/share/applications/org.blender.Blender.desktop").exists()
    )
