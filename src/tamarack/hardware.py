"""Hardware detection and driver diagnostics.

Collects what the system sees (PCI devices and their kernel drivers, Vulkan
devices, displays, input devices/controllers, storage, battery, audio,
network) and turns it into plain-language items with a status:

* ``ok``        recognized and a driver is in use
* ``attention`` recognized but something needs action (explained in detail)
* ``missing``   expected hardware/driver not found
* ``info``      informational

Parsers are pure functions over command output/file text and are unit tested
with fixtures captured from real systems.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .system import Runner

log = logging.getLogger("tamarack.hardware")

OK, ATTENTION, MISSING, INFO = "ok", "attention", "missing", "info"


@dataclass(frozen=True)
class PciDevice:
    slot: str
    class_name: str
    class_code: str
    description: str
    vendor_id: str
    device_id: str
    driver: str | None
    modules: tuple[str, ...]

    @property
    def vendor(self) -> str:
        return {"10de": "NVIDIA", "1002": "AMD", "8086": "Intel"}.get(self.vendor_id, self.vendor_id)


@dataclass(frozen=True)
class Item:
    category: str
    name: str
    status: str
    detail: str = ""
    driver: str = ""
    advice: str = ""


@dataclass
class Report:
    items: list[Item] = field(default_factory=list)
    gpus: list[dict[str, Any]] = field(default_factory=list)

    def add(self, *args: Any, **kwargs: Any) -> None:
        self.items.append(Item(*args, **kwargs))

    def to_dict(self) -> dict[str, Any]:
        return {"items": [asdict(i) for i in self.items], "gpus": self.gpus}

    def counts(self) -> dict[str, int]:
        out = {OK: 0, ATTENTION: 0, MISSING: 0, INFO: 0}
        for item in self.items:
            out[item.status] += 1
        return out


# --- Parsers ------------------------------------------------------------------

_LSPCI_HEAD = re.compile(
    r"^(?P<slot>[0-9a-fA-F:.]+)\s+(?P<cls>.+?)\s+\[(?P<code>[0-9a-fA-F]{4})\]:\s+"
    r"(?P<desc>.*)\s+\[(?P<vendor>[0-9a-fA-F]{4}):(?P<device>[0-9a-fA-F]{4})\]"
)


def parse_lspci(text: str) -> list[PciDevice]:
    """Parse ``lspci -nnk`` output."""
    devices: list[PciDevice] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        if current:
            devices.append(
                PciDevice(
                    slot=current["slot"],
                    class_name=current["cls"],
                    class_code=current["code"].lower(),
                    description=re.sub(r"\s+\(rev [0-9a-f]+\)$", "", current["desc"]).strip(),
                    vendor_id=current["vendor"].lower(),
                    device_id=current["device"].lower(),
                    driver=current.get("driver"),
                    modules=tuple(current.get("modules", ())),
                )
            )

    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            flush()
            match = _LSPCI_HEAD.match(line.split(" (rev ")[0] if " (rev " in line else line)
            current = match.groupdict() if match else None
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("Kernel driver in use:"):
            current["driver"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Kernel modules:"):
            current["modules"] = [m.strip() for m in stripped.split(":", 1)[1].split(",") if m.strip()]
    flush()
    return devices


def parse_vulkaninfo_summary(text: str) -> list[dict[str, str]]:
    """Parse the Devices section of ``vulkaninfo --summary``."""
    devices: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_devices = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "Devices:":
            in_devices = True
            continue
        if not in_devices:
            continue
        if re.fullmatch(r"GPU\d+:", line):
            current = {"index": line[3:-1]}
            devices.append(current)
        elif current is not None and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            current[key] = value
    return devices


def parse_input_devices(text: str) -> list[dict[str, str]]:
    """Parse /proc/bus/input/devices into dicts with name, handlers, bus ids."""
    devices = []
    for block in text.strip().split("\n\n"):
        info: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("N: Name="):
                info["name"] = line[len("N: Name=") :].strip().strip('"')
            elif line.startswith("H: Handlers="):
                info["handlers"] = line[len("H: Handlers=") :].strip()
            elif line.startswith("I: "):
                for part in line[3:].split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        info[k.lower()] = v.lower()
        if "name" in info:
            devices.append(info)
    return devices


_CONTROLLER_WORDS = re.compile(
    r"controller|gamepad|joystick|xbox|dualsense|dualshock|wireless controller|8bitdo|pro controller|"
    r"steam deck|joy-con|stadia",
    re.IGNORECASE,
)
_NOT_CONTROLLER = re.compile(r"motion sensors|touchpad|consumer control|system control|keyboard|mouse", re.IGNORECASE)


def controllers(devices: list[dict[str, str]]) -> list[dict[str, str]]:
    found = []
    for dev in devices:
        handlers = dev.get("handlers", "")
        name = dev.get("name", "")
        if _NOT_CONTROLLER.search(name):
            continue
        if re.search(r"\bjs\d+\b", handlers) or _CONTROLLER_WORDS.search(name):
            kind = "Racing wheel" if re.search(r"wheel", name, re.IGNORECASE) else "Game controller"
            found.append({**dev, "kind": kind})
    return found


def parse_asound_cards(text: str) -> list[str]:
    cards = []
    for line in text.splitlines():
        match = re.match(r"^\s*\d+\s+\[[^\]]*\]:\s+(.*)$", line)
        if match:
            cards.append(match.group(1).strip())
    return cards


def nvidia_open_supported(description: str) -> bool | None:
    """Whether NVIDIA's open kernel modules support this GPU (Turing or newer).

    Uses the chip codename in the lspci description (TU/GA/AD/GH/GB = Turing
    and later; GP/GM/GK/GV = older). Returns None when it cannot tell.
    """
    match = re.search(r"\b(TU|GA|AD|GH|GB|GP|GM|GK|GV|GF)\d{2,3}", description)
    if not match:
        return None
    return match.group(1) in {"TU", "GA", "AD", "GH", "GB"}


# --- Collection ---------------------------------------------------------------

GPU_CLASSES = {"0300", "0302", "0380"}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@dataclass
class Environment:
    """Where to read system files from (overridable in tests)."""

    root: Path = Path("/")
    image_flavor: str = ""

    def path(self, rel: str) -> Path:
        return self.root / rel.lstrip("/")


def gpu_items(
    report: Report, devices: list[PciDevice], vulkan: list[dict[str, str]], env: Environment, nvidia_image: bool
) -> None:
    gpus = [d for d in devices if d.class_code in GPU_CLASSES]
    if not gpus:
        report.add("Graphics", "No graphics card detected", MISSING, "lspci reported no display controller.")
    vendors = {g.vendor for g in gpus}
    for gpu in gpus:
        driver = gpu.driver or ""
        status, advice, detail = OK, "", gpu.description
        if gpu.vendor == "NVIDIA":
            supported = nvidia_open_supported(gpu.description)
            if driver == "nvidia":
                version = _read(env.path("/sys/module/nvidia/version")).strip()
                detail = f"{gpu.description}; NVIDIA driver {version}".strip("; ") if version else gpu.description
            elif not nvidia_image:
                status = ATTENTION
                if supported is False:
                    advice = (
                        "This NVIDIA GPU is older than Turing (GTX 16 series) and needs NVIDIA's legacy "
                        "driver, which Tamarack OS does not build yet. It runs on the open-source "
                        "nouveau driver with limited performance; see Help > Troubleshooting."
                    )
                else:
                    advice = (
                        "You are on the AMD/Intel edition. Switch to the NVIDIA edition for full "
                        "performance: sudo bootc switch ghcr.io/brecken321/tamarack-os-nvidia:stable"
                    )
            elif not driver:
                status = ATTENTION
                advice = (
                    "The NVIDIA driver is installed but not loaded. If Secure Boot is on, enroll the "
                    "signing key (ujust enroll-secure-boot-key) and reboot."
                )
            elif driver == "nouveau":
                status = ATTENTION
                advice = "Using nouveau instead of the NVIDIA driver; see Help > Troubleshooting > NVIDIA."
        elif gpu.vendor == "AMD":
            if driver == "radeon":
                status = ATTENTION
                advice = (
                    "Old 'radeon' driver in use; Vulkan games need amdgpu (GCN 1.0/1.1 cards may need a kernel option)."
                )
            elif not driver:
                status = MISSING
                advice = "No driver loaded for this AMD GPU."
        elif gpu.vendor == "Intel" and not driver:
            status = MISSING
            advice = "No driver loaded for this Intel GPU."
        elif not driver:
            status = ATTENTION
            advice = "No kernel driver in use (normal for virtual machines with a basic display adapter)."
        report.add("Graphics", f"{gpu.vendor} GPU", status, detail, driver, advice)
        report.gpus.append({**asdict(gpu), "vendor": gpu.vendor})
    integrated = {"Intel", "AMD"} & vendors
    if "NVIDIA" in vendors and integrated:
        report.add(
            "Graphics",
            "Hybrid graphics (laptop)",
            INFO,
            "The desktop runs on the integrated GPU. Games can use the NVIDIA GPU; see Help > Hybrid laptops "
            "for how to check and choose which GPU a game uses.",
        )
    if vulkan:
        for dev in vulkan:
            name = dev.get("deviceName", "Unknown")
            if "llvmpipe" in name.lower():
                report.add(
                    "Graphics",
                    "Vulkan: software rendering only",
                    ATTENTION,
                    f"{name} ({dev.get('driverName', '')})",
                    advice="Only the CPU fallback renderer is available; games will be very slow.",
                )
            else:
                report.add(
                    "Graphics",
                    f"Vulkan: {name}",
                    OK,
                    f"API {dev.get('apiVersion', '?')}, {dev.get('driverName', '')} "
                    f"{dev.get('driverInfo', '')}".strip(),
                    dev.get("driverName", ""),
                )
    else:
        report.add(
            "Graphics",
            "Vulkan",
            ATTENTION,
            "vulkaninfo found no devices or is unavailable.",
            advice="Steam/Proton needs Vulkan for most Windows games.",
        )


def device_items(report: Report, devices: list[PciDevice]) -> None:
    for dev in devices:
        if dev.class_code in ("0200", "0280"):
            kind = "Wi-Fi" if dev.class_code == "0280" else "Ethernet"
            if dev.driver:
                report.add("Network", kind, OK, dev.description, dev.driver)
            else:
                report.add(
                    "Network",
                    kind,
                    MISSING,
                    dev.description,
                    advice="No driver is loaded for this network adapter; it may lack Linux support.",
                )
        elif dev.class_code == "0108":
            report.add("Storage", "NVMe controller", OK if dev.driver else ATTENTION, dev.description, dev.driver or "")


def storage_items(report: Report, runner: Runner) -> None:
    result = runner.run(["lsblk", "--json", "--bytes", "-o", "NAME,MODEL,SIZE,TYPE,ROTA,TRAN,FSTYPE,MOUNTPOINTS"])
    if not result.ok:
        return
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk" or str(dev.get("name", "")).startswith(("zram", "loop")):
            continue
        size = int(dev.get("size") or 0) / 1e9
        kind = "HDD" if dev.get("rota") in (True, "1", 1) else "SSD"
        tran = (dev.get("tran") or "").upper()
        name = (dev.get("model") or dev.get("name") or "Disk").strip()
        report.add("Storage", name, OK, f"{size:.0f} GB {tran} {kind}".replace("  ", " "))


def input_items(report: Report, env: Environment) -> None:
    devices = parse_input_devices(_read(env.path("/proc/bus/input/devices")))
    pads = controllers(devices)
    if pads:
        for pad in pads:
            report.add("Controllers", pad["name"], OK, pad["kind"], advice="")
    else:
        report.add(
            "Controllers", "No game controller connected", INFO, "Plug in or pair a controller (Bluetooth) and refresh."
        )


def battery_items(report: Report, env: Environment) -> None:
    supply = env.path("/sys/class/power_supply")
    if not supply.is_dir():
        return
    for bat in sorted(supply.glob("BAT*")):
        capacity = _read(bat / "capacity").strip()
        status = _read(bat / "status").strip()
        full = _read(bat / "energy_full").strip() or _read(bat / "charge_full").strip()
        design = _read(bat / "energy_full_design").strip() or _read(bat / "charge_full_design").strip()
        health = ""
        if full.isdigit() and design.isdigit() and int(design) > 0:
            health = f", health {int(full) * 100 // int(design)}%"
        limit = _read(bat / "charge_control_end_threshold").strip()
        limit_text = f", charge limit {limit}% (set in System Settings > Power)" if limit else ""
        report.add("Power", f"Battery {bat.name}", OK, f"{capacity}% {status.lower()}{health}{limit_text}")


def audio_items(report: Report, env: Environment, runner: Runner) -> None:
    cards = parse_asound_cards(_read(env.path("/proc/asound/cards")))
    if not cards:
        report.add("Audio", "Sound card", MISSING, "No sound cards found in /proc/asound/cards.")
    for card in cards:
        report.add("Audio", card, OK)
    info = runner.run(["pactl", "info"], timeout=5)
    if info.ok:
        server = next(
            (line.split(":", 1)[1].strip() for line in info.stdout.splitlines() if line.startswith("Server Name:")), ""
        )
        report.add("Audio", "Sound server", OK, server)


def bluetooth_items(report: Report, env: Environment) -> None:
    adapters = (
        sorted(env.path("/sys/class/bluetooth").glob("hci*")) if env.path("/sys/class/bluetooth").is_dir() else []
    )
    if adapters:
        report.add("Bluetooth", "Bluetooth adapter", OK, ", ".join(a.name for a in adapters))
    else:
        report.add("Bluetooth", "Bluetooth", INFO, "No Bluetooth adapter found.")


def camera_items(report: Report, env: Environment) -> None:
    base = env.path("/sys/class/video4linux")
    if not base.is_dir():
        return
    seen = set()
    for dev in sorted(base.glob("video*")):
        name = _read(dev / "name").strip()
        if name and name not in seen:
            seen.add(name)
            report.add("Cameras", name, OK)


def display_items(report: Report, runner: Runner) -> None:
    result = runner.run(["kscreen-doctor", "--json"], timeout=10)
    if not result.ok:
        return
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return
    for out in data.get("outputs", []):
        if not out.get("connected"):
            continue
        mode: dict[str, Any] = next((m for m in out.get("modes", []) if m.get("id") == out.get("currentModeId")), {})
        size = mode.get("size", {})
        detail = f"{size.get('width', '?')}x{size.get('height', '?')} @ {float(mode.get('refreshRate', 0)):.0f} Hz"
        if out.get("scale"):
            detail += f", scale {out['scale']:g}"
        report.add("Displays", out.get("name", "Display"), OK if out.get("enabled") else INFO, detail)


def cpu_memory_items(report: Report, env: Environment) -> None:
    cpuinfo = _read(env.path("/proc/cpuinfo"))
    model = next(
        (line.split(":", 1)[1].strip() for line in cpuinfo.splitlines() if line.startswith("model name")), "Unknown CPU"
    )
    threads = sum(1 for line in cpuinfo.splitlines() if line.startswith("processor"))
    report.add("Processor", model, OK, f"{threads} threads")
    meminfo = _read(env.path("/proc/meminfo"))
    total = re.search(r"^MemTotal:\s+(\d+) kB", meminfo, re.MULTILINE)
    if total:
        gib = int(total.group(1)) / 1024 / 1024
        advice = "Many recent games need 16 GB; close background apps while gaming." if gib < 15 else ""
        report.add("Memory", f"{gib:.1f} GiB RAM", ATTENTION if gib < 7 else OK, advice=advice)


def collect(runner: Runner, env: Environment | None = None) -> Report:
    env = env or Environment(image_flavor=os.environ.get("TAMARACK_IMAGE_FLAVOR", ""))
    report = Report()
    nvidia_image = "nvidia" in _image_name(env)
    lspci = runner.run(["lspci", "-nnk"])
    devices = parse_lspci(lspci.stdout) if lspci.ok else []
    vk = runner.run(["vulkaninfo", "--summary"], timeout=20)
    vulkan = parse_vulkaninfo_summary(vk.stdout) if vk.ok else []
    steps: list[Callable[[], None]] = [
        lambda: cpu_memory_items(report, env),
        lambda: gpu_items(report, devices, vulkan, env, nvidia_image),
        lambda: display_items(report, runner),
        lambda: storage_items(report, runner),
        lambda: device_items(report, devices),
        lambda: audio_items(report, env, runner),
        lambda: bluetooth_items(report, env),
        lambda: input_items(report, env),
        lambda: camera_items(report, env),
        lambda: battery_items(report, env),
    ]
    for step in steps:
        try:
            step()
        except Exception:  # one broken probe must not hide the rest of the report
            log.exception("hardware probe failed")
    return report


def _image_name(env: Environment) -> str:
    try:
        return str(json.loads(_read(env.path("/usr/share/ublue-os/image-info.json")) or "{}").get("image-name", ""))
    except json.JSONDecodeError:
        return ""
