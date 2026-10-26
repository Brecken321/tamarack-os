from pathlib import Path

import pytest

from tamarack import appearance, gaming

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
    text = gaming.build_override(STEAM_ENTRY, gaming.NVIDIA_OFFLOAD)
    execs = [line for line in text.splitlines() if line.startswith("Exec=")]
    assert len(execs) == 2
    assert all(
        line.startswith("Exec=env __NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only") for line in execs
    )
    assert execs[1].endswith("/usr/bin/bazzite-steam steam://store")
    assert text.startswith(f"[Desktop Entry]\n{gaming.MARKER_KEY}=true\n")
    # Applying twice does not double the prefix.
    assert gaming.build_override(text, gaming.NVIDIA_OFFLOAD).count("__NV_PRIME_RENDER_OFFLOAD") == 2


def test_enable_disable_and_autostart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    system = tmp_path / "steam.desktop"
    system.write_text(STEAM_ENTRY, encoding="utf-8")
    monkeypatch.setattr(appearance, "STEAM_DESKTOP", system)
    paths = appearance.Paths(tmp_path)
    gaming.set_enabled(paths.data, True, gaming.NVIDIA_OFFLOAD, system)
    assert gaming.is_enabled(paths.data)
    appearance.set_steam_autostart(paths, True)
    autostart = (paths.autostart / "steam.desktop").read_text(encoding="utf-8")
    assert "Exec=env __NV_PRIME_RENDER_OFFLOAD=1" in autostart and "-silent" in autostart
    gaming.set_enabled(paths.data, False, None, system)
    assert not gaming.override_path(paths.data).exists()


def test_never_overwrites_a_user_file(tmp_path: Path) -> None:
    system = tmp_path / "steam.desktop"
    system.write_text(STEAM_ENTRY, encoding="utf-8")
    user_file = gaming.override_path(tmp_path)
    user_file.parent.mkdir(parents=True)
    user_file.write_text("[Desktop Entry]\nName=My Steam\nExec=steam -bigpicture\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        gaming.set_enabled(tmp_path, True, gaming.NVIDIA_OFFLOAD, system)
    gaming.set_enabled(tmp_path, False, None, system)  # disabling leaves someone else's file alone
    assert user_file.exists()


def test_enable_without_hybrid_setup_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no hybrid"):
        gaming.set_enabled(tmp_path, True, None)
