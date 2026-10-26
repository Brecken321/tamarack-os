import json
from pathlib import Path

import pytest

from tamarack import hardware
from tamarack.system import FakeRunner

FIX = Path(__file__).resolve().parent / "fixtures/hw"


def test_parse_lspci() -> None:
    devices = hardware.parse_lspci((FIX / "lspci-hybrid-laptop.txt").read_text(encoding="utf-8"))
    gpus = [d for d in devices if d.class_code in hardware.GPU_CLASSES]
    assert [(g.vendor, g.driver) for g in gpus] == [("Intel", "i915"), ("NVIDIA", "nvidia")]
    nvidia = gpus[1]
    assert nvidia.description == "NVIDIA Corporation TU117M [GeForce GTX 1650 Ti Mobile]"
    assert nvidia.modules == ("nouveau", "nvidia_drm", "nvidia")
    ethernet = next(d for d in devices if d.class_code == "0200")
    assert ethernet.driver is None and ethernet.modules == ("r8169",)


def test_parse_vulkaninfo() -> None:
    devices = hardware.parse_vulkaninfo_summary((FIX / "vulkaninfo-summary.txt").read_text(encoding="utf-8"))
    assert [d["deviceName"] for d in devices] == ["Intel(R) UHD Graphics (CML GT2)", "NVIDIA GeForce GTX 1650 Ti"]
    assert devices[1]["driverInfo"] == "580.95.05"


def test_controllers_and_wheels() -> None:
    devices = hardware.parse_input_devices((FIX / "input-devices.txt").read_text(encoding="utf-8"))
    pads = hardware.controllers(devices)
    assert [(p["name"], p["kind"]) for p in pads] == [
        ("Microsoft Xbox Series S|X Controller", "Game controller"),
        ("Logitech G29 Driving Force Racing Wheel", "Racing wheel"),
    ]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("NVIDIA Corporation TU117M [GeForce GTX 1650 Ti Mobile]", True),
        ("NVIDIA Corporation AD104 [GeForce RTX 4070]", True),
        ("NVIDIA Corporation GB205 [GeForce RTX 5070]", True),
        ("NVIDIA Corporation GP104 [GeForce GTX 1080]", False),
        ("NVIDIA Corporation GM206 [GeForce GTX 960]", False),
        ("NVIDIA Corporation Device 2c05", None),
    ],
)
def test_nvidia_open_support(description: str, expected: bool | None) -> None:
    assert hardware.nvidia_open_supported(description) is expected


def _system(tmp_path: Path, image: str) -> hardware.Environment:
    (tmp_path / "usr/share/ublue-os").mkdir(parents=True)
    (tmp_path / "usr/share/ublue-os/image-info.json").write_text(json.dumps({"image-name": image}), encoding="utf-8")
    (tmp_path / "proc/bus/input").mkdir(parents=True)
    (tmp_path / "proc/bus/input/devices").write_text(
        (FIX / "input-devices.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "proc/asound").mkdir(parents=True)
    (tmp_path / "proc/asound/cards").write_text(" 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n", encoding="utf-8")
    (tmp_path / "proc/cpuinfo").write_text(
        "processor : 0\nmodel name : Intel(R) Core(TM) i5-10300H CPU @ 2.50GHz\nprocessor : 1\n", encoding="utf-8"
    )
    (tmp_path / "proc/meminfo").write_text("MemTotal:        8013472 kB\n", encoding="utf-8")
    bat = tmp_path / "sys/class/power_supply/BAT0"
    bat.mkdir(parents=True)
    for name, value in {
        "capacity": "81",
        "status": "Discharging",
        "energy_full": "41000000",
        "energy_full_design": "48000000",
        "charge_control_end_threshold": "80",
    }.items():
        (bat / name).write_text(value + "\n", encoding="utf-8")
    (tmp_path / "sys/module/nvidia").mkdir(parents=True)
    (tmp_path / "sys/module/nvidia/version").write_text("580.95.05\n", encoding="utf-8")
    return hardware.Environment(root=tmp_path)


def _runner() -> FakeRunner:
    runner = FakeRunner()
    runner.add(["lspci", "-nnk"], (FIX / "lspci-hybrid-laptop.txt").read_text(encoding="utf-8"))
    runner.add(["vulkaninfo", "--summary"], (FIX / "vulkaninfo-summary.txt").read_text(encoding="utf-8"))
    return runner


def test_collect_on_nvidia_edition(tmp_path: Path) -> None:
    report = hardware.collect(_runner(), _system(tmp_path, "tamarack-os-nvidia"))
    by_name = {(i.category, i.name): i for i in report.items}
    nvidia = by_name[("Graphics", "NVIDIA GPU")]
    assert nvidia.status == hardware.OK and "580.95.05" in nvidia.detail
    assert by_name[("Graphics", "Hybrid graphics (laptop)")].status == hardware.INFO
    assert by_name[("Network", "Ethernet")].status == hardware.MISSING  # driver not bound in fixture
    assert by_name[("Controllers", "Microsoft Xbox Series S|X Controller")].status == hardware.OK
    battery = by_name[("Power", "Battery BAT0")]
    assert "health 85%" in battery.detail and "charge limit 80%" in battery.detail
    assert any(i.name.startswith("Vulkan: NVIDIA") for i in report.items)
    memory = next(i for i in report.items if i.category == "Memory")
    assert memory.status == hardware.OK
    assert "16 GB" in memory.advice  # 7.6 GiB works, but many recent games want 16 GB


def test_nvidia_gpu_on_main_edition_recommends_switch(tmp_path: Path) -> None:
    lspci = (
        (FIX / "lspci-hybrid-laptop.txt")
        .read_text(encoding="utf-8")
        .replace("Kernel driver in use: nvidia", "Kernel driver in use: nouveau")
    )
    runner = _runner()
    runner.add(["lspci", "-nnk"], lspci)
    report = hardware.collect(runner, _system(tmp_path, "tamarack-os"))
    nvidia = next(i for i in report.items if i.name == "NVIDIA GPU")
    assert nvidia.status == hardware.ATTENTION
    assert "tamarack-os-nvidia" in nvidia.advice


def test_collect_survives_missing_tools(tmp_path: Path) -> None:
    report = hardware.collect(FakeRunner(), hardware.Environment(root=tmp_path))
    names = [i.name for i in report.items]
    assert "No graphics card detected" in names
    assert any(i.name == "Vulkan" and i.status == hardware.ATTENTION for i in report.items)


def test_software_rendering_is_flagged() -> None:
    report = hardware.Report()
    hardware.gpu_items(
        report,
        [],
        [{"deviceName": "llvmpipe (LLVM 19.1.0, 256 bits)", "driverName": "llvmpipe"}],
        hardware.Environment(),
        nvidia_image=False,
    )
    assert any(i.status == hardware.ATTENTION and "software" in i.name for i in report.items)
