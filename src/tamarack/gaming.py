"""Gaming helpers: run Steam (and its games) on the discrete GPU of hybrid laptops.

On laptops with an integrated GPU plus a discrete one, the desktop runs on
the integrated GPU and apps inherit it unless told otherwise. This writes a
per-user Steam launcher that sets the PRIME render-offload variables, so
Steam and every game it starts use the discrete GPU. It is opt-in because
keeping the discrete GPU awake while Steam idles in the tray costs battery.

The override lives in ~/.local/share/applications/steam.desktop (it shadows
the system entry) and is marked so Tamarack only ever removes its own file.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SYSTEM_STEAM_DESKTOP = Path("/usr/share/applications/steam.desktop")
MARKER_KEY = "X-Tamarack-Discrete-GPU"

# NVIDIA's documented PRIME render offload variables (OpenGL + Vulkan).
NVIDIA_OFFLOAD = {
    "__NV_PRIME_RENDER_OFFLOAD": "1",
    "__VK_LAYER_NV_optimus": "NVIDIA_only",
    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
}
# Mesa: prefer the GPU that is not driving the display.
MESA_OFFLOAD = {"DRI_PRIME": "1"}


def offload_env(gpus: Sequence[Mapping[str, Any]]) -> dict[str, str] | None:
    """Environment that selects the discrete GPU, or None if there is no hybrid setup."""
    vendors = [str(g.get("vendor", "")) for g in gpus]
    if len(vendors) < 2:
        return None
    nvidia_drivers = [g.get("driver") for g in gpus if g.get("vendor") == "NVIDIA"]
    if "nvidia" in nvidia_drivers:
        return dict(NVIDIA_OFFLOAD)
    if "NVIDIA" in vendors:
        return None  # NVIDIA GPU without the NVIDIA driver: offload would not work
    return dict(MESA_OFFLOAD)


def override_path(data_home: Path) -> Path:
    return data_home / "applications" / "steam.desktop"


def is_enabled(data_home: Path) -> bool:
    path = override_path(data_home)
    try:
        return f"{MARKER_KEY}=true" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def build_override(system_entry: str, env: Mapping[str, str]) -> str:
    """Prefix every Exec= line (main entry and actions) with `env VAR=...`."""
    prefix = "env " + " ".join(f"{k}={v}" for k, v in env.items()) + " "

    def patch(match: re.Match[str]) -> str:
        command = match.group(1)
        if command.startswith("env ") and "__NV_PRIME_RENDER_OFFLOAD" in command:
            return match.group(0)
        return f"Exec={prefix}{command}"

    text = re.sub(r"^Exec=(.*)$", patch, system_entry, flags=re.MULTILINE)
    # Mark the file in the main [Desktop Entry] group.
    return re.sub(r"^\[Desktop Entry\]$", f"[Desktop Entry]\n{MARKER_KEY}=true", text, count=1, flags=re.MULTILINE)


def set_enabled(
    data_home: Path, enabled: bool, env: Mapping[str, str] | None, system_entry: Path = SYSTEM_STEAM_DESKTOP
) -> None:
    path = override_path(data_home)
    if not enabled:
        if is_enabled(data_home):
            path.unlink()
        return
    if env is None:
        raise ValueError("no hybrid graphics setup detected; Steam already uses the only GPU")
    if path.exists() and not is_enabled(data_home):
        raise FileExistsError(f"{path} was customized by you; Tamarack will not overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_override(system_entry.read_text(encoding="utf-8"), env), encoding="utf-8")
