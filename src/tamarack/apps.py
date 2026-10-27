"""Apps from Flathub: optional bundles, search, install and remove."""

from __future__ import annotations

import platform
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .system import CommandResult, Runner

BUNDLES = Path("/usr/share/tamarack/flatpaks/bundles.toml")
REMOTE = "flathub"
# Flathub's catalog (AppStream) as Flatpak keeps it for system installs. It
# includes an icon for every app, installed or not.
APPSTREAM = Path("/var/lib/flatpak/appstream") / REMOTE / (platform.machine() or "x86_64") / "active"
SEARCH_LIMIT = 40
_APP_ID = re.compile(r"^[A-Za-z][\w-]*(\.[\w-]+){2,}$")


@dataclass(frozen=True)
class Bundle:
    id: str
    name: str
    description: str
    apps: tuple[str, ...]
    # Human-readable names for the app ids (falls back to the id).
    names: dict[str, str] = field(default_factory=dict)

    def name_of(self, app_id: str) -> str:
        return self.names.get(app_id, app_id)


def parse_bundles(data: dict[str, Any]) -> list[Bundle]:
    bundles = []
    seen = set()
    for raw in data.get("bundle", []):
        bundle_id = raw.get("id")
        apps = raw.get("apps")
        if not isinstance(bundle_id, str) or not isinstance(apps, list) or not apps:
            raise ValueError(f"bundle {bundle_id!r} needs an id and a non-empty apps list")
        if bundle_id in seen:
            raise ValueError(f"duplicate bundle id {bundle_id!r}")
        seen.add(bundle_id)
        ids: list[str] = []
        names: dict[str, str] = {}
        for app in apps:
            # Either a bare id or a table: { id = "...", name = "..." }.
            app_id = app.get("id") if isinstance(app, dict) else app
            if not isinstance(app_id, str) or not _APP_ID.match(app_id):
                raise ValueError(f"bundle {bundle_id!r}: {app!r} is not a valid Flatpak app id")
            ids.append(app_id)
            if isinstance(app, dict) and isinstance(app.get("name"), str):
                names[app_id] = app["name"]
        bundles.append(
            Bundle(bundle_id, str(raw.get("name", bundle_id)), str(raw.get("description", "")), tuple(ids), names)
        )
    return bundles


def load_bundles(path: Path = BUNDLES) -> list[Bundle]:
    with path.open("rb") as fh:
        return parse_bundles(tomllib.load(fh))


def installed_names(runner: Runner) -> dict[str, str]:
    """Installed apps (any remote) mapped to their display names."""
    result = runner.run(["flatpak", "list", "--app", "--columns=application,name"], timeout=30)
    if not result.ok:
        return {}
    names = {}
    for line in result.stdout.splitlines():
        app_id, _, name = line.strip().partition("\t")
        if app_id:
            names[app_id] = name.strip() or app_id
    return names


def installed_apps(runner: Runner) -> set[str]:
    return set(installed_names(runner))


def icon_path(app_id: str, appstream: Path = APPSTREAM) -> str:
    """The app's icon from the Flathub catalog, or "" if the catalog has none."""
    # Older apps are listed under "<id>.desktop", and a few in lowercase.
    names = (app_id, f"{app_id}.desktop", app_id.lower(), f"{app_id.lower()}.desktop")
    for size in ("128x128", "64x64"):
        for name in names:
            path = appstream / "icons" / size / f"{name}.png"
            if path.is_file():
                return str(path)
    return ""


def bundles_with_state(runner: Runner, path: Path = BUNDLES, appstream: Path = APPSTREAM) -> list[dict[str, Any]]:
    installed = installed_apps(runner)
    out = []
    for bundle in load_bundles(path):
        data: dict[str, Any] = {"id": bundle.id, "name": bundle.name, "description": bundle.description}
        data["apps"] = [
            {"id": a, "name": bundle.name_of(a), "installed": a in installed, "icon": icon_path(a, appstream)}
            for a in bundle.apps
        ]
        data["installed_count"] = sum(1 for a in bundle.apps if a in installed)
        out.append(data)
    return out


@dataclass(frozen=True)
class SearchResult:
    id: str
    name: str
    summary: str


def parse_search(text: str) -> list[SearchResult]:
    """Parse ``flatpak search --columns=application,name,description,remotes`` (tab-separated)."""
    seen: set[str] = set()
    results = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split("\t")]
        if len(cols) < 4:
            continue  # e.g. "No matches found"
        app_id, name, summary, remotes = cols[:4]
        if not _APP_ID.match(app_id) or app_id in seen or REMOTE not in remotes.split(","):
            continue
        seen.add(app_id)
        results.append(SearchResult(app_id, name or app_id, summary))
    return results


def search(runner: Runner, query: str, appstream: Path = APPSTREAM, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    """Search Flathub's catalog. Runs locally against the downloaded catalog."""
    query = query.strip()
    if not query:
        return []
    if not appstream.exists():
        # A fresh install may not have the catalog yet; downloading it needs no authorization.
        runner.run(["flatpak", "update", "--appstream", "--noninteractive", REMOTE], timeout=300)
    result = runner.run(["flatpak", "search", "--columns=application,name,description,remotes", query], timeout=60)
    if not result.ok:
        raise RuntimeError(f"flatpak search failed: {result.error_summary()}")
    installed = installed_apps(runner)
    return [
        {
            "id": r.id,
            "name": r.name,
            "summary": r.summary,
            "installed": r.id in installed,
            "icon": icon_path(r.id, appstream),
        }
        for r in parse_search(result.stdout)[:limit]
    ]


def install(runner: Runner, app_ids: list[str]) -> CommandResult:
    """Install apps system-wide from Flathub (polkit may ask for authorization)."""
    for app in app_ids:
        if not _APP_ID.match(app):
            raise ValueError(f"not a valid Flatpak app id: {app!r}")
    return runner.run(
        ["flatpak", "install", "--system", "--noninteractive", "--or-update", REMOTE, *app_ids], timeout=3600
    )


def uninstall(runner: Runner, app_id: str) -> CommandResult:
    if not _APP_ID.match(app_id):
        raise ValueError(f"not a valid Flatpak app id: {app_id!r}")
    return runner.run(["flatpak", "uninstall", "--system", "--noninteractive", app_id], timeout=600)
