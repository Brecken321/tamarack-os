"""Privacy dashboard data: what runs, what talks to the network, who can access what.

Everything here is read-only except :func:`set_toggle`, which changes a small
set of documented optional behaviors through their normal system mechanisms
(systemctl via pkexec, NetworkManager's D-Bus API, kwriteconfig6).
"""

from __future__ import annotations

import configparser
import logging
import re
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .system import CommandResult, Runner

log = logging.getLogger("tamarack.privacy")

CATALOG = Path("/usr/share/tamarack/privacy/catalog.toml")


@dataclass(frozen=True)
class ServiceInfo:
    unit: str
    state: str
    name: str
    purpose: str
    network: bool | None
    safe_to_disable: bool | None
    known: bool


@dataclass(frozen=True)
class Listener:
    protocol: str
    address: str
    port: str
    process: str


@dataclass(frozen=True)
class AppPermissions:
    app_id: str
    camera: bool
    microphone: bool
    location: bool
    files: str
    network: bool
    background: bool
    devices: tuple[str, ...]


@dataclass(frozen=True)
class AutostartEntry:
    name: str
    path: str
    scope: str  # "user" or "system"
    enabled: bool


@dataclass
class PrivacyReport:
    toggles: dict[str, bool | None] = field(default_factory=dict)
    services: list[ServiceInfo] = field(default_factory=list)
    listeners: list[Listener] = field(default_factory=list)
    apps: list[AppPermissions] = field(default_factory=list)
    autostart: list[AutostartEntry] = field(default_factory=list)
    network_catalog: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "toggles": self.toggles,
            "services": [asdict(s) for s in self.services],
            "listeners": [asdict(x) for x in self.listeners],
            "apps": [asdict(a) for a in self.apps],
            "autostart": [asdict(a) for a in self.autostart],
            "network_catalog": self.network_catalog,
        }


def load_catalog(path: Path = CATALOG) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("privacy catalog unavailable", extra={"path": str(path), "error": str(exc)})
        return {"network": [], "service": []}


# --- Parsers ------------------------------------------------------------------


def parse_unit_files(text: str) -> list[tuple[str, str]]:
    """Parse ``systemctl list-unit-files --no-legend --plain`` lines: (unit, state)."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and "." in parts[0]:
            rows.append((parts[0], parts[1]))
    return rows


def parse_ss(text: str) -> list[Listener]:
    """Parse ``ss -tulpnH`` output (listening TCP/UDP sockets)."""
    listeners = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[4]
        address, _, port = local.rpartition(":")
        process = ""
        match = re.search(r'users:\(\("([^"]+)"', line)
        if match:
            process = match.group(1)
        listeners.append(Listener(proto, address.strip("[]"), port, process))
    return listeners


def is_loopback(address: str) -> bool:
    address = address.split("%", 1)[0]
    return address.startswith("127.") or address in ("::1", "localhost")


def parse_flatpak_permissions(app_id: str, metadata: str, store: dict[str, set[str]]) -> AppPermissions:
    """Interpret ``flatpak info --show-permissions APP`` plus portal permission store grants."""
    parser = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    parser.optionxform = str  # type: ignore[assignment,method-assign]
    try:
        parser.read_string(metadata)
    except configparser.Error:
        parser.read_string("[Context]\n")
    ctx = parser["Context"] if parser.has_section("Context") else {}

    def items(key: str) -> list[str]:
        return [v for v in str(ctx.get(key, "")).split(";") if v]

    devices = items("devices")
    sockets = items("sockets")
    shared = items("shared")
    filesystems = items("filesystems")
    if any(fs.split(":")[0] in ("host", "host-os", "host-etc") for fs in filesystems):
        files = "All files on the system"
    elif any(fs.split(":")[0] in ("home", "~") for fs in filesystems):
        files = "Your whole home folder"
    elif filesystems:
        files = "Some folders: " + ", ".join(fs.split(":")[0] for fs in filesystems[:4])
    else:
        files = "Only files you choose"
    granted = store.get(app_id, set())
    return AppPermissions(
        app_id=app_id,
        camera="all" in devices or "camera" in granted,
        microphone="pulseaudio" in sockets or "microphone" in granted,
        location="location" in granted,
        files=files,
        network="network" in shared,
        background="background" in granted,
        devices=tuple(devices),
    )


def parse_permission_store(text: str) -> dict[str, set[str]]:
    """Parse ``flatpak permissions TABLE`` rows: Table, Object, App, Permissions, Data."""
    grants: dict[str, set[str]] = {}
    for line in text.splitlines():
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) < 4 or parts[0] in ("Table", ""):
            continue
        table, obj, app, perms = parts[0], parts[1], parts[2], parts[3]
        if "yes" not in perms:
            continue
        kind = {"devices": obj, "location": "location", "background": "background"}.get(table, table)
        grants.setdefault(app, set()).add(kind)
    return grants


def parse_desktop_file(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    in_entry = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if in_entry and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip())
    return values


def autostart_entries(home: Path, system_dir: Path = Path("/etc/xdg/autostart")) -> list[AutostartEntry]:
    """Effective autostart apps for a KDE session (user files override system ones)."""
    entries: dict[str, AutostartEntry] = {}
    for scope, directory in (("system", system_dir), ("user", home / ".config/autostart")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            try:
                data = parse_desktop_file(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            only = data.get("OnlyShowIn", "")
            not_in = data.get("NotShowIn", "")
            if (only and "KDE" not in only.split(";")) or "KDE" in not_in.split(";"):
                continue
            enabled = (
                data.get("Hidden", "false").lower() != "true"
                and data.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
            )
            entries[path.name] = AutostartEntry(data.get("Name", path.stem), str(path), scope, enabled)
    return sorted(entries.values(), key=lambda e: e.name.lower())


# --- Collection ---------------------------------------------------------------


def service_inventory(runner: Runner, catalog: dict[str, Any]) -> list[ServiceInfo]:
    known = {s["unit"]: s for s in catalog.get("service", [])}
    result = runner.run(
        [
            "systemctl",
            "list-unit-files",
            "--type=service,timer,socket",
            "--state=enabled",
            "--no-legend",
            "--plain",
            "--no-pager",
        ]
    )
    rows = parse_unit_files(result.stdout) if result.ok else []
    services = []
    for unit, state in rows:
        info = known.get(unit)
        if info:
            services.append(
                ServiceInfo(
                    unit, state, info["name"], info["purpose"], info.get("network"), info.get("safe_to_disable"), True
                )
            )
        else:
            services.append(ServiceInfo(unit, state, unit, "", None, None, False))
    return services


def toggles(runner: Runner, home: Path) -> dict[str, bool | None]:
    out: dict[str, bool | None] = {}
    countme = runner.run(["systemctl", "is-enabled", "rpm-ostree-countme.timer"])
    out["countme"] = countme.stdout.strip() == "enabled" if countme.stdout.strip() else None
    nm = runner.run(
        [
            "busctl",
            "get-property",
            "org.freedesktop.NetworkManager",
            "/org/freedesktop/NetworkManager",
            "org.freedesktop.NetworkManager",
            "ConnectivityCheckEnabled",
        ]
    )
    out["connectivity"] = nm.stdout.strip().endswith("true") if nm.ok else None
    store = runner.run(
        [
            "kreadconfig6",
            "--file",
            "krunnerrc",
            "--group",
            "Plugins",
            "--key",
            "bazaarrunnerEnabled",
            "--default",
            "true",
        ]
    )
    out["store_search"] = store.stdout.strip() != "false" if store.ok else None
    recent = runner.run(
        [
            "kreadconfig6",
            "--file",
            "kactivitymanagerd-pluginsrc",
            "--group",
            "Plugin-org.kde.ActivityManager.Resources.Scoring",
            "--key",
            "what-to-remember",
            "--default",
            "0",
        ]
    )
    out["recent_files"] = recent.stdout.strip() != "2" if recent.ok else None
    autostart = autostart_entries(home)
    out["steam_autostart"] = any(e.name == "Steam" and e.enabled and e.scope == "user" for e in autostart)
    return out


TOGGLES = ("countme", "connectivity", "store_search", "recent_files")


def set_toggle(runner: Runner, name: str, enabled: bool) -> CommandResult:
    """Change one optional behavior. Privileged changes go through pkexec (polkit)."""
    if name == "countme":
        verb = "enable" if enabled else "disable"
        return runner.run(["pkexec", "systemctl", verb, "--now", "rpm-ostree-countme.timer"], timeout=120)
    if name == "connectivity":
        return runner.run(
            [
                "busctl",
                "set-property",
                "org.freedesktop.NetworkManager",
                "/org/freedesktop/NetworkManager",
                "org.freedesktop.NetworkManager",
                "ConnectivityCheckEnabled",
                "b",
                "true" if enabled else "false",
            ],
            timeout=60,
        )
    if name == "store_search":
        return runner.run(
            [
                "kwriteconfig6",
                "--file",
                "krunnerrc",
                "--group",
                "Plugins",
                "--key",
                "bazaarrunnerEnabled",
                "--notify",
                "true" if enabled else "false",
            ]
        )
    if name == "recent_files":
        # 0 = remember all, 2 = remember nothing (KDE's own Recent Files setting).
        return runner.run(
            [
                "kwriteconfig6",
                "--file",
                "kactivitymanagerd-pluginsrc",
                "--group",
                "Plugin-org.kde.ActivityManager.Resources.Scoring",
                "--key",
                "what-to-remember",
                "--notify",
                "0" if enabled else "2",
            ]
        )
    raise ValueError(f"unknown privacy toggle {name!r}; known: {', '.join(TOGGLES)}")


def flatpak_apps(runner: Runner) -> list[AppPermissions]:
    listing = runner.run(["flatpak", "list", "--app", "--columns=application"], timeout=30)
    if not listing.ok:
        return []
    store_text = ""
    for table in ("devices", "location", "background"):
        res = runner.run(["flatpak", "permissions", table], timeout=15)
        if res.ok:
            store_text += res.stdout
    store = parse_permission_store(store_text)
    apps = []
    for app_id in sorted({line.strip() for line in listing.stdout.splitlines() if line.strip()}):
        info = runner.run(["flatpak", "info", "--show-permissions", app_id], timeout=15)
        apps.append(parse_flatpak_permissions(app_id, info.stdout if info.ok else "", store))
    return apps


def collect(runner: Runner, home: Path | None = None, catalog_path: Path = CATALOG) -> PrivacyReport:
    home = home or Path.home()
    catalog = load_catalog(catalog_path)
    report = PrivacyReport(network_catalog=list(catalog.get("network", [])))

    def listeners() -> None:
        result = runner.run(["ss", "-tulpnH"])
        if result.ok:
            report.listeners.extend(parse_ss(result.stdout))

    probes: list[tuple[str, Callable[[], None]]] = [
        ("toggles", lambda: report.toggles.update(toggles(runner, home))),
        ("services", lambda: report.services.extend(service_inventory(runner, catalog))),
        ("listeners", listeners),
        ("apps", lambda: report.apps.extend(flatpak_apps(runner))),
        ("autostart", lambda: report.autostart.extend(autostart_entries(home))),
    ]
    for name, probe in probes:
        try:
            probe()
        except Exception:  # one failing probe must not hide the rest of the dashboard
            log.exception("privacy probe failed", extra={"probe": name})
    return report
