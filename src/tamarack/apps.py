"""Optional app bundles (Flatpak from Flathub)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .system import CommandResult, Runner

BUNDLES = Path("/usr/share/tamarack/flatpaks/bundles.toml")
REMOTE = "flathub"
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


def installed_apps(runner: Runner) -> set[str]:
    result = runner.run(["flatpak", "list", "--app", "--columns=application"], timeout=30)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()} if result.ok else set()


def bundles_with_state(runner: Runner, path: Path = BUNDLES) -> list[dict[str, Any]]:
    installed = installed_apps(runner)
    out = []
    for bundle in load_bundles(path):
        data: dict[str, Any] = {"id": bundle.id, "name": bundle.name, "description": bundle.description}
        data["apps"] = [{"id": a, "name": bundle.name_of(a), "installed": a in installed} for a in bundle.apps]
        data["installed_count"] = sum(1 for a in bundle.apps if a in installed)
        out.append(data)
    return out


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
