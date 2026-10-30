"""Desktop presets: a validated description of a whole desktop setup.

A preset is a TOML file (see ``branding/presets``) describing appearance,
panel layout and behavior. This module turns a preset into two concrete,
inspectable artifacts:

* a Plasma desktop script (the same API as look-and-feel layout scripts),
  used both as the default layout baked into the image and at runtime via
  ``org.kde.PlasmaShell.evaluateScript``;
* a list of :class:`ConfigWrite` operations for ``kwriteconfig6``.

Nothing here touches the system; :mod:`tamarack.appearance` executes plans.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .system import kwriteconfig_argv

MODES = ("light", "dark", "auto", "high-contrast")
LOCATIONS = ("top", "bottom", "left", "right")
LENGTH_MODES = ("fill", "fit")
ALIGNMENTS = ("left", "center", "right")
HIDING = ("none", "autohide", "dodgewindows", "windowsgobelow")
OPACITY = ("adaptive", "opaque", "translucent")
LAUNCHERS = {
    "kickoff": "org.kde.plasma.kickoff",
    "kicker": "org.kde.plasma.kicker",
    "kickerdash": "org.kde.plasma.kickerdash",
}
TASK_MANAGERS = {
    "icontasks": "org.kde.plasma.icontasks",
    "tasks": "org.kde.plasma.taskmanager",
}
# Widget aliases usable in a preset's ``panel.widgets`` list.
WIDGETS = {
    "tray": "org.kde.plasma.systemtray",
    "clock": "org.kde.plasma.digitalclock",
    "showdesktop": "org.kde.plasma.showdesktop",
    "pager": "org.kde.plasma.pager",
    "spacer": "org.kde.plasma.panelspacer",
    "separator": "org.kde.plasma.marginsseparator",
}
# KDE's "Animation speed" slider only offers these duration factors.
ANIMATION_FACTORS = (0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
# Plasma defaults; keys equal to these are deleted rather than written so that
# switching back to a default-valued preset really restores KDE's defaults.
DEFAULT_FONT_SIZE = 10
DEFAULT_CURSOR_SIZE = 24
DEFAULT_ANIMATION = 1.0
FONT_FAMILY = "Noto Sans"
FIXED_FONT_FAMILY = "Noto Sans Mono"


class PresetError(ValueError):
    """Raised when a preset file is invalid. The message names the bad key."""


@dataclass(frozen=True)
class Appearance:
    mode: str
    wallpaper: str
    font_size: int
    cursor_size: int
    animation_duration: float
    blur: bool
    titlebar_buttons_left: str
    titlebar_buttons_right: str


@dataclass(frozen=True)
class Panel:
    location: str
    thickness: int
    floating: bool
    length_mode: str
    alignment: str
    hiding: str
    opacity: str
    launcher: str
    task_manager: str
    widgets: tuple[str, ...]
    pins: tuple[str, ...]


@dataclass(frozen=True)
class Desktop:
    virtual_desktops: int
    virtual_desktop_rows: int


@dataclass(frozen=True)
class Behavior:
    quick_tiling: bool
    dnd_when_fullscreen: bool
    steam_autostart: bool


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    summary: str
    appearance: Appearance
    panel: Panel
    desktop: Desktop
    behavior: Behavior
    default: bool = False


@dataclass(frozen=True)
class ConfigWrite:
    """One ``kwriteconfig6`` operation. ``value`` None means delete the key."""

    file: str
    groups: tuple[str, ...]
    key: str
    value: str | None

    def argv(self, notify: bool = True) -> list[str]:
        return kwriteconfig_argv(self.file, self.groups, self.key, self.value, notify)


@dataclass(frozen=True)
class LookAndFeelIds:
    """Global theme (look-and-feel package) ids for each appearance mode."""

    light: str
    dark: str
    high_contrast: str

    @classmethod
    def for_prefix(cls, reverse_dns: str) -> LookAndFeelIds:
        return cls(
            light=f"{reverse_dns}.light.desktop",
            dark=f"{reverse_dns}.dark.desktop",
            high_contrast=f"{reverse_dns}.highcontrast.desktop",
        )


@dataclass(frozen=True)
class _Field:
    kind: type | tuple[type, ...]
    choices: tuple[Any, ...] = field(default_factory=tuple)
    minimum: float | None = None
    maximum: float | None = None


def _get(table: Mapping[str, Any], key: str, spec: _Field, where: str) -> Any:
    if key not in table:
        raise PresetError(f"{where}.{key} is required")
    value: Any = table[key]
    # bool is a subclass of int; never accept it where a number is expected.
    if isinstance(value, bool) and spec.kind is not bool:
        raise PresetError(f"{where}.{key} must be {spec.kind}, got bool")
    if not isinstance(value, spec.kind):
        raise PresetError(f"{where}.{key} must be {spec.kind}, got {type(value).__name__}")
    if spec.choices and value not in spec.choices:
        raise PresetError(f"{where}.{key} must be one of {list(spec.choices)}, got {value!r}")
    number = float(value) if isinstance(value, (int, float)) else 0.0
    if spec.minimum is not None and number < spec.minimum:
        raise PresetError(f"{where}.{key} must be >= {spec.minimum}")
    if spec.maximum is not None and number > spec.maximum:
        raise PresetError(f"{where}.{key} must be <= {spec.maximum}")
    return value


def _table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise PresetError(f"[{key}] table is required")
    return value


def _str_list(table: Mapping[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PresetError(f"{where}.{key} must be a list of strings")
    return tuple(value)


_TITLEBAR_BUTTONS = set("MSHIAXFBNL")


def parse_preset(data: Mapping[str, Any]) -> Preset:
    """Validate a decoded preset document and build a :class:`Preset`."""
    preset_id = _get(data, "id", _Field(str), "preset")
    if not preset_id or not all(c.isalnum() or c == "-" for c in preset_id):
        raise PresetError("preset.id may only contain letters, digits and '-'")
    a = _table(data, "appearance")
    appearance = Appearance(
        mode=_get(a, "mode", _Field(str, MODES), "appearance"),
        wallpaper=_get(a, "wallpaper", _Field(str), "appearance"),
        font_size=_get(a, "font_size", _Field(int, minimum=6, maximum=32), "appearance"),
        cursor_size=_get(a, "cursor_size", _Field(int, (24, 30, 36, 48, 60, 72)), "appearance"),
        animation_duration=float(_get(a, "animation_duration", _Field((int, float), ANIMATION_FACTORS), "appearance")),
        blur=_get(a, "blur", _Field(bool), "appearance"),
        titlebar_buttons_left=_get(a, "titlebar_buttons_left", _Field(str), "appearance"),
        titlebar_buttons_right=_get(a, "titlebar_buttons_right", _Field(str), "appearance"),
    )
    for side in ("titlebar_buttons_left", "titlebar_buttons_right"):
        bad = set(getattr(appearance, side)) - _TITLEBAR_BUTTONS
        if bad:
            raise PresetError(f"appearance.{side} has unknown button codes {sorted(bad)}")

    p = _table(data, "panel")
    widgets = _str_list(p, "widgets", "panel")
    known_widgets = {"launcher", "tasks", *WIDGETS}
    unknown = [w for w in widgets if w not in known_widgets]
    if unknown:
        raise PresetError(f"panel.widgets has unknown entries {unknown}")
    if widgets.count("launcher") != 1 or widgets.count("tasks") != 1:
        raise PresetError("panel.widgets must contain exactly one 'launcher' and one 'tasks'")
    panel = Panel(
        location=_get(p, "location", _Field(str, LOCATIONS), "panel"),
        thickness=_get(p, "thickness", _Field(int, minimum=24, maximum=128), "panel"),
        floating=_get(p, "floating", _Field(bool), "panel"),
        length_mode=_get(p, "length_mode", _Field(str, LENGTH_MODES), "panel"),
        alignment=_get(p, "alignment", _Field(str, ALIGNMENTS), "panel"),
        hiding=_get(p, "hiding", _Field(str, HIDING), "panel"),
        opacity=_get(p, "opacity", _Field(str, OPACITY), "panel"),
        launcher=_get(p, "launcher", _Field(str, tuple(LAUNCHERS)), "panel"),
        task_manager=_get(p, "task_manager", _Field(str, tuple(TASK_MANAGERS)), "panel"),
        widgets=widgets,
        pins=_str_list(p, "pins", "panel"),
    )
    for pin in panel.pins:
        if not (pin.startswith("applications:") and pin.endswith(".desktop")) and not pin.startswith("preferred://"):
            raise PresetError(f"panel.pins entry {pin!r} must be applications:<id>.desktop or preferred://")

    d = _table(data, "desktop")
    desktop = Desktop(
        virtual_desktops=_get(d, "virtual_desktops", _Field(int, minimum=1, maximum=20), "desktop"),
        virtual_desktop_rows=_get(d, "virtual_desktop_rows", _Field(int, minimum=1, maximum=4), "desktop"),
    )
    if desktop.virtual_desktop_rows > desktop.virtual_desktops:
        raise PresetError("desktop.virtual_desktop_rows cannot exceed desktop.virtual_desktops")

    b = _table(data, "behavior")
    behavior = Behavior(
        quick_tiling=_get(b, "quick_tiling", _Field(bool), "behavior"),
        dnd_when_fullscreen=_get(b, "dnd_when_fullscreen", _Field(bool), "behavior"),
        steam_autostart=_get(b, "steam_autostart", _Field(bool), "behavior"),
    )
    default = data.get("default", False)
    if not isinstance(default, bool):
        raise PresetError("preset.default must be a boolean")
    return Preset(
        id=preset_id,
        name=_get(data, "name", _Field(str), "preset"),
        summary=_get(data, "summary", _Field(str), "preset"),
        appearance=appearance,
        panel=panel,
        desktop=desktop,
        behavior=behavior,
        default=default,
    )


def load_preset(path: Path) -> Preset:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise PresetError(f"{path.name}: invalid TOML: {exc}") from exc
    try:
        preset = parse_preset(data)
    except PresetError as exc:
        raise PresetError(f"{path.name}: {exc}") from exc
    if path.stem != preset.id:
        raise PresetError(f"{path.name}: file name must match id {preset.id!r}")
    return preset


def load_presets(directory: Path) -> list[Preset]:
    """Load every ``*.toml`` preset, enforcing unique ids and one default."""
    presets = [load_preset(p) for p in sorted(directory.glob("*.toml"))]
    if not presets:
        raise PresetError(f"no presets found in {directory}")
    ids = [p.id for p in presets]
    if len(set(ids)) != len(ids):
        raise PresetError("duplicate preset ids")
    defaults = [p.id for p in presets if p.default]
    if len(defaults) != 1:
        raise PresetError(f"exactly one preset must set default = true, found {defaults}")
    # Keep the default first so menus list it first.
    presets.sort(key=lambda p: (not p.default, p.name))
    return presets


def default_preset(presets: Iterable[Preset]) -> Preset:
    for preset in presets:
        if preset.default:
            return preset
    raise PresetError("no default preset")


def look_and_feel_for(preset: Preset, ids: LookAndFeelIds) -> str:
    """The global theme to apply now for the preset's mode ("auto" starts light)."""
    if preset.appearance.mode == "dark":
        return ids.dark
    if preset.appearance.mode == "high-contrast":
        return ids.high_contrast
    return ids.light


def wallpaper_url(name: str) -> str:
    """Plasma accepts a wallpaper *package* directory as the image source."""
    return f"file:///usr/share/wallpapers/{name}/"


def _font(size: int, family: str = FONT_FAMILY, weight: int = 400) -> str:
    # Qt 6 QFont::toString() layout, as written by KDE's font KCM.
    return f"{family},{size},-1,5,{weight},0,0,0,0,0,0,0,0,0,0,1"


def config_writes(preset: Preset, ids: LookAndFeelIds) -> list[ConfigWrite]:
    """Every kconfig change a preset makes besides the global theme and layout."""
    a, b = preset.appearance, preset.behavior
    w: list[ConfigWrite] = []
    automatic = a.mode == "auto"
    w.append(ConfigWrite("kdeglobals", ("KDE",), "AutomaticLookAndFeel", "true" if automatic else "false"))
    w.append(ConfigWrite("kdeglobals", ("KDE",), "DefaultLightLookAndFeel", ids.light))
    w.append(ConfigWrite("kdeglobals", ("KDE",), "DefaultDarkLookAndFeel", ids.dark))

    if a.animation_duration == DEFAULT_ANIMATION:
        w.append(ConfigWrite("kdeglobals", ("KDE",), "AnimationDurationFactor", None))
    else:
        w.append(ConfigWrite("kdeglobals", ("KDE",), "AnimationDurationFactor", f"{a.animation_duration:g}"))

    if a.font_size == DEFAULT_FONT_SIZE:
        fonts: dict[tuple[str, str], str | None] = {
            ("General", "font"): None,
            ("General", "menuFont"): None,
            ("General", "toolBarFont"): None,
            ("General", "smallestReadableFont"): None,
            ("General", "fixed"): None,
            ("WM", "activeFont"): None,
        }
    else:
        fonts = {
            ("General", "font"): _font(a.font_size),
            ("General", "menuFont"): _font(a.font_size),
            ("General", "toolBarFont"): _font(a.font_size),
            ("General", "smallestReadableFont"): _font(max(a.font_size - 2, 6)),
            ("General", "fixed"): _font(a.font_size, FIXED_FONT_FAMILY),
            ("WM", "activeFont"): _font(a.font_size, weight=700),
        }
    for (group, key), value in fonts.items():
        w.append(ConfigWrite("kdeglobals", (group,), key, value))

    w.append(
        ConfigWrite(
            "kcminputrc",
            ("Mouse",),
            "cursorSize",
            None if a.cursor_size == DEFAULT_CURSOR_SIZE else str(a.cursor_size),
        )
    )
    w.append(ConfigWrite("kwinrc", ("Plugins",), "blurEnabled", "true" if a.blur else "false"))
    w.append(ConfigWrite("kwinrc", ("org.kde.kdecoration2",), "ButtonsOnLeft", a.titlebar_buttons_left))
    w.append(ConfigWrite("kwinrc", ("org.kde.kdecoration2",), "ButtonsOnRight", a.titlebar_buttons_right))
    tiling = "true" if b.quick_tiling else "false"
    w.append(ConfigWrite("kwinrc", ("Windows",), "ElectricBorderTiling", tiling))
    w.append(ConfigWrite("kwinrc", ("Windows",), "ElectricBorderMaximize", tiling))
    w.append(
        ConfigWrite(
            "plasmanotifyrc",
            ("DoNotDisturb",),
            "WhenFullscreen",
            "true" if b.dnd_when_fullscreen else "false",
        )
    )
    image = wallpaper_url(a.wallpaper)
    w.append(ConfigWrite("kscreenlockerrc", ("Greeter", "Wallpaper", "org.kde.image", "General"), "Image", image))
    w.append(
        ConfigWrite("kscreenlockerrc", ("Greeter", "Wallpaper", "org.kde.image", "General"), "PreviewImage", image)
    )
    return w


def _widget_specs(panel: Panel, pins: Iterable[str], launcher_icon: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for alias in panel.widgets:
        if alias == "launcher":
            specs.append(
                {
                    "plugin": LAUNCHERS[panel.launcher],
                    "config": [{"group": ["General"], "key": "icon", "value": launcher_icon}],
                }
            )
        elif alias == "tasks":
            specs.append(
                {
                    "plugin": TASK_MANAGERS[panel.task_manager],
                    "config": [{"group": ["General"], "key": "launchers", "value": list(pins)}],
                }
            )
        else:
            specs.append({"plugin": WIDGETS[alias], "config": []})
    return specs


_LAYOUT_TEMPLATE = """\
// Generated by Tamarack OS from preset "{preset_id}". Do not edit by hand;
// change branding/presets/{preset_id}.toml instead.
(function () {{
    var spec = {spec};

    if (spec.replacePanels) {{
        var existing = panels();
        for (var i = 0; i < existing.length; ++i) {{
            existing[i].remove();
        }}
    }}

    var panel = new Panel;
    panel.location = spec.panel.location;
    panel.height = spec.panel.thickness;
    panel.floating = spec.panel.floating;
    panel.lengthMode = spec.panel.lengthMode;
    panel.alignment = spec.panel.alignment;
    panel.hiding = spec.panel.hiding;
    panel.opacity = spec.panel.opacity;

    // Like Plasma's default panel: keep a horizontal full-width panel from
    // stretching across ultrawide monitors wider than 21:9.
    if (spec.panel.lengthMode === "fill" && panel.formFactor === "horizontal") {{
        var geo = screenGeometry(panel.screen);
        var maximumWidth = Math.ceil(geo.height * 21 / 9);
        if (geo.width > maximumWidth) {{
            panel.alignment = "center";
            panel.minimumLength = maximumWidth;
            panel.maximumLength = maximumWidth;
        }}
    }}

    // Input-method widget for languages that usually need one (from Plasma's
    // default panel template).
    var imeLanguages = ["as", "bn", "bo", "brx", "doi", "gu", "hi", "ja", "kn", "ko", "kok",
        "ks", "lep", "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "si",
        "ta", "te", "th", "ur", "vi", "zh_CN", "zh_TW"];
    var wantsIme = typeof languageId !== "undefined" && imeLanguages.indexOf(languageId) !== -1;

    for (var w = 0; w < spec.panel.widgets.length; ++w) {{
        var item = spec.panel.widgets[w];
        if (wantsIme && item.plugin === "org.kde.plasma.systemtray") {{
            panel.addWidget("org.kde.plasma.kimpanel");
        }}
        var widget = panel.addWidget(item.plugin);
        for (var c = 0; c < item.config.length; ++c) {{
            widget.currentConfigGroup = item.config[c].group;
            widget.writeConfig(item.config[c].key, item.config[c].value);
        }}
    }}

    var allDesktops = desktops();
    for (var d = 0; d < allDesktops.length; ++d) {{
        allDesktops[d].wallpaperPlugin = "org.kde.image";
        allDesktops[d].currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
        allDesktops[d].writeConfig("Image", spec.wallpaper);
        allDesktops[d].writeConfig("PreviewImage", spec.wallpaper);
    }}
}})();
"""


def layout_script(
    preset: Preset,
    launcher_icon: str,
    pins: Iterable[str] | None = None,
    replace_panels: bool = True,
) -> str:
    """Plasma desktop script that builds the preset's panel and wallpaper.

    ``pins`` overrides the preset's launchers (the runtime filters out apps
    that are not installed). ``replace_panels`` removes existing panels
    first; the image's default layout script runs on an empty desktop and
    passes False.
    """
    panel = preset.panel
    spec = {
        "replacePanels": replace_panels,
        "panel": {
            "location": panel.location,
            "thickness": panel.thickness,
            "floating": panel.floating,
            "lengthMode": panel.length_mode,
            "alignment": panel.alignment,
            "hiding": panel.hiding,
            "opacity": panel.opacity,
            "widgets": _widget_specs(panel, panel.pins if pins is None else pins, launcher_icon),
        },
        "wallpaper": wallpaper_url(preset.appearance.wallpaper),
    }
    return _LAYOUT_TEMPLATE.format(preset_id=preset.id, spec=json.dumps(spec, indent=4))


def look_and_feel_defaults(
    color_scheme: str,
    icons: str,
    wallpaper: str,
    plasma_theme: str = "default",
    cursor: str = "breeze_cursors",
) -> str:
    """The ``contents/defaults`` file of a look-and-feel package."""
    return (
        "[kdeglobals][KDE]\n"
        "widgetStyle=Breeze\n\n"
        "[kdeglobals][General]\n"
        f"ColorScheme={color_scheme}\n\n"
        "[kdeglobals][Icons]\n"
        f"Theme={icons}\n\n"
        "[plasmarc][Theme]\n"
        f"name={plasma_theme}\n\n"
        "[Wallpaper]\n"
        f"Image={wallpaper}\n\n"
        "[kcminputrc][Mouse]\n"
        f"cursorTheme={cursor}\n\n"
        "[kwinrc][org.kde.kdecoration2]\n"
        "library=org.kde.breeze\n"
        "theme=Breeze\n\n"
        "[ksplashrc][KSplash]\n"
        "Theme=org.kde.breeze.desktop\n"
    )
