"""OS update status, history, rollback and restart control.

Tamarack OS is an image-based (bootc/ostree) system. An update downloads a
complete new OS version next to the current one; it takes effect at the next
restart and the previous version stays available for rollback. Personal
files in /home and system settings in /etc are kept across updates and
rollbacks; rollback does not undo changes to personal files.

Nothing here restarts the computer unless the user explicitly asks.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .system import CommandResult, Runner

log = logging.getLogger("tamarack.updates")

# Below this much free space on /var an update may fail to download.
LOW_SPACE_BYTES = 10 * 1024**3

LIVE_MESSAGE = (
    "You are trying Tamarack OS from the live USB, which does not update. Updates start once Tamarack OS is installed."
)


def live_session(root: Path = Path("/")) -> bool:
    """True when running from the live USB (its medium is mounted here at boot)."""
    return (root / "run/initramfs/live").is_dir()


@dataclass(frozen=True)
class Deployment:
    role: str  # "booted", "staged" or "rollback"
    version: str
    image: str
    timestamp: int
    pinned: bool
    digest: str

    @property
    def date(self) -> str:
        if not self.timestamp:
            return ""
        return dt.datetime.fromtimestamp(self.timestamp, tz=dt.UTC).strftime("%Y-%m-%d")


@dataclass
class UpdateStatus:
    booted: Deployment | None = None
    staged: Deployment | None = None
    rollback: Deployment | None = None
    auto_updates: bool | None = None
    free_bytes: int | None = None
    transaction: str | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def restart_needed(self) -> bool:
        return self.staged is not None

    @property
    def low_space(self) -> bool:
        return self.free_bytes is not None and self.free_bytes < LOW_SPACE_BYTES

    def to_dict(self) -> dict[str, Any]:
        def dep(d: Deployment | None) -> dict[str, Any] | None:
            return None if d is None else {**asdict(d), "date": d.date}

        return {
            "booted": dep(self.booted),
            "staged": dep(self.staged),
            "rollback": dep(self.rollback),
            "auto_updates": self.auto_updates,
            "free_bytes": self.free_bytes,
            "low_space": self.low_space,
            "restart_needed": self.restart_needed,
            "transaction": self.transaction,
            "errors": self.errors,
        }


_TRANSPORT_PREFIXES = (
    "ostree-unverified-registry:",
    "ostree-unverified-image:",
    "ostree-image-signed:",
    "ostree-remote-image:",
    "ostree-remote-registry:",
    "docker://",
    "registry:",
)


def _image_ref(raw: dict[str, Any]) -> str:
    """Image name without ostree/containers transport prefixes, e.g. ghcr.io/org/img:stable."""
    ref = str(raw.get("container-image-reference") or raw.get("origin") or "")
    if "docker://" in ref:
        return ref.split("docker://", 1)[1]
    for prefix in _TRANSPORT_PREFIXES:
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def _os_release_version(root: Path) -> str:
    try:
        for line in (root / "usr/lib/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("IMAGE_VERSION="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def parse_rpm_ostree_status(text: str) -> UpdateStatus:
    """Parse ``rpm-ostree status --json``."""
    data = json.loads(text)
    status = UpdateStatus()
    txn = data.get("transaction")
    if txn:
        status.transaction = " ".join(str(x) for x in txn) if isinstance(txn, list) else str(txn)
    for raw in data.get("deployments", []):
        role = "booted" if raw.get("booted") else "staged" if raw.get("staged") else "rollback"
        deployment = Deployment(
            role=role,
            version=str(raw.get("version") or ""),
            image=_image_ref(raw),
            timestamp=int(raw.get("timestamp") or 0),
            pinned=bool(raw.get("pinned")),
            digest=str(raw.get("container-image-reference-digest") or raw.get("checksum") or "")[:71],
        )
        if role == "booted":
            status.booted = deployment
        elif role == "staged":
            status.staged = deployment
        elif status.rollback is None:
            # Only the newest non-booted deployment is the rollback target.
            status.rollback = deployment
    return status


def status(runner: Runner, var_path: Path = Path("/var"), root: Path = Path("/")) -> UpdateStatus:
    if live_session(root):
        return UpdateStatus(errors=[LIVE_MESSAGE])
    result = runner.run(["rpm-ostree", "status", "--json"], timeout=60)
    if result.ok:
        try:
            st = parse_rpm_ostree_status(result.stdout)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            st = UpdateStatus(errors=[f"Could not read update status: {exc}"])
        # Images without a version label report none; the running system knows its own.
        if st.booted is not None and not st.booted.version:
            st.booted = dataclasses.replace(st.booted, version=_os_release_version(root))
    else:
        st = UpdateStatus(errors=[result.error_summary() or "rpm-ostree status failed"])
    timer = runner.run(["systemctl", "is-enabled", "uupd.timer"])
    st.auto_updates = timer.stdout.strip() == "enabled" if timer.stdout.strip() else None
    try:
        st.free_bytes = shutil.disk_usage(var_path).free
    except OSError:
        st.free_bytes = None
    return st


def parse_journal_runs(text: str) -> list[dict[str, str]]:
    """Summarize ``journalctl -u uupd.service -o json`` into update runs."""
    runs: list[dict[str, str]] = []
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = str(entry.get("MESSAGE", ""))
        usec = int(entry.get("__REALTIME_TIMESTAMP", "0") or 0)
        when = dt.datetime.fromtimestamp(usec / 1e6, tz=dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
        lowered = message.lower()
        if message.startswith("Finished") or "deactivated successfully" in lowered:
            runs.append({"time": when, "result": "success", "message": message})
        elif message.startswith("Failed") or "failed with result" in lowered:
            runs.append({"time": when, "result": "failed", "message": message})
    return runs[-50:]


def history(runner: Runner) -> list[dict[str, str]]:
    result = runner.run(
        ["journalctl", "--unit=uupd.service", "--output=json", "--since=-90 days", "--no-pager"], timeout=30
    )
    return parse_journal_runs(result.stdout) if result.ok else []


# --- Actions (each asks for authorization through polkit) ---------------------


def update_now(runner: Runner) -> CommandResult:
    """Start the same update service the timer uses (OS + Flatpak + containers)."""
    if runner.run(["systemctl", "cat", "uupd.service"]).ok:
        return runner.run(["pkexec", "systemctl", "start", "--no-block", "uupd.service"], timeout=120)
    return runner.run(["pkexec", "bootc", "upgrade"], timeout=3600)


def set_auto_updates(runner: Runner, enabled: bool) -> CommandResult:
    verb = "enable" if enabled else "disable"
    return runner.run(["pkexec", "systemctl", verb, "--now", "uupd.timer"], timeout=120)


def rollback(runner: Runner) -> CommandResult:
    """Make the previous OS version the default for the next boot. Does not restart."""
    return runner.run(["pkexec", "bootc", "rollback"], timeout=600)


def pin_current(runner: Runner) -> CommandResult:
    """Keep the booted version forever (it will not be garbage-collected by updates)."""
    return runner.run(["pkexec", "ostree", "admin", "pin", "booted"], timeout=120)


def restart(runner: Runner) -> CommandResult:
    """Restart now. Only ever called after the user confirms in the UI/CLI."""
    return runner.run(["systemctl", "reboot"], timeout=30)
