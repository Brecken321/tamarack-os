"""Gaming helpers: a per-user Steam launcher with optional features, and Game Mode.

Steam launcher features (each opt-in):

* ``discrete_gpu``: on hybrid laptops, set the PRIME render-offload variables
  so Steam and every game it starts use the discrete GPU. Off by default
  because keeping that GPU awake while Steam idles costs battery.
* ``overlay``: set ``MANGOHUD=1`` so every Steam game shows the MangoHud
  performance overlay (FPS, frame times, CPU/GPU load and temperatures).

The launcher lives in ~/.local/share/applications/steam.desktop (it shadows
the system entry). It is rebuilt from the system entry whenever features
change and is marked so Tamarack only ever replaces or removes its own file.

Game Mode switches the power profile to "performance" (when the hardware
offers it) and turns on Do Not Disturb; turning it off restores both.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .system import CommandResult, Runner

SYSTEM_STEAM_DESKTOP = Path("/usr/share/applications/steam.desktop")
OWNER_KEY = "X-Tamarack-Launcher"
FEATURE_KEYS = {
    "discrete_gpu": "X-Tamarack-Discrete-GPU",
    "overlay": "X-Tamarack-Performance-Overlay",
}

# NVIDIA's documented PRIME render offload variables (OpenGL + Vulkan).
NVIDIA_OFFLOAD = {
    "__NV_PRIME_RENDER_OFFLOAD": "1",
    "__VK_LAYER_NV_optimus": "NVIDIA_only",
    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
}
# Mesa: prefer the GPU that is not driving the display.
MESA_OFFLOAD = {"DRI_PRIME": "1"}
OVERLAY_ENV = {"MANGOHUD": "1"}


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


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def is_ours(data_home: Path) -> bool:
    return f"{OWNER_KEY}=true" in _read(override_path(data_home))


def enabled_features(data_home: Path) -> set[str]:
    text = _read(override_path(data_home))
    if f"{OWNER_KEY}=true" not in text:
        return set()
    return {name for name, key in FEATURE_KEYS.items() if f"{key}=true" in text}


def is_enabled(data_home: Path, feature: str = "discrete_gpu") -> bool:
    return feature in enabled_features(data_home)


def build_override(system_entry: str, env: Mapping[str, str], features: Iterable[str]) -> str:
    """Prefix every Exec= line (main entry and actions) with `env VAR=...` and mark the file."""
    prefix = "env " + " ".join(f"{k}={v}" for k, v in env.items()) + " " if env else ""

    def patch(match: re.Match[str]) -> str:
        return f"Exec={prefix}{match.group(1)}"

    text = re.sub(r"^Exec=(.*)$", patch, system_entry, flags=re.MULTILINE)
    markers = [f"{OWNER_KEY}=true"] + [f"{FEATURE_KEYS[f]}=true" for f in sorted(features)]
    return re.sub(r"^\[Desktop Entry\]$", "[Desktop Entry]\n" + "\n".join(markers), text, count=1, flags=re.MULTILINE)


def apply_features(
    data_home: Path, features: set[str], dgpu_env: Mapping[str, str] | None, system_entry: Path = SYSTEM_STEAM_DESKTOP
) -> None:
    unknown = features - set(FEATURE_KEYS)
    if unknown:
        raise ValueError(f"unknown Steam launcher feature(s): {sorted(unknown)}")
    path = override_path(data_home)
    if path.exists() and not is_ours(data_home):
        raise FileExistsError(f"{path} was customized by you; Tamarack will not overwrite it")
    if not features:
        path.unlink(missing_ok=True)
        return
    env: dict[str, str] = {}
    if "discrete_gpu" in features:
        if dgpu_env is None:
            raise ValueError("no hybrid graphics setup detected; Steam already uses the only GPU")
        env.update(dgpu_env)
    if "overlay" in features:
        env.update(OVERLAY_ENV)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_override(system_entry.read_text(encoding="utf-8"), env, features), encoding="utf-8")


def current_dgpu_env(data_home: Path) -> dict[str, str] | None:
    """The offload variables already in our launcher, so other changes keep them."""
    text = _read(override_path(data_home)) if is_ours(data_home) else ""
    if "__NV_PRIME_RENDER_OFFLOAD=1" in text:
        return dict(NVIDIA_OFFLOAD)
    if "DRI_PRIME=1" in text:
        return dict(MESA_OFFLOAD)
    return None


def set_feature(
    data_home: Path,
    feature: str,
    enabled: bool,
    dgpu_env: Mapping[str, str] | None,
    system_entry: Path = SYSTEM_STEAM_DESKTOP,
) -> None:
    features = enabled_features(data_home)
    if enabled:
        features.add(feature)
    else:
        features.discard(feature)
    if dgpu_env is None:
        dgpu_env = current_dgpu_env(data_home)
    apply_features(data_home, features, dgpu_env, system_entry)


# --- Game Mode -------------------------------------------------------------------

PPD = ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles")
DND_FOREVER = "2099-12-31T23:59:59"


def _busctl_string(output: str) -> str:
    # `busctl get-property` prints e.g.: s "balanced"
    match = re.search(r'"([^"]*)"', output)
    return match.group(1) if match else ""


def power_profiles(runner: Runner) -> tuple[str, list[str]]:
    """(active profile, available profiles) from power-profiles-daemon/tuned-ppd; ("", []) if unavailable."""
    active = runner.run(["busctl", "get-property", *PPD, "ActiveProfile"])
    if not active.ok:
        return "", []
    listing = runner.run(["busctl", "--json=short", "get-property", *PPD, "Profiles"])
    names: list[str] = []
    if listing.ok:
        try:
            data = json.loads(listing.stdout).get("data", [])
            names = [str(p.get("Profile", {}).get("data", "")) for p in data]
        except (json.JSONDecodeError, AttributeError):
            names = []
    return _busctl_string(active.stdout), [n for n in names if n]


def game_mode_state_file(state_dir: Path) -> Path:
    return state_dir / "gamemode.json"


def game_mode_active(state_dir: Path) -> bool:
    return game_mode_state_file(state_dir).exists()


def set_game_mode(runner: Runner, state_dir: Path, enabled: bool) -> list[CommandResult]:
    """Turn Game Mode on/off. Returns the commands' results so callers can report failures."""
    results: list[CommandResult] = []
    state_file = game_mode_state_file(state_dir)
    if enabled:
        if state_file.exists():
            return results
        active, available = power_profiles(runner)
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"previous_profile": active}), encoding="utf-8")
        if "performance" in available and active != "performance":
            results.append(runner.run(["busctl", "set-property", *PPD, "ActiveProfile", "s", "performance"]))
        results.append(
            runner.run(
                [
                    "kwriteconfig6",
                    "--file",
                    "plasmanotifyrc",
                    "--group",
                    "DoNotDisturb",
                    "--key",
                    "Until",
                    "--notify",
                    DND_FOREVER,
                ]
            )
        )
        return results
    if not state_file.exists():
        return results
    try:
        previous = str(json.loads(state_file.read_text(encoding="utf-8")).get("previous_profile", ""))
    except (OSError, json.JSONDecodeError):
        previous = ""
    if previous:
        results.append(runner.run(["busctl", "set-property", *PPD, "ActiveProfile", "s", previous]))
    results.append(
        runner.run(
            [
                "kwriteconfig6",
                "--file",
                "plasmanotifyrc",
                "--group",
                "DoNotDisturb",
                "--key",
                "Until",
                "--notify",
                "--delete",
            ]
        )
    )
    state_file.unlink(missing_ok=True)
    return results
