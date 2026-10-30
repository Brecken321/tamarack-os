"""Running system commands: one injectable entry point with timeouts and logging.

All Tamarack code that talks to the OS (kwriteconfig6, flatpak, systemctl,
rpm-ostree, lspci, ...) goes through a :class:`Runner`, so tests can replace
it with :class:`FakeRunner` and the UI can run commands off the main thread.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger("tamarack.system")

# Exit codes used for failures that happen before/around the process itself,
# matching the shell conventions people already know.
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def error_summary(self) -> str:
        """Short human-readable reason for a failure (last stderr line)."""
        if self.ok:
            return ""
        lines = [line for line in self.stderr.strip().splitlines() if line.strip()]
        detail = lines[-1] if lines else f"exit code {self.returncode}"
        return f"{self.argv[0]}: {detail}"


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...

    def which(self, name: str) -> bool: ...


class SubprocessRunner:
    """Runs real commands. Never uses a shell; arguments are passed verbatim."""

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        args = tuple(argv)
        merged_env = None if env is None else {**os.environ, **env}
        start = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=merged_env,
                check=False,
            )
        except FileNotFoundError:
            result = CommandResult(args, EXIT_NOT_FOUND, "", f"command not found: {args[0]}")
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, str) else ""
            result = CommandResult(args, EXIT_TIMEOUT, out, f"timed out after {timeout:.0f}s")
        else:
            result = CommandResult(args, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start)
        level = logging.DEBUG if result.ok else logging.WARNING
        log.log(
            level,
            "command finished",
            extra={"argv": list(args), "returncode": result.returncode, "duration": round(result.duration, 3)},
        )
        return result

    def which(self, name: str) -> bool:
        return shutil.which(name) is not None


Handler = Callable[[tuple[str, ...]], CommandResult]


@dataclass
class FakeRunner:
    """Test double: maps an argv prefix to canned output and records calls."""

    responses: dict[tuple[str, ...], CommandResult | Handler] = field(default_factory=dict)
    available: set[str] = field(default_factory=set)
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def add(self, prefix: Sequence[str], stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        key = tuple(prefix)
        self.responses[key] = CommandResult(key, returncode, stdout, stderr)
        self.available.add(key[0])

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        args = tuple(argv)
        self.calls.append(args)
        best: tuple[str, ...] | None = None
        for prefix in self.responses:
            if args[: len(prefix)] == prefix and (best is None or len(prefix) > len(best)):
                best = prefix
        if best is None:
            return CommandResult(args, EXIT_NOT_FOUND, "", f"command not found: {args[0]}")
        response = self.responses[best]
        if callable(response):
            return response(args)
        return CommandResult(args, response.returncode, response.stdout, response.stderr)

    def which(self, name: str) -> bool:
        return name in self.available


# --- KDE settings ---------------------------------------------------------------


def kwriteconfig_argv(file: str, groups: Sequence[str], key: str, value: str | None, notify: bool = True) -> list[str]:
    """``kwriteconfig6`` writing KEY (value None deletes it)."""
    args = ["kwriteconfig6", "--file", file]
    for group in groups:
        args += ["--group", group]
    args += ["--key", key]
    if notify:
        args.append("--notify")
    args += ["--delete"] if value is None else [value]
    return args


def kconfig_notice_argv(file: str, groups: Sequence[str], key: str) -> list[str]:
    """``busctl`` sending KConfig's change notice for KEY, which running KDE
    apps (KConfigWatcher) re-read their settings on: ``ConfigChanged`` with
    {group: [key]} on the path "/" + file name (other than letters, digits
    and "_" as "_"); nested groups are joined with "\x1d"."""
    path = "/" + re.sub(r"[^A-Za-z0-9_]", "_", file)
    name = key.encode()
    return [
        "busctl", "--user", "emit", path, "org.kde.kconfig.notify", "ConfigChanged", "a{saay}",
        "1", "\x1d".join(groups), "1", str(len(name)), *(str(b) for b in name),
    ]  # fmt: skip


def write_kde_config(runner: Runner, file: str, groups: Sequence[str], key: str, value: str | None) -> CommandResult:
    """Write (value None: delete) a KDE setting and tell running apps.

    kwriteconfig6 --notify sends the change notice and exits without waiting
    for it to leave, so it is sometimes lost: in the VM test Plasma kept Do
    Not Disturb on after Game Mode removed it. busctl sends it again and waits;
    a second notice only makes an app re-read its settings once more.
    """
    result = runner.run(kwriteconfig_argv(file, groups, key, value))
    if result.ok:
        runner.run(kconfig_notice_argv(file, groups, key))  # best effort: the setting is written
    return result
