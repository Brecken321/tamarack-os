"""Every button, switch, tile and action in Tamarack Center must do something.

A static check of the QML sources: each interactive element needs a handler
(onClicked, onToggled, onTriggered, an `action:`) or must say why it has
none. The preview workflow also clicks every button for real
(`tamarack-center --check-buttons`); this test catches a missing handler
before that, on any machine.
"""

import re
from pathlib import Path

import pytest

QML = Path(__file__).resolve().parents[1] / "src/tamarack/ui/qml"

INTERACTIVE = re.compile(
    r"\b(Controls\.(?:Button|ToolButton|Switch|CheckBox|SwitchDelegate|CheckDelegate|RadioButton|ItemDelegate|"
    r"RoundButton|DelayButton)|PrimaryButton|ActionTile|Kirigami\.Action|Kirigami\.AbstractCard|Kirigami\.Card)"
    r"\s*\{"
)
# Any of these in an element's own properties counts as doing something.
HANDLED = re.compile(
    r"^\s*(on(?:Clicked|Toggled|Triggered|Released|PressAndHold|CheckedChanged)\s*:|action\s*:|"
    r"interactive\s*:\s*false|enabled\s*:\s*false|showClickFeedback\s*:\s*false)",
    re.M,
)
# Components whose root is one of the types above; their uses are checked
# where they are instantiated, not in the component file itself.
COMPONENT_ROOTS = {"ActionTile.qml", "PresetCard.qml", "PrimaryButton.qml", "SectionCard.qml"}


def own_properties(block: str) -> str:
    """The element's own lines: nested elements and JS blocks removed."""
    out, depth = [], 0
    for ch in block:
        if ch == "{":
            depth += 1
            if depth == 1:
                continue
        elif ch == "}":
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


def elements(text: str) -> list[tuple[str, int, str]]:
    found = []
    for match in INTERACTIVE.finditer(text):
        start = match.end() - 1
        depth = 0
        for end in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            if depth == 0:
                break
        found.append((match.group(1), text.count("\n", 0, match.start()) + 1, text[start + 1 : end]))
    return found


def needs_handler(kind: str, body: str) -> bool:
    props = own_properties(body)
    if HANDLED.search(props):
        return False
    if kind == "Kirigami.Action" and "Kirigami.Action" in body:
        return False  # a submenu: its children are the actions
    if kind in ("Kirigami.Card", "Kirigami.AbstractCard", "SectionCard") and "showClickFeedback" not in props:
        return False  # a plain card that only groups content
    # An explicit, reviewed exception: "// no-handler: <reason>".
    return "no-handler:" not in body


QML_FILES = sorted(p for p in QML.rglob("*.qml") if p.name not in COMPONENT_ROOTS)


@pytest.mark.parametrize("path", QML_FILES, ids=lambda p: str(p.relative_to(QML)))
def test_every_interactive_element_has_a_handler(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [f"{kind} at line {line}" for kind, line, body in elements(text) if needs_handler(kind, body)]
    assert not missing, f"{path.name}: no handler for " + ", ".join(missing)


def test_the_check_sees_the_elements() -> None:
    # Guard against the regex silently matching nothing.
    total = sum(len(elements(p.read_text(encoding="utf-8"))) for p in QML_FILES)
    assert total > 60
    assert needs_handler("Controls.Button", 'text: "x"\nicon.name: "y"')
    assert not needs_handler("Controls.Button", 'text: "x"\nonClicked: page.go("a")')
    # A handler in a nested element does not count for its parent.
    assert needs_handler("Controls.Button", 'text: "x"\nItem { MouseArea { onClicked: x() } }')
