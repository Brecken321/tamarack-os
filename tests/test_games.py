from pathlib import Path

import pytest

from tamarack import games

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db() -> games.AntiCheatDatabase:
    return games.AntiCheatDatabase.load(ROOT / "data/awacy/games.json", ROOT / "data/awacy/source.json")


def test_dataset_loads_with_source_info(db: games.AntiCheatDatabase) -> None:
    assert len(db.entries) > 500
    assert db.info.license == "MIT"
    assert db.info.commit and db.info.commit_date


@pytest.mark.parametrize(
    ("status", "category"),
    [
        ("Supported", "likely"),
        ("Running", "likely"),
        ("Planned", "issues"),
        ("Broken", "incompatible"),
        ("Denied", "incompatible"),
    ],
)
def test_every_status_maps_to_a_category(db: games.AntiCheatDatabase, status: str, category: str) -> None:
    entry = next((e for e in db.entries if e.status == status), None)
    if entry is None:
        pytest.skip(f"no {status} entries in this dataset snapshot")
    verdict = games.verdict(entry, db.info)
    assert verdict.category == category
    assert verdict.source == "AreWeAntiCheatYet"
    assert verdict.explanation
    assert any("areweanticheatyet.com/game/" in url for url in verdict.links.values())


def test_lookup_by_name_and_steam_id(db: games.AntiCheatDatabase) -> None:
    entry = next(e for e in db.entries if e.steam_id)
    assert db.by_steam_id(entry.steam_id) is entry
    assert db.search(entry.name)[0] is entry
    assert db.search(entry.name.upper() + "™")[0] is entry
    assert db.search(entry.steam_id or "") == [entry]


def test_denied_games_explain_windows_is_needed(db: games.AntiCheatDatabase) -> None:
    denied = next(e for e in db.entries if e.status == "Denied")
    verdict = games.verdict(denied, db.info)
    assert "needs Windows" in verdict.explanation
    assert "bypass" in verdict.explanation


def test_unknown_game_is_untested_with_community_links(db: games.AntiCheatDatabase) -> None:
    results = games.check(db, "Definitely Not A Real Game 9000")
    assert len(results) == 1
    assert results[0].category == "untested"
    assert "ProtonDB search" in results[0].links
    by_id = games.check(db, "99999999")
    assert by_id[0].category == "untested"
    assert by_id[0].links["ProtonDB community reports"].endswith("/app/99999999")


def test_verified_is_never_assigned_automatically(db: games.AntiCheatDatabase) -> None:
    verdicts = [games.verdict(e, db.info) for e in db.entries]
    assert all(v.category != "verified" for v in verdicts)
    counts = games.summarize(verdicts)
    assert counts["verified"] == 0 and sum(counts.values()) == len(db.entries)


def test_malformed_entries_are_skipped(tmp_path: Path) -> None:
    data = tmp_path / "games.json"
    data.write_text('[{"name": "Ok", "status": "Supported"}, {"status": "Broken"}, "junk"]', encoding="utf-8")
    db = games.AntiCheatDatabase.load(data, None)
    assert [e.name for e in db.entries] == ["Ok"]


def test_normalize() -> None:
    assert games.normalize("  Tom Clancy's Rainbow Six® Siege ") == "tom clancy s rainbow six siege"
    assert games.normalize("Pokémon & Friends") == "pokemon and friends"
