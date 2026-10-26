"""Read-only inspection of the user's Steam installation.

Finds Steam libraries, installed games, installed Proton versions and the
compatibility tool chosen per game, so Tamarack Center can show them next
to anti-cheat verdicts and help diagnose launch problems. Never touches
Steam credentials or modifies Steam files.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import vdf

log = logging.getLogger("tamarack.steam")

# StateFlags bit 4 (value 4) = "fully installed" in appmanifest files.
STATE_FULLY_INSTALLED = 4
# Steam's own runtime/redistributable entries that are not games.
NON_GAME_PREFIXES = ("Proton", "Steam Linux Runtime", "Steamworks Common Redistributables", "SteamVR")


@dataclass(frozen=True)
class SteamApp:
    appid: str
    name: str
    install_dir: str
    library: str
    size_on_disk: int
    installed: bool
    compat_tool: str | None = None

    @property
    def is_tool(self) -> bool:
        return self.name.startswith(NON_GAME_PREFIXES)


@dataclass
class SteamInstall:
    root: Path
    libraries: list[Path] = field(default_factory=list)
    apps: list[SteamApp] = field(default_factory=list)
    proton_versions: list[str] = field(default_factory=list)
    custom_tools: list[str] = field(default_factory=list)
    default_compat_tool: str | None = None

    @property
    def games(self) -> list[SteamApp]:
        return [a for a in self.apps if not a.is_tool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "libraries": [str(p) for p in self.libraries],
            "games": [asdict(a) for a in sorted(self.games, key=lambda a: a.name.lower())],
            "proton_versions": self.proton_versions,
            "custom_tools": self.custom_tools,
            "default_compat_tool": self.default_compat_tool,
        }


def candidate_roots(home: Path) -> list[Path]:
    return [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    ]


def find_root(home: Path) -> Path | None:
    for candidate in candidate_roots(home):
        if (candidate / "steamapps").is_dir():
            return candidate.resolve()
    return None


def _read_vdf(path: Path) -> vdf.VdfDict:
    try:
        return vdf.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, vdf.VdfError) as exc:
        log.warning("could not read Steam file", extra={"path": str(path), "error": str(exc)})
        return {}


def libraries(root: Path) -> list[Path]:
    """Library folders from steamapps/libraryfolders.vdf (always includes root)."""
    result = [root]
    data = _read_vdf(root / "steamapps/libraryfolders.vdf")
    for key, value in vdf.get_dict(data, "libraryfolders").items():
        if not key.isdigit():
            continue
        path_value = vdf.get_ci(value, "path") if isinstance(value, dict) else value
        if isinstance(path_value, str):
            path = Path(path_value)
            if path.resolve() != root and path not in result:
                result.append(path)
    return result


def apps_in(library: Path, compat: dict[str, str]) -> list[SteamApp]:
    apps = []
    for manifest in sorted((library / "steamapps").glob("appmanifest_*.acf")):
        state = vdf.get_dict(_read_vdf(manifest), "AppState")
        appid = vdf.get_ci(state, "appid")
        name = vdf.get_ci(state, "name")
        if not isinstance(appid, str) or not isinstance(name, str):
            continue
        flags = vdf.get_ci(state, "StateFlags")
        size = vdf.get_ci(state, "SizeOnDisk")
        installdir = vdf.get_ci(state, "installdir")
        flag_value = int(flags) if isinstance(flags, str) and flags.isdigit() else 0
        apps.append(
            SteamApp(
                appid=appid,
                name=name,
                install_dir=installdir if isinstance(installdir, str) else "",
                library=str(library),
                size_on_disk=int(size) if isinstance(size, str) and size.isdigit() else 0,
                installed=bool(flag_value & STATE_FULLY_INSTALLED),
                compat_tool=compat.get(appid),
            )
        )
    return apps


def compat_mapping(root: Path) -> dict[str, str]:
    """appid -> compatibility tool name; key "0" is the default for all games."""
    data = _read_vdf(root / "config/config.vdf")
    mapping = vdf.get_dict(data, "InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping")
    result = {}
    for appid, value in mapping.items():
        if isinstance(value, dict):
            name = vdf.get_ci(value, "name")
            if isinstance(name, str) and name:
                result[appid] = name
    return result


def scan(home: Path) -> SteamInstall | None:
    root = find_root(home)
    if root is None:
        return None
    compat = compat_mapping(root)
    install = SteamInstall(root=root, libraries=libraries(root), default_compat_tool=compat.get("0"))
    for library in install.libraries:
        install.apps.extend(apps_in(library, compat))
        common = library / "steamapps/common"
        if common.is_dir():
            install.proton_versions.extend(
                sorted(p.name for p in common.iterdir() if p.is_dir() and p.name.startswith("Proton"))
            )
    tools_dir = root / "compatibilitytools.d"
    if tools_dir.is_dir():
        install.custom_tools = sorted(p.name for p in tools_dir.iterdir() if p.is_dir())
    return install


def launch_uri(appid: str) -> str:
    return f"steam://rungameid/{appid}"


def proton_log(home: Path, appid: str) -> Path | None:
    """Proton writes ~/steam-<appid>.log when launched with PROTON_LOG=1."""
    path = home / f"steam-{appid}.log"
    return path if path.exists() else None


def tail(path: Path, lines: int = 40) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()[-lines:]
    except OSError:
        return []
