"""Example data for rendering Tamarack Center outside Tamarack OS.

Used only by ``tamarack-center --screenshots`` (the CI page previews), so
the interface can be reviewed in minutes without building and booting an
image. It describes an example hybrid-graphics gaming laptop. The installed
app never uses it: it always reads the real system.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl

from .. import appearance, apps, games, privacy
from .. import presets as preset_lib
from ..brand import Brand
from ..system import FakeRunner
from .backend import Backend, _preset_dict

REPO = Path(__file__).resolve().parents[3]
SYSTEM_FILES = REPO / "system_files/usr/share/tamarack"

# Labels Backend._run uses for data refreshes, mapped to example data.
# Every other label is an action (install, apply, …), which a preview skips.
REFRESHES = {
    "Checking your system": "doctor",
    "Detecting hardware": "hardware",
    "Reading privacy settings": "privacy",
    "Reading your Steam library": "library",
    "Checking installed apps": "bundles",
    "Checking update status": "updates",
    "Looking up game": "game_results",
    "Searching Flathub": "search",
}

INSTALLED = [
    "org.mozilla.firefox",
    "org.kde.gwenview",
    "org.kde.okular",
    "org.kde.haruna",
    "org.kde.kcalc",
    "org.kde.ark",
    "com.heroicgameslauncher.hgl",
    "com.discordapp.Discord",
    "com.obsproject.Studio",
]

STEAM_GAMES = [
    ("1245620", "ELDEN RING", True),
    ("1091500", "Cyberpunk 2077", True),
    ("413150", "Stardew Valley", True),
    ("1172470", "Apex Legends", False),
    ("730", "Counter-Strike 2", False),
]


def _hardware() -> dict[str, Any]:
    def item(
        category: str, name: str, status: str = "ok", detail: str = "", driver: str = "", advice: str = ""
    ) -> dict[str, str]:
        return {
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
            "driver": driver,
            "advice": advice,
        }

    return {
        "items": [
            item("Processor", "Intel Core i5-10300H", detail="8 threads"),
            item(
                "Memory",
                "7.6 GiB RAM",
                "attention",
                advice="Many recent games need 16 GB; close background apps while gaming.",
            ),
            item("Graphics", "NVIDIA GeForce GTX 1650 Ti Mobile", detail="NVIDIA Corporation TU117M", driver="nvidia"),
            item("Graphics", "Intel UHD Graphics", detail="Intel Corporation CometLake-H GT2", driver="i915"),
            item("Graphics", "Vulkan: 2 GPUs ready", detail="NVIDIA GeForce GTX 1650 Ti, Intel UHD Graphics (CML GT2)"),
            item("Displays", "eDP-1", detail="1920x1080 @ 144 Hz, scale 1"),
            item("Storage", "nvme0n1", detail="512 GB NVMe SSD"),
            item("Network", "Wi-Fi", detail="Intel Wi-Fi 6 AX201", driver="iwlwifi"),
            item("Network", "Ethernet", detail="Realtek RTL8111/8168", driver="r8169"),
            item("Audio", "Built-in audio", detail="Intel Comet Lake PCH cAVS", driver="snd_hda_intel"),
            item("Bluetooth", "Bluetooth adapter", detail="Intel AX201 Bluetooth", driver="btusb"),
            item("Battery BAT0", "Battery", detail="84% charged, health 91%"),
            item("Controllers", "Xbox Wireless Controller", detail="Connected over Bluetooth"),
        ],
        "gpus": [
            {"vendor": "Intel", "driver": "i915", "name": "Intel UHD Graphics"},
            {"vendor": "NVIDIA", "driver": "nvidia", "name": "NVIDIA GeForce GTX 1650 Ti Mobile"},
        ],
    }


def _deployment(role: str, version: str, date: str) -> dict[str, Any]:
    return {
        "role": role,
        "version": version,
        "image": "ghcr.io/brecken321/tamarack-os-nvidia:stable",
        "timestamp": 0,
        "pinned": False,
        "digest": "sha256:" + "0" * 64,
        "date": date,
    }


def _updates() -> dict[str, Any]:
    return {
        "booted": _deployment("booted", "44.20261027", "2026-10-27"),
        "staged": None,
        "rollback": _deployment("rollback", "44.20261020", "2026-10-20"),
        "auto_updates": True,
        "free_bytes": 300 * 1024**3,
        "low_space": False,
        "restart_needed": False,
        "transaction": None,
        "errors": [],
        "history": [
            {"time": "2026-10-20 09:12 UTC", "result": "success", "message": "Finished System Update."},
            {"time": "2026-10-27 09:08 UTC", "result": "success", "message": "Finished System Update."},
        ],
    }


def _privacy(appstream: Path) -> dict[str, Any]:
    catalog = privacy.load_catalog(SYSTEM_FILES / "privacy/catalog.toml")
    runner = FakeRunner()
    runner.add(
        ["systemctl", "list-unit-files"],
        "".join(f"{s['unit']} enabled enabled\n" for s in catalog.get("service", [])),
    )
    names = apps.installed_names(_installed_runner())
    report = privacy.PrivacyReport(
        toggles={
            "countme": False,
            "connectivity": True,
            "store_search": True,
            "recent_files": True,
            "steam_autostart": False,
        },
        services=privacy.service_inventory(runner, catalog),
        network_catalog=list(catalog.get("network", [])),
    )
    perms = {
        "org.mozilla.firefox": "[Context]\nshared=network;ipc;\nsockets=wayland;pulseaudio;\ndevices=all;\n",
        "com.discordapp.Discord": "[Context]\nshared=network;ipc;\nsockets=wayland;pulseaudio;\n",
        "com.obsproject.Studio": "[Context]\nshared=network;ipc;\nsockets=wayland;pulseaudio;\nfilesystems=host;\n",
        "com.heroicgameslauncher.hgl": "[Context]\nshared=network;ipc;\nfilesystems=home;\n",
    }
    for app_id, name in sorted(names.items(), key=lambda kv: kv[1].lower()):
        parsed = privacy.parse_flatpak_permissions(app_id, perms.get(app_id, "[Context]\nsockets=wayland;\n"), {})
        report.apps.append(replace(parsed, name=name))
    report.autostart = [
        privacy.AutostartEntry("Discord", "~/.config/autostart/discord.desktop", "user", True),
        privacy.AutostartEntry("Steam", "~/.config/autostart/steam.desktop", "user", False),
    ]
    data = report.to_dict()
    for app in data["apps"]:
        app["icon"] = apps.icon_path(app["app_id"], appstream)
    return data


def _installed_runner() -> FakeRunner:
    runner = FakeRunner()
    names = {
        "org.mozilla.firefox": "Firefox",
        "org.kde.gwenview": "Gwenview",
        "org.kde.okular": "Okular",
        "org.kde.haruna": "Haruna",
        "org.kde.kcalc": "KCalc",
        "org.kde.ark": "Ark",
        "com.heroicgameslauncher.hgl": "Heroic Games Launcher",
        "com.discordapp.Discord": "Discord",
        "com.obsproject.Studio": "OBS Studio",
    }
    runner.add(["flatpak", "list"], "".join(f"{a}\t{names[a]}\n" for a in INSTALLED))
    return runner


def _library(db: games.AntiCheatDatabase) -> dict[str, Any]:
    rows = []
    for appid, name, installed in STEAM_GAMES:
        v = games.verdict(db.by_steam_id(appid), db.info, name=name, steam_id=appid)
        rows.append(
            {
                "appid": appid,
                "name": name,
                "compatTool": "proton_experimental" if appid == "1245620" else "",
                "installed": installed,
                "category": v.category,
                "title": v.title,
                "explanation": v.explanation,
                "protonLog": "",
            }
        )
    rows.sort(key=lambda r: str(r["name"]).lower())
    return {
        "found": True,
        "rows": rows,
        "proton_versions": ["Proton 10.0", "Proton Experimental"],
        "custom_tools": ["GE-Proton10-25"],
    }


def _search(appstream: Path) -> tuple[str, list[dict[str, Any]]]:
    found = [
        ("org.supertuxproject.SuperTux", "SuperTux", "A jump-and-run game starring Tux the Penguin"),
        ("net.supertuxkart.SuperTuxKart", "SuperTuxKart", "A 3D open-source kart racing game"),
        ("net.sourceforge.ExtremeTuxRacer", "Extreme Tux Racer", "High speed arctic racing game"),
    ]
    return "tux", [
        {"id": a, "name": n, "summary": s, "installed": False, "icon": apps.icon_path(a, appstream)}
        for a, n, s in found
    ]


class DemoBackend(Backend):
    def __init__(self, brand: Brand, data_root: Path, appstream: Path, welcome: bool = False) -> None:
        super().__init__(brand, FakeRunner(), welcome=welcome, data_root=data_root)
        self.requests: list[str] = []
        # Show everything a Tamarack system offers.
        self._gaming_session = True
        self._appstream = appstream
        hardware = _hardware()
        problems = [f"Memory: 7.6 GiB RAM. {hardware['items'][1]['advice']}"]
        db = self._database()
        self._fixture: dict[str, Any] = {
            "hardware": hardware,
            "updates": _updates(),
            "privacy": _privacy(appstream),
            "library": _library(db),
            "bundles": apps.bundles_with_state(_installed_runner(), SYSTEM_FILES / "flatpaks/bundles.toml", appstream),
            "game_results": [v.to_dict() for v in games.check(db, "Apex Legends")],
            "search": _search(appstream),
            "doctor": {
                "system": {
                    "name": brand.name,
                    "version": "44.20261027",
                    "image": brand.image_nvidia,
                    "based_on": "bazzite 44.20261026",
                    "kernel": "7.2.11-ogc4.1.fc44.x86_64",
                },
                "updates": _updates(),
                "gaming": {
                    "Steam": True,
                    "Gamescope (gaming compositor)": True,
                    "MangoHud (performance overlay)": True,
                    "Lutris (game launcher)": True,
                    "umu (Proton outside Steam)": True,
                },
                "default_apps": {"state": "done", "message": "All default apps are set up."},
                "hardware": hardware,
                "problems": problems,
            },
        }
        # Show the Apps page with a search already made.
        self._search_query, self._search_results = self._fixture["search"]

    def _run(self, label: str, func: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        # Every request is recorded (the button check uses this); only data
        # refreshes are answered.
        self.requests.append(label)
        key = next((k for prefix, k in REFRESHES.items() if label.startswith(prefix)), None)
        if key is not None:
            on_done(self._fixture[key])

    def _has_tool(self, name: str) -> bool:
        return True

    def _database(self) -> games.AntiCheatDatabase:
        if self._db is None:
            self._db = games.AntiCheatDatabase.load(REPO / "data/awacy/games.json", REPO / "data/awacy/source.json")
        return self._db

    def _all_presets(self) -> list[preset_lib.Preset]:
        return appearance.all_presets(self._paths, REPO / "branding/presets")

    def _preset_rows(self) -> list[dict[str, Any]]:
        found = preset_lib.load_presets(REPO / "branding/presets")
        default = preset_lib.default_preset(found)
        previews = self._data_root / "usr/share/tamarack/presets/previews"
        return [
            _preset_dict(p, default.id, QUrl.fromLocalFile(str(previews / f"{p.id}.png")).toString(), True)
            for p in found
        ]
