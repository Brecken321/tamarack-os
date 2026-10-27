#!/usr/bin/env python3
"""Tiny QEMU Machine Protocol client for headless VM tests (stdlib only).

Usage:
  qmp.py SOCKET screenshot FILE.png      save the VM screen
  qmp.py SOCKET type TEXT                type text on the VM keyboard
  qmp.py SOCKET key KEY [KEY...]         press keys together (e.g. ctrl alt t, ret)
"""

from __future__ import annotations

import json
import socket
import sys
import time
from typing import Any

# QEMU "qcode" names for characters we may type (lowercase, digits, a few symbols).
_CHARS = {c: c for c in "abcdefghijklmnopqrstuvwxyz0123456789"}
_CHARS.update({" ": "spc", "-": "minus", ".": "dot", "/": "slash", "\n": "ret", "_": "shift-minus"})


class Qmp:
    def __init__(self, path: str) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(60)  # a stuck QEMU must not hang the test
        self.sock.connect(path)
        self.file = self.sock.makefile("rw", encoding="utf-8")
        self._read()  # greeting
        self.command("qmp_capabilities")

    def _read(self) -> dict[str, Any]:
        while True:
            line = self.file.readline()
            if not line:
                raise ConnectionError("QMP connection closed")
            message: dict[str, Any] = json.loads(line)
            if "event" not in message:
                return message

    def command(self, name: str, **arguments: Any) -> Any:
        payload: dict[str, Any] = {"execute": name}
        if arguments:
            payload["arguments"] = arguments
        self.file.write(json.dumps(payload) + "\n")
        self.file.flush()
        reply = self._read()
        if "error" in reply:
            raise RuntimeError(f"{name}: {reply['error']}")
        return reply.get("return")

    def keys(self, *qcodes: str) -> None:
        events = [{"type": "qcode", "data": code} for code in qcodes]
        self.command("send-key", keys=events, **{"hold-time": 60})
        time.sleep(0.08)

    def type(self, text: str) -> None:
        for char in text:
            code = _CHARS.get(char.lower())
            if code is None:
                raise ValueError(f"cannot type {char!r}")
            if code.startswith("shift-"):
                self.keys("shift", code.removeprefix("shift-"))
            elif char.isupper():
                self.keys("shift", code)
            else:
                self.keys(code)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    qmp = Qmp(argv[1])
    action = argv[2]
    if action == "screenshot":
        qmp.command("screendump", filename=argv[3], format="png")
    elif action == "type":
        qmp.type(" ".join(argv[3:]))
    elif action == "key":
        qmp.keys(*argv[3:])
    else:
        print(f"unknown action {action}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
