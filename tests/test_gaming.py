import json
from pathlib import Path

import pytest

from tamarack import appearance, gaming
from tamarack.system import FakeRunner

STEAM_ENTRY = """[Desktop Entry]
Name=Steam
Exec=/usr/bin/bazzite-steam %U
Icon=steam
Actions=Store;

[Desktop Action Store]
Name=Store
Exec=/usr/bin/bazzite-steam steam://store
"""

INTEL = {"vendor": "Intel", "driver": "i915"}
NVIDIA = {"vendor": "NVIDIA", "driver": "nvidia"}
NOUVEAU = {"vendor": "NVIDIA", "driver": "nouveau"}
AMD = {"vendor": "AMD", "driver": "amdgpu"}


@pytest.fixture
def system_entry(tmp_path: Path) -> Path:
    path = tmp_path / "system-steam.desktop"
    path.write_text(STEAM_ENTRY, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("gpus", "expected"),
    [
        ([INTEL, NVIDIA], gaming.NVIDIA_OFFLOAD),
        ([AMD, NVIDIA], gaming.NVIDIA_OFFLOAD),
        ([INTEL, AMD], gaming.MESA_OFFLOAD),
        ([AMD, AMD], gaming.MESA_OFFLOAD),
        ([INTEL, NOUVEAU], None),  # offload variables need the NVIDIA driver
        ([NVIDIA], None),
        ([], None),
    ],
)
def test_offload_env(gpus: list[dict[str, str]], expected: dict[str, str] | None) -> None:
    assert gaming.offload_env(gpus) == expected


def test_override_prefixes_every_exec_line() -> None:
    text = gaming.build_override(
        STEAM_ENTRY, {**gaming.NVIDIA_OFFLOAD, **gaming.OVERLAY_ENV}, {"discrete_gpu", "overlay"}
    )
    execs = [line for line in text.splitlines() if line.startswith("Exec=")]
    assert len(execs) == 2
    assert all(line.startswith("Exec=env __NV_PRIME_RENDER_OFFLOAD=1 ") and "MANGOHUD=1" in line for line in execs)
    assert execs[1].endswith("/usr/bin/bazzite-steam steam://store")
    assert text.startswith("[Desktop Entry]\nX-Tamarack-Launcher=true\nX-Tamarack-Discrete-GPU=true\n")


def test_features_combine_and_are_removed_cleanly(tmp_path: Path, system_entry: Path) -> None:
    data = tmp_path / "data"
    gaming.set_feature(data, "discrete_gpu", True, gaming.NVIDIA_OFFLOAD, system_entry)
    # Hardware info is not needed again: the existing offload variables are kept.
    gaming.set_feature(data, "overlay", True, None, system_entry)
    assert gaming.enabled_features(data) == {"discrete_gpu", "overlay"}
    text = gaming.override_path(data).read_text(encoding="utf-8")
    assert "__NV_PRIME_RENDER_OFFLOAD=1" in text and "MANGOHUD=1" in text
    gaming.set_feature(data, "discrete_gpu", False, None, system_entry)
    text = gaming.override_path(data).read_text(encoding="utf-8")
    assert "__NV_PRIME_RENDER_OFFLOAD" not in text and "MANGOHUD=1" in text
    gaming.set_feature(data, "overlay", False, None, system_entry)
    assert not gaming.override_path(data).exists()


def test_autostart_uses_the_users_launcher(tmp_path: Path, system_entry: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(appearance, "STEAM_DESKTOP", system_entry)
    paths = appearance.Paths(tmp_path)
    gaming.set_feature(paths.data, "discrete_gpu", True, gaming.NVIDIA_OFFLOAD, system_entry)
    appearance.set_steam_autostart(paths, True)
    autostart = (paths.autostart / "steam.desktop").read_text(encoding="utf-8")
    assert "Exec=env __NV_PRIME_RENDER_OFFLOAD=1" in autostart and "-silent" in autostart


def test_never_overwrites_a_user_file(tmp_path: Path, system_entry: Path) -> None:
    user_file = gaming.override_path(tmp_path)
    user_file.parent.mkdir(parents=True)
    user_file.write_text("[Desktop Entry]\nName=My Steam\nExec=steam -bigpicture\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        gaming.set_feature(tmp_path, "overlay", True, None, system_entry)
    with pytest.raises(FileExistsError):
        gaming.set_feature(tmp_path, "overlay", False, None, system_entry)
    assert user_file.read_text(encoding="utf-8").startswith("[Desktop Entry]\nName=My Steam")


def test_discrete_gpu_without_hybrid_setup_is_an_error(tmp_path: Path, system_entry: Path) -> None:
    with pytest.raises(ValueError, match="no hybrid"):
        gaming.set_feature(tmp_path, "discrete_gpu", True, None, system_entry)
    with pytest.raises(ValueError, match="unknown"):
        gaming.apply_features(tmp_path, {"turbo"}, None, system_entry)


def _ppd_runner(active: str = "balanced") -> FakeRunner:
    runner = FakeRunner()
    runner.add(["busctl", "get-property", *gaming.PPD, "ActiveProfile"], f's "{active}"\n')
    profiles = {
        "type": "aa{sv}",
        "data": [{"Profile": {"type": "s", "data": p}} for p in ("power-saver", "balanced", "performance")],
    }
    runner.add(["busctl", "--json=short", "get-property"], json.dumps(profiles))
    runner.add(["busctl", "set-property"])
    runner.add(["kwriteconfig6"])
    return runner


def test_game_mode_on_and_off_restores_previous_state(tmp_path: Path) -> None:
    runner = _ppd_runner("power-saver")
    assert all(r.ok for r in gaming.set_game_mode(runner, tmp_path, True))
    assert gaming.game_mode_active(tmp_path)
    calls = [list(c) for c in runner.calls]
    assert ["busctl", "set-property", *gaming.PPD, "ActiveProfile", "s", "performance"] in calls
    assert any(c[0] == "kwriteconfig6" and gaming.DND_FOREVER in c for c in calls)
    # KConfig's date format: at least six comma-separated numbers, or Plasma ignores it.
    assert [int(x) for x in gaming.DND_FOREVER.split(",")][:6] == [2099, 12, 31, 23, 59, 59]
    runner.calls.clear()
    gaming.set_game_mode(runner, tmp_path, False)
    calls = [list(c) for c in runner.calls]
    assert ["busctl", "set-property", *gaming.PPD, "ActiveProfile", "s", "power-saver"] in calls
    assert any(c[0] == "kwriteconfig6" and "--delete" in c for c in calls)
    assert not gaming.game_mode_active(tmp_path)


def test_game_mode_without_power_profiles_still_silences_notifications(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.add(["kwriteconfig6"])
    results = gaming.set_game_mode(runner, tmp_path, True)
    assert [r.argv[0] for r in results] == ["kwriteconfig6"]
    assert gaming.set_game_mode(runner, tmp_path, True) == []  # already on: no-op


@pytest.mark.parametrize(
    ("choices", "expected"),
    [
        ([], ""),
        (["overlay"], "mangohud %command%"),
        (["fps60"], "MANGOHUD_CONFIG=fps_limit=60,no_display mangohud %command%"),
        (["overlay", "fps60"], "MANGOHUD_CONFIG=fps_limit=60 mangohud %command%"),
        (["fsr"], "gamescope -f -F fsr -- %command%"),
        (["fsr", "overlay"], "gamescope -f -F fsr --mangoapp -- %command%"),
        (["gamemode", "protonlog"], "PROTON_LOG=1 gamemoderun %command%"),
    ],
)
def test_launch_options(choices: list[str], expected: str) -> None:
    assert gaming.launch_options(choices) == expected


def test_launch_options_discrete_gpu_uses_the_offload_variables() -> None:
    options = gaming.launch_options(["dgpu", "overlay"], gaming.NVIDIA_OFFLOAD)
    assert options.startswith("__NV_PRIME_RENDER_OFFLOAD=1 ") and options.endswith(" mangohud %command%")
    # Without a hybrid setup there is nothing to add.
    assert gaming.launch_options(["dgpu"], None) == "%command%"


def test_launch_options_reject_unknown_choices() -> None:
    with pytest.raises(ValueError, match="unknown launch options"):
        gaming.launch_options(["turbo"])
