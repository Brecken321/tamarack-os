"""QObject bridge between the QML UI and the tamarack modules.

Slow work (probing hardware, running flatpak/pkexec, reading Steam data)
runs on a thread pool; results come back to the GUI thread through a queued
signal, so the interface never blocks. Every failure is reported to the UI
as a message instead of being swallowed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import re
import subprocess
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QRunnable, Qt, QThreadPool, QUrl, Signal, Slot

from .. import appearance, apps, art, doctor, games, gaming, hardware, privacy, steam, updates
from .. import presets as preset_lib
from ..brand import Brand
from ..system import CommandResult, Runner

log = logging.getLogger("tamarack.ui")

Callback = Callable[[Any], None]


class _Task(QRunnable):
    def __init__(self, task_id: int, func: Callable[[], Any], done: Signal) -> None:
        super().__init__()
        self.task_id = task_id
        self.func = func
        self.done = done

    def run(self) -> None:
        try:
            result: Any = ("ok", self.func())
        except Exception as exc:  # reported to the UI by _on_task_done
            log.exception("background task failed")
            result = ("error", f"{type(exc).__name__}: {exc}", traceback.format_exc())
        self.done.emit(self.task_id, result)


def _preset_dict(p: preset_lib.Preset, current: str | None, preview: str, builtin: bool) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "summary": p.summary,
        "preview": preview,
        "builtin": builtin,
        "current": p.id == current,
        "isDefault": p.default,
        "mode": p.appearance.mode,
        "wallpaper": p.appearance.wallpaper,
        "fontSize": p.appearance.font_size,
        "cursorSize": p.appearance.cursor_size,
        "animation": p.appearance.animation_duration,
        "blur": p.appearance.blur,
        "location": p.panel.location,
        "thickness": p.panel.thickness,
        "floating": p.panel.floating,
        "lengthMode": p.panel.length_mode,
        "alignment": p.panel.alignment,
        "hiding": p.panel.hiding,
        "launcher": p.panel.launcher,
        "taskManager": p.panel.task_manager,
        "virtualDesktops": p.desktop.virtual_desktops,
        "steamAutostart": p.behavior.steam_autostart,
    }


class Backend(QObject):
    _taskDone = Signal(int, object)

    notify = Signal(str, str, arguments=["message", "kind"])
    busyChanged = Signal()
    doctorChanged = Signal()
    presetsChanged = Signal()
    hardwareChanged = Signal()
    privacyChanged = Signal()
    libraryChanged = Signal()
    gameResultsChanged = Signal()
    bundlesChanged = Signal()
    updatesChanged = Signal()
    welcomeFinished = Signal()
    gpuChanged = Signal()

    def __init__(
        self, brand: Brand, runner: Runner, welcome: bool = False, home: Path | None = None, dry_run: bool = False
    ) -> None:
        super().__init__()
        self._brand = brand
        self._runner = runner
        self._welcome = welcome
        # dry_run: never start background work (used by --self-test).
        self._dry_run = dry_run
        self._home = home or Path.home()
        self._paths = appearance.Paths(self._home)
        self._pool = QThreadPool.globalInstance()
        self._ids = itertools.count(1)
        self._callbacks: dict[int, tuple[Callback, str]] = {}
        self._busy: dict[int, str] = {}
        self._taskDone.connect(self._on_task_done, Qt.ConnectionType.QueuedConnection)
        self._doctor: dict[str, Any] = {}
        self._presets: list[dict[str, Any]] = []
        self._hardware: dict[str, Any] = {}
        self._privacy: dict[str, Any] = {}
        self._library: dict[str, Any] = {}
        self._game_results: list[dict[str, Any]] = []
        self._bundles: list[dict[str, Any]] = []
        self._updates: dict[str, Any] = {}
        self._db: games.AntiCheatDatabase | None = None
        self._cache = self._home / ".cache/tamarack"

    # -- task plumbing -----------------------------------------------------
    def _run(self, label: str, func: Callable[[], Any], on_done: Callback) -> None:
        if self._dry_run:
            return
        task_id = next(self._ids)
        self._callbacks[task_id] = (on_done, label)
        self._busy[task_id] = label
        self.busyChanged.emit()
        self._pool.start(_Task(task_id, func, self._taskDone))

    @Slot(int, object)
    def _on_task_done(self, task_id: int, result: Any) -> None:
        callback, label = self._callbacks.pop(task_id)
        self._busy.pop(task_id, None)
        self.busyChanged.emit()
        if result[0] == "error":
            self.notify.emit(f"{label} failed: {result[1]}", "error")
            return
        try:
            callback(result[1])
        except Exception as exc:
            log.exception("UI callback failed")
            self.notify.emit(f"{label}: {exc}", "error")

    def _report(self, label: str, res: CommandResult, success: str) -> None:
        if res.ok:
            self.notify.emit(success, "positive")
        elif res.returncode in (126, 127) and res.argv and res.argv[0] == "pkexec":
            self.notify.emit(f"{label}: authorization was cancelled or denied.", "warning")
        else:
            self.notify.emit(f"{label} failed: {res.error_summary()}", "error")

    # -- simple properties -----------------------------------------------------
    @Property("QVariant", constant=True)
    def brand(self) -> dict[str, Any]:
        b = self._brand
        return {
            "name": b.name,
            "shortName": b.short_name,
            "tagline": b.tagline,
            "basedOn": b.based_on,
            "homeUrl": b.home_url,
            "docsUrl": b.documentation_url,
            "supportUrl": b.support_url,
            "bugUrl": b.bug_report_url,
            "logo": b.logo_icon,
            "accent": b.palette["accent"],
            "amber": b.palette["amber"],
        }

    @Property(bool, constant=True)
    def welcomeMode(self) -> bool:
        return self._welcome

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return bool(self._busy)

    @Property(str, notify=busyChanged)
    def busyText(self) -> str:
        return next(iter(self._busy.values()), "")

    # -- doctor / home ---------------------------------------------------------
    @Property("QVariant", notify=doctorChanged)
    def doctor(self) -> dict[str, Any]:
        return self._doctor

    @Slot()
    def refreshDoctor(self) -> None:
        self._run("Checking your system", lambda: doctor.report(self._runner), self._set_doctor)

    def _set_doctor(self, data: dict[str, Any]) -> None:
        self._doctor = data
        self.doctorChanged.emit()

    # -- presets / appearance ----------------------------------------------------
    @Property("QVariant", notify=presetsChanged)
    def presets(self) -> list[dict[str, Any]]:
        return self._presets

    @Property("QVariant", notify=presetsChanged)
    def backups(self) -> list[dict[str, str]]:
        out = []
        for path in appearance.list_backups(self._paths):
            try:
                manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append(
                {
                    "name": path.name,
                    "label": str(manifest.get("label", "")),
                    "created": str(manifest.get("created", "")),
                }
            )
        return out

    @Slot()
    def refreshPresets(self) -> None:
        try:
            found = appearance.all_presets(self._paths)
        except preset_lib.PresetError as exc:
            self.notify.emit(f"Could not load presets: {exc}", "error")
            return
        current = appearance.current_preset(self._paths)
        builtin_dir = appearance.SYSTEM_PRESETS / "previews"
        result = []
        for p in found:
            png = builtin_dir / f"{p.id}.png"
            builtin = png.exists()
            preview = QUrl.fromLocalFile(str(png)).toString() if builtin else self._preview_file(p)
            result.append(_preset_dict(p, current, preview, builtin))
        self._presets = result
        self.presetsChanged.emit()

    def _preview_file(self, preset: preset_lib.Preset) -> str:
        svg = art.preview_svg(self._brand, preset)
        digest = hashlib.sha256(svg.encode()).hexdigest()[:16]
        target = self._cache / f"preview-{digest}.svg"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(svg, encoding="utf-8")
        return QUrl.fromLocalFile(str(target)).toString()

    def _find(self, preset_id: str) -> preset_lib.Preset:
        return appearance.find_preset(appearance.all_presets(self._paths), preset_id)

    @Slot(str)
    def applyPreset(self, preset_id: str) -> None:
        try:
            preset = self._find(preset_id)
        except (KeyError, preset_lib.PresetError) as exc:
            self.notify.emit(str(exc), "error")
            return
        self._run(
            f"Applying {preset.name}",
            lambda: appearance.apply(preset, self._brand, self._runner, self._paths),
            self._applied,
        )

    def _applied(self, result: appearance.ApplyResult) -> None:
        self.refreshPresets()
        if result.ok:
            self.notify.emit("Done. Use “Undo last change” if you want the previous look back.", "positive")
        else:
            failed = "; ".join(f"{s.step}: {s.detail}" for s in result.steps if not s.ok)
            self.notify.emit(f"Applied with problems: {failed}", "warning")

    @Slot()
    def undoAppearance(self) -> None:
        self._run("Restoring your previous look", lambda: appearance.restore(self._paths, self._runner), self._applied)

    @Slot()
    def resetAppearance(self) -> None:
        default = preset_lib.default_preset(appearance.all_presets(self._paths))
        self.applyPreset(default.id)

    def _preset_from_form(self, form: dict[str, Any]) -> preset_lib.Preset:
        base = self._find(str(form.get("base", "")))
        data = json.loads(json.dumps(appearance.export_preset_data(base)["preset"]))
        name = str(form.get("name", "")).strip() or "My preset"
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-") or "custom"
        data.update(id=f"custom-{slug}"[:48], name=name, summary=str(form.get("summary") or f"Based on {base.name}"))
        mapping = {
            "mode": ("appearance", "mode", str),
            "wallpaper": ("appearance", "wallpaper", str),
            "fontSize": ("appearance", "font_size", int),
            "cursorSize": ("appearance", "cursor_size", int),
            "animation": ("appearance", "animation_duration", float),
            "blur": ("appearance", "blur", bool),
            "location": ("panel", "location", str),
            "thickness": ("panel", "thickness", int),
            "floating": ("panel", "floating", bool),
            "lengthMode": ("panel", "length_mode", str),
            "alignment": ("panel", "alignment", str),
            "hiding": ("panel", "hiding", str),
            "launcher": ("panel", "launcher", str),
            "taskManager": ("panel", "task_manager", str),
            "virtualDesktops": ("desktop", "virtual_desktops", int),
            "steamAutostart": ("behavior", "steam_autostart", bool),
        }
        for key, (section, field_name, cast) in mapping.items():
            if key in form and form[key] is not None:
                data[section][field_name] = cast(form[key])
        rows = data["desktop"]["virtual_desktop_rows"]
        data["desktop"]["virtual_desktop_rows"] = min(rows, data["desktop"]["virtual_desktops"])
        return preset_lib.parse_preset(data)

    @Slot("QVariant", result=str)
    def previewCustom(self, form: Any) -> str:
        try:
            return self._preview_file(self._preset_from_form(dict(form)))
        except (KeyError, ValueError, preset_lib.PresetError) as exc:
            log.warning("preview failed", extra={"error": str(exc)})
            return ""

    @Slot("QVariant", bool, result=str)
    def saveCustomPreset(self, form: Any, apply_now: bool) -> str:
        try:
            preset = self._preset_from_form(dict(form))
        except (KeyError, ValueError, preset_lib.PresetError) as exc:
            return str(exc)
        appearance.save_user_preset(self._paths, preset)
        self.refreshPresets()
        self.notify.emit(f"Saved “{preset.name}”.", "positive")
        if apply_now:
            self.applyPreset(preset.id)
        return ""

    @Slot(str)
    def deleteCustomPreset(self, preset_id: str) -> None:
        appearance.delete_user_preset(self._paths, preset_id)
        self.refreshPresets()

    @Slot(str, str)
    def exportPreset(self, preset_id: str, file_url: str) -> None:
        try:
            data = appearance.export_preset_data(self._find(preset_id))
            Path(QUrl(file_url).toLocalFile()).write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.notify.emit("Preset exported.", "positive")
        except (OSError, KeyError) as exc:
            self.notify.emit(f"Export failed: {exc}", "error")

    @Slot(str)
    def importPreset(self, file_url: str) -> None:
        try:
            raw = json.loads(Path(QUrl(file_url).toLocalFile()).read_text(encoding="utf-8"))
            preset = appearance.import_preset_data(raw)
            appearance.save_user_preset(self._paths, preset)
            self.refreshPresets()
            self.notify.emit(f"Imported “{preset.name}”. Select it to apply.", "positive")
        except (OSError, ValueError, preset_lib.PresetError) as exc:
            self.notify.emit(f"Import failed: {exc}", "error")

    # -- hardware ------------------------------------------------------------
    @Property("QVariant", notify=hardwareChanged)
    def hardware(self) -> dict[str, Any]:
        return self._hardware

    @Slot()
    def refreshHardware(self) -> None:
        self._run("Detecting hardware", lambda: hardware.collect(self._runner).to_dict(), self._set_hardware)

    def _set_hardware(self, data: dict[str, Any]) -> None:
        self._hardware = data
        self.hardwareChanged.emit()
        self.gpuChanged.emit()

    @Property(bool, notify=gpuChanged)
    def hybridGraphics(self) -> bool:
        return gaming.offload_env(self._hardware.get("gpus", [])) is not None

    @Property(bool, notify=gpuChanged)
    def steamOnDiscreteGpu(self) -> bool:
        return gaming.is_enabled(self._paths.data, "discrete_gpu")

    @Property(bool, notify=gpuChanged)
    def steamOverlay(self) -> bool:
        return gaming.is_enabled(self._paths.data, "overlay")

    @Property(bool, notify=gpuChanged)
    def gameMode(self) -> bool:
        return gaming.game_mode_active(self._paths.state)

    def _set_launcher_feature(self, feature: str, enabled: bool) -> None:
        try:
            gaming.set_feature(self._paths.data, feature, enabled, gaming.offload_env(self._hardware.get("gpus", [])))
            if (self._paths.autostart / "steam.desktop").exists():
                appearance.set_steam_autostart(self._paths, True)
        except (OSError, ValueError) as exc:
            self.notify.emit(str(exc), "error")
        else:
            self.notify.emit("Done. Quit and reopen Steam for this to take effect.", "positive")
        self.gpuChanged.emit()

    @Slot(bool)
    def setSteamOnDiscreteGpu(self, enabled: bool) -> None:
        self._set_launcher_feature("discrete_gpu", enabled)

    @Slot(bool)
    def setSteamOverlay(self, enabled: bool) -> None:
        self._set_launcher_feature("overlay", enabled)

    @Slot(bool)
    def setGameMode(self, enabled: bool) -> None:
        def run() -> list[CommandResult]:
            return gaming.set_game_mode(self._runner, self._paths.state, enabled)

        def done(results: list[CommandResult]) -> None:
            failed = [r for r in results if not r.ok]
            if failed:
                self.notify.emit("Game Mode: " + "; ".join(r.error_summary() for r in failed), "warning")
            elif enabled:
                self.notify.emit("Game Mode on: performance power profile and Do Not Disturb.", "positive")
            else:
                self.notify.emit("Game Mode off: previous power profile and notifications restored.", "positive")
            self.gpuChanged.emit()

        self._run("Switching Game Mode", run, done)

    # -- privacy -------------------------------------------------------------
    @Property("QVariant", notify=privacyChanged)
    def privacy(self) -> dict[str, Any]:
        return self._privacy

    @Slot()
    def refreshPrivacy(self) -> None:
        self._run(
            "Reading privacy settings", lambda: privacy.collect(self._runner, self._home).to_dict(), self._set_privacy
        )

    def _set_privacy(self, data: dict[str, Any]) -> None:
        self._privacy = data
        self.privacyChanged.emit()

    @Slot(str, bool)
    def setPrivacyToggle(self, name: str, enabled: bool) -> None:
        def done(res: CommandResult) -> None:
            self._report("Changing privacy setting", res, "Privacy setting updated.")
            self.refreshPrivacy()

        self._run("Changing privacy setting", lambda: privacy.set_toggle(self._runner, name, enabled), done)

    # -- games ---------------------------------------------------------------
    def _database(self) -> games.AntiCheatDatabase:
        if self._db is None:
            self._db = games.AntiCheatDatabase.load()
        return self._db

    @Property("QVariant", notify=libraryChanged)
    def library(self) -> dict[str, Any]:
        return self._library

    @Property("QVariant", notify=gameResultsChanged)
    def gameResults(self) -> list[dict[str, Any]]:
        return self._game_results

    @Property("QVariant", notify=libraryChanged)
    def datasetInfo(self) -> dict[str, Any]:
        try:
            info = self._database().info
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}
        return {
            "name": info.name,
            "url": info.url,
            "license": info.license,
            "date": info.commit_date,
            "games": len(self._database().entries),
        }

    @Slot()
    def refreshLibrary(self) -> None:
        def scan() -> dict[str, Any]:
            install = steam.scan(self._home)
            if install is None:
                return {"found": False}
            db = self._database()
            rows = []
            for game in sorted(install.games, key=lambda g: g.name.lower()):
                v = games.verdict(db.by_steam_id(game.appid), db.info, name=game.name, steam_id=game.appid)
                log_path = steam.proton_log(self._home, game.appid)
                rows.append(
                    {
                        "appid": game.appid,
                        "name": game.name,
                        "compatTool": game.compat_tool or "",
                        "installed": game.installed,
                        "category": v.category,
                        "title": v.title,
                        "explanation": v.explanation,
                        "protonLog": str(log_path) if log_path else "",
                    }
                )
            data = install.to_dict()
            data.update(found=True, rows=rows)
            return data

        self._run("Reading your Steam library", scan, self._set_library)

    def _set_library(self, data: dict[str, Any]) -> None:
        self._library = data
        self.libraryChanged.emit()

    @Slot(str)
    def checkGame(self, query: str) -> None:
        if not query.strip():
            return
        self._run(
            "Looking up game",
            lambda: [v.to_dict() for v in games.check(self._database(), query)],
            self._set_game_results,
        )

    def _set_game_results(self, data: list[dict[str, Any]]) -> None:
        self._game_results = data
        self.gameResultsChanged.emit()

    @Slot(str, result=str)
    def protonLogTail(self, appid: str) -> str:
        path = steam.proton_log(self._home, appid)
        return "".join(steam.tail(path, 60)) if path else ""

    # -- apps ----------------------------------------------------------------
    @Property("QVariant", notify=bundlesChanged)
    def bundles(self) -> list[dict[str, Any]]:
        return self._bundles

    @Slot()
    def refreshBundles(self) -> None:
        self._run("Checking installed apps", lambda: apps.bundles_with_state(self._runner), self._set_bundles)

    def _set_bundles(self, data: list[dict[str, Any]]) -> None:
        self._bundles = data
        self.bundlesChanged.emit()

    @Slot("QVariant")
    def installApps(self, app_ids: Any) -> None:
        ids = [str(a) for a in app_ids]
        if not ids:
            return

        count = "1 app" if len(ids) == 1 else f"{len(ids)} apps"

        def done(res: CommandResult) -> None:
            self._report("Installing apps", res, f"Installed {count}.")
            self.refreshBundles()

        self._run(f"Installing {count} from Flathub", lambda: apps.install(self._runner, ids), done)

    @Slot(str)
    def uninstallApp(self, app_id: str) -> None:
        def done(res: CommandResult) -> None:
            self._report("Removing app", res, "App removed.")
            self.refreshBundles()

        self._run(f"Removing {app_id}", lambda: apps.uninstall(self._runner, app_id), done)

    # -- updates ---------------------------------------------------------------
    @Property("QVariant", notify=updatesChanged)
    def updates(self) -> dict[str, Any]:
        return self._updates

    @Slot()
    def refreshUpdates(self) -> None:
        def collect() -> dict[str, Any]:
            data = updates.status(self._runner).to_dict()
            data["history"] = updates.history(self._runner)
            return data

        self._run("Checking update status", collect, self._set_updates)

    def _set_updates(self, data: dict[str, Any]) -> None:
        self._updates = data
        self.updatesChanged.emit()

    def _update_action(self, label: str, func: Callable[[Runner], CommandResult], success: str) -> None:
        def done(res: CommandResult) -> None:
            self._report(label, res, success)
            self.refreshUpdates()

        self._run(label, lambda: func(self._runner), done)

    @Slot()
    def updateNow(self) -> None:
        self._update_action(
            "Starting update", updates.update_now, "Update started in the background. It finishes at your next restart."
        )

    @Slot()
    def rollback(self) -> None:
        self._update_action(
            "Rolling back", updates.rollback, "The previous version will start after your next restart."
        )

    @Slot()
    def pinCurrent(self) -> None:
        self._update_action("Pinning this version", updates.pin_current, "This version will be kept.")

    @Slot(bool)
    def setAutoUpdates(self, enabled: bool) -> None:
        self._update_action(
            "Changing automatic updates",
            lambda r: updates.set_auto_updates(r, enabled),
            "Automatic updates turned " + ("on." if enabled else "off."),
        )

    @Slot()
    def restartNow(self) -> None:
        res = updates.restart(self._runner)
        if not res.ok:
            self.notify.emit(f"Restart failed: {res.error_summary()}", "error")

    # -- misc ------------------------------------------------------------------
    @Slot(str)
    def openSettings(self, module: str) -> None:
        """Open a KDE System Settings page (e.g. kcm_app-permissions, kcm_autostart)."""
        if not re.fullmatch(r"kcm_[A-Za-z0-9_-]+", module):
            return
        try:
            subprocess.Popen(["systemsettings", module], start_new_session=True)
        except OSError as exc:
            self.notify.emit(f"Could not open System Settings: {exc}", "error")

    @Slot(str)
    def launch(self, app: str) -> None:
        """Start one of a fixed set of companion apps by their desktop entry."""
        desktop_ids = {
            "steam": "steam",
            "store": "io.github.kolunmi.Bazaar",
            "konsole": "org.kde.konsole",
            "lutris": "net.lutris.Lutris",
            "systemmonitor": "org.kde.plasma-systemmonitor",
            "settings": "systemsettings",
        }
        desktop_id = desktop_ids.get(app)
        if desktop_id is None:
            return
        for argv in (["kstart", "--application", desktop_id], ["gtk-launch", desktop_id]):
            try:
                subprocess.Popen(argv, start_new_session=True)
                return
            except OSError:
                continue
        self.notify.emit(f"Could not start {app}.", "error")

    @Slot()
    def finishWelcome(self) -> None:
        state = appearance.Paths(self._home).state
        state.mkdir(parents=True, exist_ok=True)
        (state / "welcome-done").write_text("1\n", encoding="utf-8")
        self.welcomeFinished.emit()
