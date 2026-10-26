import copy
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tamarack import presets as p
from tamarack.presets import ConfigWrite, LookAndFeelIds, PresetError, parse_preset

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PRESETS = {
    "clean-modern",
    "classic-desktop",
    "minimalist",
    "gaming",
    "creator",
    "productivity",
    "high-contrast",
}


def _raw(name: str = "clean-modern") -> dict[str, Any]:
    with (ROOT / "branding/presets" / f"{name}.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_all_required_presets_exist(presets: list[p.Preset]) -> None:
    assert {x.id for x in presets} == REQUIRED_PRESETS
    assert presets[0].default and presets[0].id == "clean-modern"


def test_presets_change_real_settings_not_just_wallpaper(presets: list[p.Preset]) -> None:
    """Every preset must differ from the default in more than the wallpaper."""
    default = p.default_preset(presets)
    ids = LookAndFeelIds.for_prefix("x")
    base_writes = {(w.file, w.groups, w.key): w.value for w in p.config_writes(default, ids)}
    for preset in presets:
        if preset.default:
            continue
        writes = {(w.file, w.groups, w.key): w.value for w in p.config_writes(preset, ids)}
        changed_settings = {
            k for k in writes if writes[k] != base_writes.get(k) and k[2] not in ("Image", "PreviewImage")
        }
        layout_changed = preset.panel != default.panel or preset.desktop != default.desktop
        assert changed_settings or layout_changed, preset.id


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("appearance", "mode"), "neon", "appearance.mode"),
        (("appearance", "font_size"), 2, "appearance.font_size"),
        (("appearance", "animation_duration"), 0.3, "appearance.animation_duration"),
        (("appearance", "blur"), "yes", "appearance.blur"),
        (("appearance", "titlebar_buttons_right"), "IAXZ", "unknown button codes"),
        (("panel", "location"), "middle", "panel.location"),
        (("panel", "thickness"), True, "got bool"),
        (("panel", "launcher"), "start", "panel.launcher"),
        (("panel", "widgets"), ["tasks", "tray"], r"exactly one .launcher."),
        (("panel", "widgets"), ["launcher", "tasks", "weather"], "unknown entries"),
        (("panel", "pins"), ["firefox"], "must be applications"),
        (("desktop", "virtual_desktop_rows"), 3, "cannot exceed"),
    ],
)
def test_invalid_values_are_rejected(path: tuple[str, str], value: Any, message: str) -> None:
    raw = copy.deepcopy(_raw())
    raw[path[0]][path[1]] = value
    with pytest.raises(PresetError, match=message):
        parse_preset(raw)


def test_missing_tables_and_keys() -> None:
    raw = _raw()
    del raw["panel"]
    with pytest.raises(PresetError, match=r"\[panel\]"):
        parse_preset(raw)
    raw = _raw()
    del raw["appearance"]["wallpaper"]
    with pytest.raises(PresetError, match=r"appearance.wallpaper is required"):
        parse_preset(raw)


def test_load_presets_requires_single_default(tmp_path: Path) -> None:
    for name in ("clean-modern", "gaming"):
        text = (ROOT / "branding/presets" / f"{name}.toml").read_text(encoding="utf-8")
        (tmp_path / f"{name}.toml").write_text(text.replace("default = true", ""), encoding="utf-8")
    with pytest.raises(PresetError, match="exactly one preset"):
        p.load_presets(tmp_path)


def test_file_name_must_match_id(tmp_path: Path) -> None:
    text = (ROOT / "branding/presets/gaming.toml").read_text(encoding="utf-8")
    (tmp_path / "wrong.toml").write_text(text, encoding="utf-8")
    with pytest.raises(PresetError, match="must match id"):
        p.load_preset(tmp_path / "wrong.toml")


def test_default_values_are_deleted_so_kde_defaults_return(presets: list[p.Preset]) -> None:
    writes = p.config_writes(p.default_preset(presets), LookAndFeelIds.for_prefix("x"))
    by_key = {(w.file, w.key): w for w in writes}
    assert by_key[("kdeglobals", "font")].value is None
    assert by_key[("kdeglobals", "AnimationDurationFactor")].value is None
    assert by_key[("kcminputrc", "cursorSize")].value is None
    assert by_key[("kdeglobals", "AutomaticLookAndFeel")].value == "true"


def test_high_contrast_writes_large_text_and_no_animation(presets: list[p.Preset]) -> None:
    hc = next(x for x in presets if x.id == "high-contrast")
    writes = {(w.file, w.key): w.value for w in p.config_writes(hc, LookAndFeelIds.for_prefix("x"))}
    assert writes[("kdeglobals", "font")].startswith("Noto Sans,12,")
    assert writes[("kdeglobals", "AnimationDurationFactor")] == "0"
    assert writes[("kcminputrc", "cursorSize")] == "36"
    assert writes[("kwinrc", "blurEnabled")] == "false"
    assert p.look_and_feel_for(hc, LookAndFeelIds.for_prefix("x")) == "x.highcontrast.desktop"


def test_config_write_argv() -> None:
    write = ConfigWrite("kwinrc", ("Plugins",), "blurEnabled", "false")
    assert write.argv() == [
        "kwriteconfig6",
        "--file",
        "kwinrc",
        "--group",
        "Plugins",
        "--key",
        "blurEnabled",
        "--notify",
        "false",
    ]
    nested = ConfigWrite("kscreenlockerrc", ("Greeter", "Wallpaper"), "Image", None)
    assert nested.argv(notify=False) == [
        "kwriteconfig6",
        "--file",
        "kscreenlockerrc",
        "--group",
        "Greeter",
        "--group",
        "Wallpaper",
        "--key",
        "Image",
        "--delete",
    ]


def test_layout_scripts_are_valid_javascript(presets: list[p.Preset], tmp_path: Path, node: str) -> None:
    for preset in presets:
        script = p.layout_script(preset, "tamarack-logo")
        path = tmp_path / f"{preset.id}.js"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"{preset.id}: {result.stderr}"


def test_layout_script_contents(presets: list[p.Preset]) -> None:
    gaming = next(x for x in presets if x.id == "gaming")
    script = p.layout_script(gaming, "tamarack-logo", pins=["applications:steam.desktop"])
    assert '"replacePanels": true' in script
    assert '"org.kde.plasma.kickoff"' in script
    assert '"applications:steam.desktop"' in script
    assert "net.lutris.Lutris" not in script  # overridden pins are used
    assert "file:///usr/share/wallpapers/Tamarack-Dusk/" in script
    default_layout = p.layout_script(p.default_preset(presets), "tamarack-logo", replace_panels=False)
    assert '"replacePanels": false' in default_layout


def test_look_and_feel_defaults_format() -> None:
    text = p.look_and_feel_defaults("TamarackDark", "breeze-dark", "Tamarack-Ridge")
    assert "[kdeglobals][General]\nColorScheme=TamarackDark" in text
    assert "[Wallpaper]\nImage=Tamarack-Ridge" in text
