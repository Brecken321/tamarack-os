"""One-page system health summary used by `tamarack doctor` and the Center's home page."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

from . import hardware, updates
from .system import Runner

GAMING_TOOLS = {
    "steam": "Steam",
    "gamescope": "Gamescope (gaming compositor)",
    "mangohud": "MangoHud (performance overlay)",
    "lutris": "Lutris (game launcher)",
    "umu-run": "umu (Proton outside Steam)",
}


def _os_release(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in (root / "usr/lib/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def _json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def report(runner: Runner, root: Path = Path("/"), include_hardware: bool = True) -> dict[str, Any]:
    osr = _os_release(root)
    info = _json_file(root / "usr/share/ublue-os/image-info.json")
    upd = updates.status(runner, root / "var")
    gaming = {cmd: runner.which(cmd) for cmd in GAMING_TOOLS}
    flatpak_setup = _json_file(root / "var/lib/tamarack/flatpak-setup.status")
    data: dict[str, Any] = {
        "system": {
            "name": osr.get("PRETTY_NAME", "Unknown"),
            "version": osr.get("IMAGE_VERSION") or osr.get("BUILD_ID", ""),
            "image": info.get("image-name", ""),
            "based_on": f"{info.get('upstream-image', '')} {info.get('upstream-version', '')}".strip(),
            "kernel": platform.release(),
            "session": os.environ.get("XDG_SESSION_TYPE", ""),
        },
        "updates": upd.to_dict(),
        "gaming": {GAMING_TOOLS[k]: v for k, v in gaming.items()},
        "default_apps": flatpak_setup or {"state": "unknown", "message": "Default app setup has not reported yet."},
    }
    if include_hardware:
        hw = hardware.collect(runner, hardware.Environment(root=root))
        data["hardware"] = hw.to_dict()
        data["hardware_counts"] = hw.counts()
    data["problems"] = problems(data)
    return data


def problems(data: dict[str, Any]) -> list[str]:
    """Plain-language list of things that need attention."""
    out = []
    upd = data.get("updates", {})
    if upd.get("restart_needed"):
        out.append("An update is ready. Restart when convenient to finish installing it.")
    if upd.get("low_space"):
        out.append("Less than 10 GB free on the system drive; updates may fail to download.")
    for err in upd.get("errors", []):
        out.append(f"Update status unavailable: {err}")
    for name, present in data.get("gaming", {}).items():
        if not present and name.startswith(("Steam", "Gamescope", "MangoHud")):
            out.append(f"{name} is missing from this system image.")
    for item in data.get("hardware", {}).get("items", []):
        if item["status"] in (hardware.ATTENTION, hardware.MISSING):
            message = f"{item['category']}: {item['name']}"
            if item.get("advice"):
                message += f". {item['advice']}"
            out.append(message)
    if data.get("default_apps", {}).get("state") == "retrying":
        out.append(data["default_apps"].get("message", "Default apps are still being installed."))
    return out
