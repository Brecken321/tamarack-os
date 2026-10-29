"""Click every button in Tamarack Center and check that each one does something.

Used by ``tamarack-center --check-buttons`` in CI, with the example data
from demo.py, so nothing is installed, applied or launched for real: apps
and URLs that a button would open are recorded instead.

For every page (and every Welcome step) it clicks each visible, enabled
button, switch and clickable card, and each one inside the dialogs, sheets
and menus those open, and triggers every action (including those only
reachable through "⋮" overflow menus). A control passes when
the click has a visible effect: another page, a dialog or menu, a request
to the system (install, apply, refresh…), an app or link being opened, a
message, its own on/off state changing, or its dialog closing. A control fails when it has no
effect or raises a QML error.
"""

from __future__ import annotations

import functools
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import Q_ARG, QEventLoop, QMetaObject, QObject, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QAccessible, QDesktopServices, QGuiApplication

from . import backend as backend_module

BACKEND_SIGNALS = (
    "notify",
    "busyChanged",
    "doctorChanged",
    "presetsChanged",
    "hardwareChanged",
    "privacyChanged",
    "libraryChanged",
    "gameResultsChanged",
    "bundlesChanged",
    "updatesChanged",
    "welcomeFinished",
    "gpuChanged",
    "searchChanged",
)
# Controls inside Kirigami's own components that only move focus or the
# view (no app behavior to check). Matched against the control's label.
IGNORED = {"Clear search", "Search"}


@dataclass
class Result:
    page: str
    control: str
    effects: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.effects) and not self.errors


class _UrlRecorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.opened: list[str] = []

    @Slot(QUrl)
    def handle(self, url: QUrl) -> None:
        self.opened.append(url.toString())


def settle(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _prop(obj: Any, name: str) -> Any:
    """A QML property, or None when PySide cannot convert its type."""
    try:
        return obj.property(name)
    except (RuntimeError, TypeError):
        return None


def accessible_name(item: Any) -> str:
    """What a screen reader announces for the control ("" if nothing)."""
    try:
        iface = QAccessible.queryAccessibleInterface(item)
    except (RuntimeError, TypeError):
        return ""
    return (iface.text(QAccessible.Text.Name) or "").strip() if iface is not None else ""


def _label(item: Any) -> str:
    name = accessible_name(item)
    if name:
        return name
    for prop in ("text", "title"):
        value = _prop(item, prop)
        if isinstance(value, str) and value.strip():
            return value.strip()
    icon = _prop(item, "icon")
    name = getattr(icon, "name", "") if icon is not None else ""
    return f"{type(item).__name__} ({name or item.metaObject().className()})"


def _popup_of(item: Any) -> Any | None:
    """The dialog, sheet, menu or drawer the control is in (None if none)."""
    parent = item.parentItem()
    while parent is not None:
        if parent.inherits("QQuickPopupItem"):
            return parent
        parent = parent.parentItem()
    return None


class ButtonCheck:
    def __init__(self, window: Any, backend: Any, warnings: list[str], welcome: bool) -> None:
        self.window = window
        self.backend = backend
        self.warnings = warnings
        self.welcome = welcome
        self.signals = 0
        self.launched: list[str] = []
        self.urls = _UrlRecorder()
        for name in BACKEND_SIGNALS:
            getattr(backend, name).connect(self._count)
        for scheme in ("http", "https", "file", "mailto", "steam"):
            QDesktopServices.setUrlHandler(scheme, self.urls, "handle")
        # Apps and System Settings pages a button would start are recorded.
        recorder = self

        class _Popen:
            def __init__(self, argv: list[str], **_kwargs: Any) -> None:
                recorder.launched.append(" ".join(argv))

        backend_module.subprocess = types.SimpleNamespace(Popen=_Popen)  # type: ignore[attr-defined,assignment]

    def _count(self, *_args: Any) -> None:
        self.signals += 1

    # -- the scene ---------------------------------------------------------
    def _items(self, kind: str) -> list[Any]:
        found: list[Any] = []

        def walk(item: Any) -> None:
            for child in item.childItems():
                if not child.isVisible() or child.opacity() == 0:
                    continue
                if child.inherits(kind):
                    found.append(child)
                walk(child)

        walk(self.window.contentItem())
        return found

    def buttons(self) -> list[Any]:
        result = []
        for item in self._items("QQuickAbstractButton"):
            if not item.isEnabled() or item.width() <= 0 or item.height() <= 0:
                continue
            # Cards that only group content are not buttons.
            if _prop(item, "showClickFeedback") is False:
                continue
            if _label(item) in IGNORED:
                continue
            result.append(item)
        return result

    def actions(self) -> list[Any]:
        """The current page's actions, including ones only in overflow menus."""
        page = (
            _prop(_prop(self.window, "pageStack"), "currentItem")
            if _prop(self.window, "pageStack") is not None
            else None
        )
        if page is None:
            return []
        result = []
        for child in [page, *page.findChildren(QObject)]:
            if not child.inherits("QQuickAction"):
                continue
            if _prop(child, "enabled") is False or _prop(child, "visible") is False:
                continue
            if (_prop(child, "text") or "") in IGNORED:
                continue
            if _prop(child, "children"):  # a submenu: its entries are the actions
                continue
            result.append(child)
        return result

    def _state(self) -> dict[str, Any]:
        popups = len(self._items("QQuickPopupItem"))
        windows = sum(1 for w in QGuiApplication.topLevelWindows() if w.isVisible())
        stack = _prop(self.window, "pageStack")
        steps = self.window.findChild(QObject, "welcomeSteps")
        selection = tuple(
            bool(_prop(item, "checked")) for item in self._items("QQuickAbstractButton") if _prop(item, "checkable")
        )
        return {
            "selection": selection,
            "page": self.window.property("currentPage"),
            "loads": self.window.property("pageLoads"),
            "depth": _prop(stack, "depth") if stack is not None else 0,
            "step": steps.property("currentIndex") if steps is not None else -1,
            "popups": popups,
            "windows": windows,
            "signals": self.signals,
            "requests": len(getattr(self.backend, "requests", [])),
            "launched": len(self.launched),
            "urls": len(self.urls.opened),
        }

    def _effects(self, before: dict[str, Any], after: dict[str, Any], checked: tuple[Any, Any]) -> list[str]:
        effects = []
        if after["page"] != before["page"] or after["depth"] != before["depth"]:
            effects.append(f"opens page {after['page']}")
        elif after["loads"] != before["loads"]:
            effects.append("reloads the page")
        if after["step"] != before["step"]:
            effects.append(f"goes to Welcome step {after['step'] + 1}")
        if after["popups"] > before["popups"] or after["windows"] > before["windows"]:
            effects.append("opens a dialog or menu")
        if after["requests"] > before["requests"]:
            effects.append("asks the system: " + ", ".join(self.backend.requests[before["requests"] :]))
        if after["launched"] > before["launched"]:
            effects.append("starts " + ", ".join(self.launched[before["launched"] :]))
        if after["urls"] > before["urls"]:
            effects.append("opens " + ", ".join(self.urls.opened[before["urls"] :]))
        if after["signals"] > before["signals"] and not effects:
            effects.append("updates the page")
        if after["popups"] < before["popups"]:
            effects.append("closes the dialog")
        if checked[0] != checked[1]:
            effects.append("switches " + ("on" if checked[1] else "off"))
        elif after["selection"] != before["selection"] and not effects:
            effects.append("changes a selection")
        return effects

    def _reload(self, page: str) -> None:
        for window in QGuiApplication.topLevelWindows():
            if window is not self.window and window.isVisible():
                window.close()
        QMetaObject.invokeMethod(self.window, "showPage", Q_ARG("QVariant", page))
        settle(700)

    def _press(self, page: str, control: str, act: Callable[[], None], item: Any | None) -> Result:
        result = Result(page, control)
        before = self._state()
        warned = len(self.warnings)
        was = _prop(item, "checked") if item is not None else None
        # Read before clicking: a control that opens another page is gone afterwards.
        named = item is None or bool(accessible_name(item))
        act()
        settle(400)
        now = _prop(item, "checked") if item is not None else None
        if not isinstance(now, bool) or not isinstance(was, bool):
            was = now = None
        result.effects = self._effects(before, self._state(), (was, now))
        result.errors = [
            w
            for w in self.warnings[warned:]
            if any(s in w for s in ("Error", "is not a function", "Cannot read", "undefined", "Unable to assign"))
        ]
        # Screen readers need a name for every control.
        if not named:
            result.errors.append("no accessible name (a screen reader cannot announce it)")
        return result

    def check_page(self, page: str) -> list[Result]:
        results: list[Result] = []
        self._reload(page)
        count = len(self.buttons())
        for index in range(count):
            self._reload(page)
            current = self.buttons()
            if index >= len(current):
                break
            item = current[index]
            if not item.isEnabled():
                continue
            label = _label(item)
            result = self._press(page, label, functools.partial(self._click, item), item)
            results.append(result)
            if "opens a dialog or menu" in result.effects:
                results.extend(self._check_popup(page, index, label))
        self._reload(page)
        names = [_prop(a, "text") or "(action)" for a in self.actions()]
        for index, name in enumerate(names):
            self._reload(page)
            current = self.actions()
            if index >= len(current):
                break
            action = current[index]
            trigger = functools.partial(QMetaObject.invokeMethod, action, "trigger", Qt.ConnectionType.DirectConnection)
            results.append(self._press(page, f"action: {name}", trigger, None))
        return results

    def _opened_by(self, page: str, index: int) -> list[Any]:
        """Reload PAGE, click its button INDEX, and return the controls in the
        dialogs, sheets and menus that opened (not the sidebar, a drawer)."""
        self._reload(page)
        # Held so each popup keeps one Python wrapper, compared by identity.
        already = self._items("QQuickPopupItem")
        self._click(self.buttons()[index])
        settle(400)
        inside = []
        for button in self.buttons():
            popup = _popup_of(button)
            if popup is not None and not any(popup is p for p in already):
                inside.append(button)
        return inside

    def _check_popup(self, page: str, index: int, opener: str) -> list[Result]:
        """Each control in the dialog, sheet or menu that the page's button INDEX opens."""
        results: list[Result] = []
        count = len(self._opened_by(page, index))
        for inner in range(count):
            current = self._opened_by(page, index)
            if inner >= len(current):
                break
            item = current[inner]
            results.append(self._press(page, f"{opener} › {_label(item)}", functools.partial(self._click, item), item))
        return results

    @staticmethod
    def _click(item: Any) -> None:
        # click() presses and releases like a mouse, so checkable controls toggle.
        if item.metaObject().indexOfMethod("click()") >= 0:
            QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)
        else:
            item.clicked.emit()


def run(window: Any, backend: Any, warnings: list[str], welcome: bool, pages: list[str], report: Path) -> int:
    # Qt Quick builds its accessibility tree only while accessibility is on
    # (normally when a screen reader connects).
    QAccessible.setActive(True)
    window.resize(1180, 800)
    window.requestActivate()
    settle(2500)
    check = ButtonCheck(window, backend, warnings, welcome)
    results: list[Result] = []
    for page in ["welcome"] if welcome else pages:
        results.extend(check.check_page(page))
    # Each control once: the same action can be reached from several places.
    lines = ["| Page | Control | Result |", "|---|---|---|"]
    for r in results:
        verdict = "; ".join(r.effects) if r.ok else ("ERROR " + " / ".join(r.errors) if r.errors else "NO EFFECT")
        lines.append(f"| {r.page} | {r.control} | {verdict} |")
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")
    failed = [r for r in results if not r.ok]
    for r in results:
        print(("ok   " if r.ok else "FAIL ") + f"{r.page}: {r.control}: " + ("; ".join(r.effects) or "no effect"))
        for error in r.errors:
            print(f"     {error}")
    print(f"{len(results)} controls checked, {len(failed)} failed")
    return 1 if failed or not results else 0
