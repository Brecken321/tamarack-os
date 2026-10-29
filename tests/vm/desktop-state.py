#!/usr/bin/python3 -I
"""Check that the running desktop matches a Tamarack preset (a "look").

Runs inside the VM's desktop session (see run-vm-test.sh):

  desktop-state.py PRESET_ID

Asks Plasma and KWin what they are actually using (panels and their widgets,
the wallpaper, virtual desktops, the blur effect), reads the settings files
KDE reads, and compares each with the preset. Prints PASS, FAIL and INFO
lines; exits non-zero if something does not match.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, "/usr/lib/tamarack/python")

from tamarack import appearance
from tamarack import presets as p
from tamarack.brand import load_runtime_brand

failures = 0
SCRIPT = """
var out = [];
var all = panels();
for (var i = 0; i < all.length; ++i) {
    var panel = all[i];
    var widgets = panel.widgets();
    var types = [];
    for (var j = 0; j < widgets.length; ++j) types.push(widgets[j].type);
    out.push({location: panel.location, height: panel.height, floating: panel.floating,
              lengthMode: panel.lengthMode, alignment: panel.alignment, hiding: panel.hiding,
              opacity: panel.opacity, widgets: types});
}
var desktop = desktops()[0];
desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
print(JSON.stringify({panels: out, wallpaper: desktop.readConfig("Image"), plugin: desktop.wallpaperPlugin}));
"""


def check(ok: bool, text: str) -> None:
    global failures
    if not ok:
        failures += 1
    print(("PASS: " if ok else "FAIL: ") + text, flush=True)


def run(*argv: str) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=60).stdout.strip()


def busctl(*args: str) -> Any:
    """A session bus call's reply data (busctl --json=short)."""
    out = run("busctl", "--user", "--json=short", *args)
    return json.loads(out)["data"] if out else None


def kread(file: str, groups: tuple[str, ...], key: str) -> str:
    args = ["kreadconfig6", "--file", file]
    for group in groups:
        args += ["--group", group]
    return run(*args, "--key", key)


def user_value(file: str, groups: tuple[str, ...], key: str) -> str | None:
    """KEY in the user's own settings file (not KDE's defaults); None if absent."""
    try:
        lines = (Path.home() / ".config" / file).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    header = "".join(f"[{g}]" for g in groups)
    inside = False
    for line in lines:
        if line.startswith("["):
            inside = line.strip() == header
        elif inside and line.partition("=")[0].strip() == key:
            return line.partition("=")[2]
    return None


def main() -> int:
    preset_id = sys.argv[1]
    brand = load_runtime_brand()
    paths = appearance.Paths(Path.home())
    preset = appearance.find_preset(appearance.all_presets(paths), preset_id)
    ids = p.LookAndFeelIds.for_prefix(brand.reverse_dns)
    print(f"== the desktop now, compared with {preset.name} ({preset.id})", flush=True)

    shell = json.loads(
        busctl("call", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript", "s", SCRIPT)[0]
    )
    panels = shell["panels"]
    check(len(panels) == 1, f"one panel ({len(panels)})")
    want = preset.panel
    expected = {
        "location": want.location,
        "height": want.thickness,
        "floating": want.floating,
        "lengthMode": want.length_mode,
        "alignment": want.alignment,
        "hiding": want.hiding,
        "opacity": want.opacity,
    }
    if panels:
        have = panels[0]
        for key, value in expected.items():
            check(have.get(key) == value, f"panel {key}: {value} (Plasma: {have.get(key)})")
        widgets = [s["plugin"] for s in p._widget_specs(want, [], brand.logo_icon)]
        check(have["widgets"] == widgets, f"panel widgets: {', '.join(widgets)} (Plasma: {', '.join(have['widgets'])})")
    wallpaper = p.wallpaper_url(preset.appearance.wallpaper)
    check(shell["wallpaper"] == wallpaper, f"wallpaper {wallpaper} (Plasma: {shell['wallpaper']})")

    theme = p.look_and_feel_for(preset, ids)
    current = kread("kdeglobals", ("KDE",), "LookAndFeelPackage")
    check(current == theme, f"global theme {theme} ({current})")
    print(f"INFO: color scheme {kread('kdeglobals', ('General',), 'ColorScheme')}", flush=True)
    wrong = []
    writes = p.config_writes(preset, ids)
    for w in writes:
        value = user_value(w.file, w.groups, w.key)
        # KDE does not store a value equal to a system default in your file:
        # then the value in effect is the default (read like Plasma does).
        if value is None and w.value is not None:
            value = kread(w.file, w.groups, w.key)
        if value != w.value:
            wrong.append(f"{w.file} {'/'.join(w.groups)} {w.key}={value!r}, not {w.value!r}")
    detail = ": " + "; ".join(wrong) if wrong else ""
    check(not wrong, f"settings in effect: the preset's {len(writes)} values (None = KDE's default){detail}")

    vdm = ("org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager")
    count = busctl("get-property", *vdm, "count")
    rows = busctl("get-property", *vdm, "rows")
    desk = preset.desktop
    check(count == desk.virtual_desktops, f"virtual desktops: {desk.virtual_desktops} (KWin: {count})")
    check(rows == desk.virtual_desktop_rows, f"virtual desktop rows: {desk.virtual_desktop_rows} (KWin: {rows})")
    effects = ("org.kde.KWin", "/Effects", "org.kde.kwin.Effects")
    if busctl("call", *effects, "isEffectSupported", "s", "blur") == [True]:
        for _ in range(10):  # KWin loads effects in the background
            loaded = busctl("call", *effects, "isEffectLoaded", "s", "blur") == [True]
            if loaded == preset.appearance.blur:
                break
            time.sleep(2)
        check(
            loaded == preset.appearance.blur,
            f"blur effect {'on' if preset.appearance.blur else 'off'} (KWin: {loaded})",
        )
    else:
        print("INFO: KWin cannot blur on this graphics (no GPU); the setting is checked in kwinrc only", flush=True)
    autostart = (paths.autostart / "steam.desktop").exists()
    steam = preset.behavior.steam_autostart
    check(
        autostart == steam,
        f"Steam starts with the desktop: {'yes' if steam else 'no'} ({'yes' if autostart else 'no'})",
    )
    check(appearance.current_preset(paths) == preset.id, f"Tamarack Center shows {preset.name} as the current look")
    print(f"{failures} failure(s)", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
