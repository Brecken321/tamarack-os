"""Apply, undo, reset, export and import desktop presets for the current user.

Applying a preset:
  1. backs up the user's appearance-related KDE config files,
  2. applies the matching Tamarack global theme (plasma-apply-lookandfeel),
  3. writes the preset's settings with kwriteconfig6,
  4. rebuilds the panel and wallpaper with a Plasma desktop script,
  5. sets virtual desktops and Steam autostart, then asks KWin to reload.

Only appearance/layout files are touched, so "Reset appearance" never resets
unrelated preferences. Every step's outcome is reported; a failed step does
not abort the others, and the backup allows a full undo.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import presets as p
from .brand import Brand
from .system import CommandResult, Runner

log = logging.getLogger("tamarack.appearance")

SYSTEM_PRESETS = Path("/usr/share/tamarack/presets")
# Config files a preset may change. Anything else is left alone.
APPEARANCE_FILES = (
    "kdeglobals",
    "kwinrc",
    "kcminputrc",
    "plasmarc",
    "plasmashellrc",
    "plasma-org.kde.plasma.desktop-appletsrc",
    "kscreenlockerrc",
    "plasmanotifyrc",
    "ksplashrc",
)
MAX_BACKUPS = 10
STEAM_DESKTOP = Path("/usr/share/applications/steam.desktop")
EXPORT_FORMAT = "tamarack-desktop-preset"


@dataclass(frozen=True)
class StepResult:
    step: str
    ok: bool
    detail: str = ""


@dataclass
class ApplyResult:
    preset: str
    backup: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {"preset": self.preset, "backup": self.backup, "ok": self.ok, "steps": [asdict(s) for s in self.steps]}


@dataclass
class Paths:
    home: Path

    @property
    def config(self) -> Path:
        return Path(os.environ.get("XDG_CONFIG_HOME") or self.home / ".config")

    @property
    def data(self) -> Path:
        return Path(os.environ.get("XDG_DATA_HOME") or self.home / ".local/share")

    @property
    def state(self) -> Path:
        return Path(os.environ.get("XDG_STATE_HOME") or self.home / ".local/state") / "tamarack"

    @property
    def backups(self) -> Path:
        return self.state / "appearance-backups"

    @property
    def user_presets(self) -> Path:
        return self.data / "tamarack/presets"

    @property
    def autostart(self) -> Path:
        return self.config / "autostart"


def all_presets(paths: Paths, system_dir: Path = SYSTEM_PRESETS) -> list[p.Preset]:
    """Built-in presets followed by the user's own (imported/custom) presets."""
    found = p.load_presets(system_dir) if system_dir.is_dir() else []
    builtin_ids = {x.id for x in found}
    if paths.user_presets.is_dir():
        for path in sorted(paths.user_presets.glob("*.json")):
            try:
                preset = import_preset_data(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, json.JSONDecodeError) as exc:
                log.warning("ignoring invalid user preset", extra={"path": str(path), "error": str(exc)})
                continue
            if preset.id not in builtin_ids:
                found.append(preset)
    return found


def find_preset(presets: Iterable[p.Preset], preset_id: str) -> p.Preset:
    for preset in presets:
        if preset.id == preset_id:
            return preset
    raise KeyError(f"no preset named {preset_id!r}")


# --- Backups ------------------------------------------------------------------


def backup(paths: Paths, label: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = paths.backups / f"{stamp}-{re.sub(r'[^a-z0-9-]', '', label.lower())[:40]}"
    suffix = 1
    while target.exists():
        target = target.with_name(f"{target.name}-{suffix}")
        suffix += 1
    target.mkdir(parents=True)
    saved = []
    for name in APPEARANCE_FILES:
        src = paths.config / name
        if src.is_file():
            shutil.copy2(src, target / name)
            saved.append(name)
    kdedefaults = paths.config / "kdedefaults"
    if kdedefaults.is_dir():
        shutil.copytree(kdedefaults, target / "kdedefaults")
    autostart = paths.autostart / "steam.desktop"
    (target / "manifest.json").write_text(
        json.dumps({"label": label, "created": stamp, "files": saved, "steam_autostart": autostart.exists()}, indent=2),
        encoding="utf-8",
    )
    _prune_backups(paths)
    return target


def _prune_backups(paths: Paths) -> None:
    backups = list_backups(paths)
    for old in backups[MAX_BACKUPS:]:
        shutil.rmtree(old, ignore_errors=True)


def list_backups(paths: Paths) -> list[Path]:
    if not paths.backups.is_dir():
        return []
    return sorted((d for d in paths.backups.iterdir() if (d / "manifest.json").is_file()), reverse=True)


def restore(paths: Paths, runner: Runner, target: Path | None = None) -> ApplyResult:
    """Restore a backup (default: the newest) and restart the Plasma shell."""
    backups = list_backups(paths)
    if target is None:
        if not backups:
            raise FileNotFoundError("there is no appearance backup to restore")
        target = backups[0]
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    result = ApplyResult(preset=f"undo:{manifest.get('label', '')}", backup=str(target))
    for name in APPEARANCE_FILES:
        dst = paths.config / name
        src = target / name
        if src.is_file():
            shutil.copy2(src, dst)
        elif dst.exists():
            # The file did not exist before the change, so remove the one
            # created since; KDE then falls back to its defaults.
            dst.unlink()
    if (target / "kdedefaults").is_dir():
        shutil.rmtree(paths.config / "kdedefaults", ignore_errors=True)
        shutil.copytree(target / "kdedefaults", paths.config / "kdedefaults")
    set_steam_autostart(paths, bool(manifest.get("steam_autostart")))
    result.steps.append(StepResult("restore files", True, f"restored from {target.name}"))
    result.steps.append(
        _step(
            "restart Plasma shell",
            runner.run(["systemctl", "--user", "restart", "plasma-plasmashell.service"], timeout=60),
        )
    )
    result.steps.append(_reconfigure_kwin(runner))
    return result


# --- Applying -----------------------------------------------------------------


def _step(name: str, res: CommandResult) -> StepResult:
    return StepResult(name, res.ok, "" if res.ok else res.error_summary())


# KDE is reached over the session bus with systemd's busctl, which every
# install has (Qt's qdbus tool is packaged under different names).
KWIN = ("org.kde.KWin", "/KWin", "org.kde.KWin")
VDM = ("org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager")
PLASMASHELL = ("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell")


def _reconfigure_kwin(runner: Runner) -> StepResult:
    return _step("reload window manager", runner.run(["busctl", "--user", "call", *KWIN, "reconfigure"]))


def evaluate_script(runner: Runner, script: str) -> CommandResult:
    """Run a Plasma desktop script in the running plasmashell."""
    return runner.run(["busctl", "--user", "call", *PLASMASHELL, "evaluateScript", "s", script], timeout=60)


def _desktop_file_exists(desktop_id: str, paths: Paths) -> bool:
    dirs = [
        paths.data / "applications",
        paths.data / "flatpak/exports/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]
    return any((d / desktop_id).exists() for d in dirs)


def available_pins(preset: p.Preset, paths: Paths) -> list[str]:
    """Drop pins for apps that are not installed (Plasma would show broken icons)."""
    pins = []
    for pin in preset.panel.pins:
        if pin.startswith("preferred://") or _desktop_file_exists(pin.removeprefix("applications:"), paths):
            pins.append(pin)
    return pins


def set_steam_autostart(paths: Paths, enabled: bool) -> None:
    target = paths.autostart / "steam.desktop"
    if not enabled:
        target.unlink(missing_ok=True)
        return
    # Prefer the user's own Steam launcher (e.g. the discrete-GPU one from gaming.py).
    user_entry = paths.data / "applications" / "steam.desktop"
    source = user_entry if user_entry.exists() else STEAM_DESKTOP
    if not source.exists():
        return
    text = source.read_text(encoding="utf-8")
    # Start minimized to the tray, like Steam's own "run at startup" option.
    text = re.sub(
        r"^Exec=(\S+)(.*)$", lambda m: f"Exec={m.group(1)} -silent{m.group(2)}", text, count=1, flags=re.MULTILINE
    )
    paths.autostart.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _virtual_desktops(runner: Runner, count: int, rows: int) -> StepResult:
    """Use KWin's D-Bus API so changes apply live (config edits alone do not)."""
    current = runner.run(["busctl", "--user", "get-property", *VDM, "count"])
    match = re.fullmatch(r"u (\d+)", current.stdout.strip())
    if not current.ok or not match:
        return StepResult("virtual desktops", False, current.error_summary() or "KWin did not answer")
    have = int(match.group(1))
    while have < count:
        res = runner.run(["busctl", "--user", "call", *VDM, "createDesktop", "us", str(have), f"Desktop {have + 1}"])
        if not res.ok:
            return _step("virtual desktops", res)
        have += 1
    if have > count:
        listing = runner.run(["busctl", "--user", "--json=short", "get-property", *VDM, "desktops"])
        try:
            desktops = json.loads(listing.stdout).get("data", [])
        except (json.JSONDecodeError, AttributeError):
            desktops = []
        # Each entry is (position, id, name); remove the highest positions first.
        for entry in sorted(desktops, key=lambda d: d[0])[count:]:
            res = runner.run(["busctl", "--user", "call", *VDM, "removeDesktop", "s", str(entry[1])])
            if not res.ok:
                return _step("virtual desktops", res)
    rows_res = runner.run(["busctl", "--user", "set-property", *VDM, "rows", "u", str(rows)])
    return StepResult("virtual desktops", rows_res.ok, f"{count} desktop(s), {rows} row(s)")


def apply(preset: p.Preset, brand: Brand, runner: Runner, paths: Paths) -> ApplyResult:
    ids = p.LookAndFeelIds.for_prefix(brand.reverse_dns)
    target = backup(paths, preset.id)
    result = ApplyResult(preset=preset.id, backup=str(target))

    lnf = p.look_and_feel_for(preset, ids)
    args = ["plasma-apply-lookandfeel", "--apply", lnf]
    if preset.appearance.mode == "auto":
        args.append("-k")  # keep automatic light/dark switching on
    result.steps.append(_step(f"apply global theme {lnf}", runner.run(args, timeout=120)))

    failures = [w for w in p.config_writes(preset, ids) if not runner.run(w.argv()).ok]
    result.steps.append(
        StepResult(
            "write settings",
            not failures,
            "" if not failures else "failed: " + ", ".join(f"{w.file}/{w.key}" for w in failures),
        )
    )

    script = p.layout_script(preset, brand.logo_icon, pins=available_pins(preset, paths), replace_panels=True)
    result.steps.append(_step("rebuild panel and wallpaper", evaluate_script(runner, script)))

    result.steps.append(_virtual_desktops(runner, preset.desktop.virtual_desktops, preset.desktop.virtual_desktop_rows))
    try:
        set_steam_autostart(paths, preset.behavior.steam_autostart)
        result.steps.append(StepResult("Steam autostart", True, "on" if preset.behavior.steam_autostart else "off"))
    except OSError as exc:
        result.steps.append(StepResult("Steam autostart", False, str(exc)))
    result.steps.append(_reconfigure_kwin(runner))
    _record_current(paths, preset.id)
    log.info("preset applied", extra={"preset": preset.id, "ok": result.ok})
    return result


def _record_current(paths: Paths, preset_id: str) -> None:
    paths.state.mkdir(parents=True, exist_ok=True)
    (paths.state / "appearance.json").write_text(
        json.dumps({"preset": preset_id, "applied": time.time()}), encoding="utf-8"
    )


def current_preset(paths: Paths) -> str | None:
    try:
        return str(json.loads((paths.state / "appearance.json").read_text(encoding="utf-8"))["preset"])
    except (OSError, ValueError, KeyError):
        return None


# --- Export / import ----------------------------------------------------------


def export_preset_data(preset: p.Preset) -> dict[str, Any]:
    data = asdict(preset)
    data.pop("default", None)
    data["panel"]["widgets"] = list(preset.panel.widgets)
    data["panel"]["pins"] = list(preset.panel.pins)
    return {"format": EXPORT_FORMAT, "version": 1, "preset": data}


def import_preset_data(data: dict[str, Any]) -> p.Preset:
    if data.get("format") != EXPORT_FORMAT or data.get("version") != 1:
        raise ValueError("not a Tamarack desktop preset file (format/version mismatch)")
    raw = dict(data.get("preset") or {})
    raw["default"] = False
    return p.parse_preset(raw)


def save_user_preset(paths: Paths, preset: p.Preset) -> Path:
    paths.user_presets.mkdir(parents=True, exist_ok=True)
    target = paths.user_presets / f"{preset.id}.json"
    target.write_text(json.dumps(export_preset_data(preset), indent=2), encoding="utf-8")
    return target


def delete_user_preset(paths: Paths, preset_id: str) -> None:
    (paths.user_presets / f"{preset_id}.json").unlink(missing_ok=True)
