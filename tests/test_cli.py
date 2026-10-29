import json
from pathlib import Path

import pytest

from tamarack import cli, doctor, games
from tamarack.system import FakeRunner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    load = games.AntiCheatDatabase.load
    monkeypatch.setattr(
        games.AntiCheatDatabase,
        "load",
        classmethod(lambda cls, *a, **k: load(ROOT / "data/awacy/games.json", ROOT / "data/awacy/source.json")),
    )


def test_games_check_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["games", "check", "--json", "Some", "Unknown", "Game", "XYZ"], FakeRunner()) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["category"] == "untested"


def test_games_data(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["games", "data"], FakeRunner()) == 0
    assert "AreWeAntiCheatYet (MIT)" in capsys.readouterr().out


def test_privacy_set_validates_input() -> None:
    with pytest.raises(SystemExit):
        cli.main(["privacy", "--set", "countme=maybe"], FakeRunner())


def test_unknown_toggle_returns_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["privacy", "--set", "nonsense=on"], FakeRunner()) == 1
    assert "unknown privacy toggle" in capsys.readouterr().err


def test_doctor_quick_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["doctor", "--quick", "--json"], FakeRunner()) == 0
    data = json.loads(capsys.readouterr().out)
    assert {"system", "updates", "gaming", "problems"} <= data.keys()


def test_doctor_problems_are_plain_language() -> None:
    data = {
        "updates": {"restart_needed": True, "staged": {"version": "44.20261030"}, "low_space": True, "errors": []},
        "gaming": {"Steam": False, "Lutris (game launcher)": False},
        "hardware": {
            "items": [
                {
                    "category": "Graphics",
                    "name": "NVIDIA GPU",
                    "status": "attention",
                    "advice": "Switch to the NVIDIA edition.",
                }
            ]
        },
        "default_apps": {"state": "retrying", "message": "1 app(s) could not be installed yet."},
    }
    problems = doctor.problems(data)
    assert any("Restart when convenient" in p for p in problems)
    assert any("10 GB" in p for p in problems)
    assert "Steam is missing from this system image." in problems
    assert not any("Lutris" in p for p in problems)  # optional tools are not "problems"
    assert any("Switch to the NVIDIA edition" in p for p in problems)
    assert any("could not be installed" in p for p in problems)


def test_doctor_names_the_version_that_starts_next() -> None:
    problems = doctor.problems({"updates": {"restart_needed": True, "next_boot": {"version": "44.20261020"}}})
    assert "44.20261020 starts at the next restart (instead of the running version)." in problems
    assert not any("update is ready" in p for p in problems)
