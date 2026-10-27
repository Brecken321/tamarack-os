from pathlib import Path

import pytest

from tamarack import privacy
from tamarack.system import FakeRunner

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "system_files/usr/share/tamarack/privacy/catalog.toml"

SS = """\
tcp   LISTEN 0      4096         127.0.0.1:631        0.0.0.0:*    users:(("cupsd",pid=1200,fd=7))
tcp   LISTEN 0      128            0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=900,fd=3))
udp   UNCONN 0      0                 [::]:5353          [::]:*    users:(("avahi-daemon",pid=800,fd=14))
tcp   LISTEN 0      4096             [::1]:631           [::]:*
"""

FIREFOX_PERMS = """\
[Context]
shared=network;ipc;
sockets=x11;wayland;pulseaudio;fallback-x11;
devices=dri;
filesystems=xdg-download;/run/.heim_org.h5l.kcm-socket;
"""

OBS_PERMS = """\
[Context]
shared=network;ipc;
sockets=x11;wayland;pulseaudio;
devices=all;
filesystems=host;
"""

PERMISSION_STORE = """\
devices	camera	org.mozilla.firefox	yes	0x00
location	location	org.gnome.Maps	yes	0x00
background	background	com.discordapp.Discord	yes	0x00
devices	camera	org.example.Denied	no	0x00
"""


def test_parse_ss_and_loopback() -> None:
    listeners = privacy.parse_ss(SS)
    assert [(x.protocol, x.address, x.port, x.process) for x in listeners] == [
        ("tcp", "127.0.0.1", "631", "cupsd"),
        ("tcp", "0.0.0.0", "22", "sshd"),
        ("udp", "::", "5353", "avahi-daemon"),
        ("tcp", "::1", "631", ""),
    ]
    exposed = [x.process for x in listeners if not privacy.is_loopback(x.address)]
    assert exposed == ["sshd", "avahi-daemon"]


def test_flatpak_permissions() -> None:
    store = privacy.parse_permission_store(PERMISSION_STORE)
    assert store["org.mozilla.firefox"] == {"camera"}
    assert "org.example.Denied" not in store
    firefox = privacy.parse_flatpak_permissions("org.mozilla.firefox", FIREFOX_PERMS, store)
    assert firefox.camera and firefox.microphone and firefox.network and not firefox.location
    assert firefox.files.startswith("Some folders")
    obs = privacy.parse_flatpak_permissions("com.obsproject.Studio", OBS_PERMS, store)
    assert obs.camera and obs.files == "All files on the system"
    sandboxed = privacy.parse_flatpak_permissions("org.kde.kcalc", "[Context]\nsockets=wayland;\n", store)
    assert not (sandboxed.camera or sandboxed.microphone or sandboxed.network)
    assert sandboxed.files == "Only files you choose"


def test_autostart_user_overrides_system(tmp_path: Path) -> None:
    system = tmp_path / "etc/xdg/autostart"
    user = tmp_path / "home/.config/autostart"
    system.mkdir(parents=True)
    user.mkdir(parents=True)
    (system / "a.desktop").write_text("[Desktop Entry]\nName=Alpha\n", encoding="utf-8")
    (system / "gnome-only.desktop").write_text("[Desktop Entry]\nName=Gnomey\nOnlyShowIn=GNOME;\n", encoding="utf-8")
    (user / "a.desktop").write_text("[Desktop Entry]\nName=Alpha\nHidden=true\n", encoding="utf-8")
    (user / "steam.desktop").write_text("[Desktop Entry]\nName=Steam\nExec=steam -silent\n", encoding="utf-8")
    entries = privacy.autostart_entries(tmp_path / "home", system)
    assert [(e.name, e.scope, e.enabled) for e in entries] == [("Alpha", "user", False), ("Steam", "user", True)]


def test_service_inventory_uses_catalog() -> None:
    runner = FakeRunner()
    runner.add(
        ["systemctl", "list-unit-files"],
        "firewalld.service enabled enabled\nuupd.timer enabled enabled\nmystery.service enabled disabled\n",
    )
    services = privacy.service_inventory(runner, privacy.load_catalog(CATALOG))
    by_unit = {s.unit: s for s in services}
    assert by_unit["firewalld.service"].known and by_unit["firewalld.service"].safe_to_disable is False
    assert by_unit["uupd.timer"].network is True
    assert not by_unit["mystery.service"].known


def test_catalog_entries_are_complete() -> None:
    catalog = privacy.load_catalog(CATALOG)
    ids = [n["id"] for n in catalog["network"]]
    assert len(ids) == len(set(ids))
    for entry in catalog["network"]:
        assert {"name", "who", "what", "why", "optional"} <= entry.keys(), entry
    for service in catalog["service"]:
        assert {"unit", "name", "purpose", "network", "safe_to_disable"} <= service.keys(), service


@pytest.mark.parametrize(
    ("name", "enabled", "expected"),
    [
        ("countme", True, ["pkexec", "systemctl", "enable", "--now", "rpm-ostree-countme.timer"]),
        ("countme", False, ["pkexec", "systemctl", "disable", "--now", "rpm-ostree-countme.timer"]),
        (
            "store_search",
            False,
            [
                "kwriteconfig6",
                "--file",
                "krunnerrc",
                "--group",
                "Plugins",
                "--key",
                "bazaarrunnerEnabled",
                "--notify",
                "false",
            ],
        ),
        (
            "recent_files",
            False,
            [
                "kwriteconfig6",
                "--file",
                "kactivitymanagerd-pluginsrc",
                "--group",
                "Plugin-org.kde.ActivityManager.Resources.Scoring",
                "--key",
                "what-to-remember",
                "--notify",
                "2",
            ],
        ),
    ],
)
def test_set_toggle_commands(name: str, enabled: bool, expected: list[str]) -> None:
    runner = FakeRunner()
    runner.add([expected[0]])
    privacy.set_toggle(runner, name, enabled)
    assert list(runner.calls[-1]) == expected


def test_unknown_toggle_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown privacy toggle"):
        privacy.set_toggle(FakeRunner(), "telemetry-everything", True)


def test_collect_tolerates_missing_tools(tmp_path: Path) -> None:
    report = privacy.collect(FakeRunner(), tmp_path, CATALOG)
    data = report.to_dict()
    assert data["toggles"]["countme"] is None  # unknown, not guessed
    assert data["network_catalog"]
    assert data["services"] == [] and data["apps"] == []


def test_flatpak_apps_use_display_names() -> None:
    runner = FakeRunner()
    runner.add(["flatpak", "list"], "org.mozilla.firefox\tFirefox\ncom.obsproject.Studio\tOBS Studio\n")
    runner.add(["flatpak", "permissions"], "")
    runner.add(["flatpak", "info", "--show-permissions", "org.mozilla.firefox"], FIREFOX_PERMS)
    runner.add(["flatpak", "info", "--show-permissions", "com.obsproject.Studio"], OBS_PERMS)
    found = privacy.flatpak_apps(runner)
    # Sorted by name, as people see them.
    assert [(a.name, a.app_id) for a in found] == [
        ("Firefox", "org.mozilla.firefox"),
        ("OBS Studio", "com.obsproject.Studio"),
    ]
    assert found[0].network
