#!/usr/bin/python3 -I
"""Use Tamarack Center like a person would, on the real system.

Runs inside the VM's desktop session (see run-vm-test.sh):

  center-drive.py [--welcome] [--timeout SECONDS] PAGE STEP [STEP...]

Opens Tamarack Center on PAGE with its real backend, so clicks run the real
commands and change real settings. Waits for the page to load, then runs
each STEP in order:

  click:NAME             click the control NAME, then wait until the work it
                         starts (and the page's refresh after it) is done
  click:NAME@CONTAINER   the control NAME inside CONTAINER (e.g. a preset card)
  expect:NAME=on|off     check that the switch NAME is on or off

Controls are found by their accessible name, which is what a screen reader
announces (the button check requires one on every control). Links a control
opens (steam://, https://) are printed instead of opened. Prints PASS, FAIL
and INFO lines; exits non-zero if a control is missing or disabled, a check
fails, or the app shows an error or a warning.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

sys.path.insert(0, "/usr/lib/tamarack/python")

from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl, Slot
from PySide6.QtGui import QAccessible, QDesktopServices, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from tamarack.system import SubprocessRunner
from tamarack.ui import app as center
from tamarack.ui.backend import Backend
from tamarack.ui.buttoncheck import ButtonCheck, accessible_name, settle

failures = 0


def report(ok: bool, text: str) -> None:
    global failures
    if not ok:
        failures += 1
    print(("PASS: " if ok else "FAIL: ") + text, flush=True)


def info(text: str) -> None:
    print(f"INFO: {text}", flush=True)


class Links(QObject):
    @Slot(QUrl)
    def handle(self, url: QUrl) -> None:
        info(f"opens {url.toString()}")


def items(root: Any) -> list[Any]:
    """Every visible item under root, depth first."""
    found: list[Any] = []

    def walk(item: Any) -> None:
        for child in item.childItems():
            if child.isVisible() and child.opacity() > 0:
                found.append(child)
                walk(child)

    walk(root)
    return found


def find_control(window: Any, name: str) -> Any | None:
    """A visible button or switch named NAME, or NAME@CONTAINER."""
    control, _, container = name.partition("@")
    roots = [window.contentItem()]
    if container:
        roots = [i for i in items(window.contentItem()) if accessible_name(i) == container]
    for root in roots:
        for item in items(root):
            if item.inherits("QQuickAbstractButton") and accessible_name(item) == control:
                return item
    return None


def find_action(window: Any, name: str) -> Any | None:
    """A page action named NAME that is not shown as a button (an overflow menu entry)."""
    stack = window.property("pageStack")
    page = stack.property("currentItem") if stack is not None else None
    if page is None:
        return None
    for child in page.findChildren(QObject):
        if child.inherits("QQuickAction") and child.property("text") == name:
            return child
    return None


def names(window: Any) -> list[str]:
    return sorted(
        {n for i in items(window.contentItem()) if i.inherits("QQuickAbstractButton") and (n := accessible_name(i))}
    )


def state(item: Any) -> str:
    """'on' or 'off' for a switch, '' for a button (or one rebuilt since)."""
    try:
        checked = item.property("checked") if item.property("checkable") else None
    except RuntimeError:  # deleted when the page rebuilt its list
        return ""
    return "" if checked is None else ("on" if checked else "off")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--welcome", action="store_true", help="open the first-run welcome flow")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for each click's work")
    parser.add_argument("page")
    parser.add_argument("steps", nargs="+")
    args = parser.parse_args()

    # The same setup as tamarack-center (tamarack.ui.app.main), with the real backend.
    brand = center._brand()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("tamarack-center")
    app.setApplicationDisplayName(f"{brand.short_name} Center")
    app.setOrganizationName(brand.short_name)
    app.setDesktopFileName(brand.center_app_id)
    app.setWindowIcon(QIcon.fromTheme(brand.center_app_id, QIcon.fromTheme(brand.logo_icon)))
    if not QQuickStyle.name():
        QQuickStyle.setStyle("org.kde.desktop")
        QQuickStyle.setFallbackStyle("Fusion")
    backend = Backend(brand, SubprocessRunner(), welcome=args.welcome)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("initialPage", "welcome" if args.welcome else args.page)
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))

    links = Links()
    for scheme in ("http", "https", "mailto", "steam"):
        QDesktopServices.setUrlHandler(scheme, links, "handle")
    messages: list[tuple[str, str]] = []

    def on_notify(message: str, kind: str) -> None:
        messages.append((kind, message))
        info(f"message ({kind}): {message}")

    backend.notify.connect(on_notify)
    backend.welcomeFinished.connect(lambda: info("Welcome finished"))

    engine.load(QUrl.fromLocalFile(str(center.QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        report(False, "Tamarack Center started: " + "; ".join(warnings))
        return 1
    window = engine.rootObjects()[0]
    QAccessible.setActive(True)
    window.resize(1180, 800)
    window.requestActivate()

    def idle(timeout: float) -> bool:
        """Wait until the app has had no work running for two seconds."""
        deadline = time.monotonic() + timeout
        quiet = 0
        while time.monotonic() < deadline:
            settle(250)
            quiet = 0 if backend.busy else quiet + 1
            if quiet >= 8:
                return True
        return False

    start = time.monotonic()
    report(idle(180), f"{args.page} page loaded ({time.monotonic() - start:.0f} s)")
    for step in args.steps:
        verb, _, target = step.partition(":")
        if verb == "expect":
            name, _, want = target.rpartition("=")
            item = find_control(window, name)
            have = state(item) if item is not None else "missing"
            report(have == want, f'"{name}" shows {want} (it shows {have})')
            continue
        if verb != "click":
            report(False, f"unknown step {step!r}")
            continue
        item = find_control(window, target)
        action = find_action(window, target) if item is None else None
        if item is None and action is None:
            report(False, f'"{target}" is on the page')
            info("controls on the page: " + ", ".join(names(window)))
            continue
        if item is not None and not item.isEnabled():
            report(False, f'"{target}" can be clicked (it is disabled)')
            continue
        before = state(item) if item is not None else ""
        seen = len(messages)
        start = time.monotonic()
        if item is not None:
            ButtonCheck._click(item)
        else:
            QMetaObject.invokeMethod(action, "trigger", Qt.ConnectionType.DirectConnection)
        done = idle(args.timeout)
        after = state(item) if item is not None else ""
        change = f" ({before} -> {after})" if before else ""
        report(done, f'clicked "{target}"{change}, work finished after {time.monotonic() - start:.0f} s')
        bad = [m for kind, m in messages[seen:] if kind in ("error", "warning")]
        report(not bad, f'"{target}" reported no error' + (f": {'; '.join(bad)}" if bad else ""))

    errors = [w for w in warnings if any(s in w for s in ("Error", "is not a function", "Cannot read", "undefined"))]
    report(not errors, "no QML errors" + (": " + "; ".join(errors) if errors else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
