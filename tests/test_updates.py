import json
from pathlib import Path

from tamarack import updates
from tamarack.system import FakeRunner

STATUS = {
    "deployments": [
        {
            "staged": True,
            "booted": False,
            "pinned": False,
            "version": "44.20261027",
            "timestamp": 1793088000,
            "container-image-reference": "ostree-image-signed:docker://ghcr.io/brecken321/tamarack-os-nvidia:stable",
            "container-image-reference-digest": "sha256:" + "b" * 64,
        },
        {
            "booted": True,
            "staged": False,
            "pinned": True,
            "version": "44.20261026",
            "timestamp": 1793001600,
            "container-image-reference": "ostree-image-signed:docker://ghcr.io/brecken321/tamarack-os-nvidia:stable",
            "container-image-reference-digest": "sha256:" + "a" * 64,
        },
        {
            "booted": False,
            "version": "44.20261020",
            "timestamp": 1792483200,
            "container-image-reference": "ostree-unverified-registry:ghcr.io/ublue-os/bazzite-nvidia-open:stable",
        },
        {"booted": False, "version": "44.20261001", "timestamp": 1790841600},
    ],
    "transaction": None,
}


def test_parse_status_roles() -> None:
    st = updates.parse_rpm_ostree_status(json.dumps(STATUS))
    assert st.booted and st.booted.version == "44.20261026" and st.booted.pinned
    assert st.booted.image == "ghcr.io/brecken321/tamarack-os-nvidia:stable"
    assert st.booted.date == "2026-10-26"
    assert st.staged and st.staged.version == "44.20261027"
    assert st.rollback and st.rollback.version == "44.20261020"  # newest non-booted only
    assert st.restart_needed
    data = st.to_dict()
    assert data["restart_needed"] and data["rollback"]["date"]


def test_status_with_failures_reports_errors(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.add(["rpm-ostree", "status"], "", returncode=1, stderr="error: Could not connect to rpm-ostreed\n")
    st = updates.status(runner, tmp_path)
    assert st.errors and "Could not connect" in st.errors[0]
    assert st.booted is None and st.auto_updates is None
    assert st.free_bytes is not None


def test_status_auto_updates(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.add(["rpm-ostree", "status"], json.dumps(STATUS))
    runner.add(["systemctl", "is-enabled", "uupd.timer"], "enabled\n")
    st = updates.status(runner, tmp_path)
    assert st.auto_updates is True and not st.errors


def test_low_space_threshold() -> None:
    st = updates.UpdateStatus(free_bytes=5 * 1024**3)
    assert st.low_space
    assert not updates.UpdateStatus(free_bytes=50 * 1024**3).low_space


def test_journal_runs() -> None:
    lines = [
        {
            "MESSAGE": "Starting uupd.service - Universal Blue Update Oneshot Service...",
            "__REALTIME_TIMESTAMP": "1792483200000000",
        },
        {"MESSAGE": "uupd.service: Deactivated successfully.", "__REALTIME_TIMESTAMP": "1792483800000000"},
        {"MESSAGE": "uupd.service: Failed with result 'exit-code'.", "__REALTIME_TIMESTAMP": "1792570200000000"},
    ]
    runs = updates.parse_journal_runs("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
    assert [r["result"] for r in runs] == ["success", "failed"]
    assert runs[0]["time"].startswith("2026-")


def test_actions_use_polkit_and_never_auto_restart() -> None:
    runner = FakeRunner()
    runner.add(["systemctl", "cat", "uupd.service"], "[Unit]\n")
    runner.add(["pkexec"])
    updates.update_now(runner)
    updates.rollback(runner)
    updates.set_auto_updates(runner, False)
    commands = [list(c) for c in runner.calls]
    assert ["pkexec", "systemctl", "start", "--no-block", "uupd.service"] in commands
    assert ["pkexec", "bootc", "rollback"] in commands
    assert ["pkexec", "systemctl", "disable", "--now", "uupd.timer"] in commands
    assert not any("reboot" in c for c in commands)


def test_image_ref_strips_transports() -> None:
    for ref in (
        "ostree-unverified-registry:ghcr.io/brecken321/tamarack-os:stable",
        "ostree-image-signed:docker://ghcr.io/brecken321/tamarack-os:stable",
        "docker://ghcr.io/brecken321/tamarack-os:stable",
    ):
        assert updates._image_ref({"container-image-reference": ref}) == "ghcr.io/brecken321/tamarack-os:stable"


def test_booted_version_falls_back_to_os_release(tmp_path: Path) -> None:
    (tmp_path / "usr/lib").mkdir(parents=True)
    (tmp_path / "usr/lib/os-release").write_text('NAME="Tamarack OS"\nIMAGE_VERSION="44.20261027"\n', encoding="utf-8")
    data = {
        "deployments": [
            {
                "booted": True,
                "timestamp": 1793001600,
                "container-image-reference": "ostree-unverified-registry:ghcr.io/x/y:stable",
            }
        ]
    }
    runner = FakeRunner()
    runner.add(["rpm-ostree", "status"], json.dumps(data))
    st = updates.status(runner, tmp_path, tmp_path)
    assert st.booted is not None and st.booted.version == "44.20261027"
