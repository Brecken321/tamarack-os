"""Game compatibility center: honest, sourced answers to "will this game work?".

Data source: AreWeAntiCheatYet (https://areweanticheatyet.com, MIT licensed),
a curated list of games that use anti-cheat and whether that anti-cheat
works on Linux/Proton. A snapshot ships in the image
(/usr/share/tamarack/games/awacy-games.json) and can be refreshed on demand.

Rules:
* A verdict is only ever derived from data, and always names its source
  and when that source last changed.
* Games not in the dataset are "Not yet tested" by us; we link to
  community resources (ProtonDB, PCGamingWiki) instead of guessing.
* "Verified working" is reserved for Valve's Steam Deck Verified rating,
  which we do not have a licensed data feed for, so it is never assigned
  automatically; the UI links to the Steam store page instead.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("tamarack.games")

SYSTEM_DATASET = Path("/usr/share/tamarack/games/awacy-games.json")
SYSTEM_SOURCE = Path("/usr/share/tamarack/games/awacy-source.json")
DATASET_URL = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    description: str


CATEGORIES: dict[str, Category] = {
    c.id: c
    for c in (
        Category(
            "verified",
            "Verified working",
            "Valve tested the game on Steam Deck/SteamOS. Check the game's Steam store page for this badge.",
        ),
        Category(
            "likely",
            "Likely working",
            "The game's anti-cheat is reported to work on Linux/Proton.",
        ),
        Category(
            "configuration",
            "Requires configuration",
            "Works after a change such as a different Proton version or a launch option.",
        ),
        Category(
            "issues",
            "Known issues",
            "Parts of the game, often online play, may not work yet.",
        ),
        Category(
            "incompatible",
            "Incompatible",
            "Online play is blocked or broken on Linux. Only Windows can run it today.",
        ),
        Category(
            "untested",
            "Not yet tested",
            "We have no data for this game. Most games without anti-cheat run through Proton; check community reports.",
        ),
    )
}


@dataclass(frozen=True)
class AntiCheatEntry:
    name: str
    slug: str
    status: str
    anticheats: tuple[str, ...]
    native: bool
    steam_id: str | None
    notes: tuple[tuple[str, str], ...]
    updates: tuple[tuple[str, str, str], ...]
    date_changed: str
    reference: str

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> AntiCheatEntry:
        name = raw.get("name")
        status = raw.get("status")
        if not isinstance(name, str) or not name or not isinstance(status, str):
            raise ValueError("entry needs a name and status")
        store_ids = raw.get("storeIds") or {}
        steam = store_ids.get("steam") if isinstance(store_ids, dict) else None
        notes = tuple(
            (str(n[0]), str(n[1]) if len(n) > 1 else "") for n in raw.get("notes") or [] if isinstance(n, list) and n
        )
        updates = tuple(
            (str(u.get("name", "")), str(u.get("date", "")), str(u.get("reference", "")))
            for u in raw.get("updates") or []
            if isinstance(u, dict)
        )
        return cls(
            name=name,
            slug=str(raw.get("slug") or ""),
            status=status,
            anticheats=tuple(str(a) for a in raw.get("anticheats") or []),
            native=bool(raw.get("native", False)),
            steam_id=str(steam) if steam else None,
            notes=notes,
            updates=updates,
            date_changed=str(raw.get("dateChanged") or ""),
            reference=str(raw.get("reference") or ""),
        )


@dataclass(frozen=True)
class DatasetInfo:
    name: str
    url: str
    license: str
    commit: str
    commit_date: str
    path: str


@dataclass(frozen=True)
class Verdict:
    game: str
    steam_id: str | None
    category: str
    title: str
    explanation: str
    anticheats: tuple[str, ...] = ()
    native_linux: bool = False
    notes: tuple[tuple[str, str], ...] = ()
    source: str = ""
    source_url: str = ""
    last_changed: str = ""
    links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category_title"] = CATEGORIES[self.category].title
        return data


def normalize(name: str) -> str:
    """Lowercase, strip accents, punctuation and trademark symbols for matching."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[™®©]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


class AntiCheatDatabase:
    def __init__(self, entries: Sequence[AntiCheatEntry], info: DatasetInfo) -> None:
        self.entries = list(entries)
        self.info = info
        self._by_steam = {e.steam_id: e for e in self.entries if e.steam_id}
        self._by_name = {normalize(e.name): e for e in self.entries}

    @classmethod
    def load(cls, dataset: Path = SYSTEM_DATASET, source: Path | None = SYSTEM_SOURCE) -> AntiCheatDatabase:
        raw = json.loads(dataset.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{dataset}: expected a JSON list of games")
        entries = []
        skipped = 0
        for item in raw:
            try:
                entries.append(AntiCheatEntry.from_json(item))
            except (ValueError, TypeError, AttributeError):
                skipped += 1
        if skipped:
            log.warning("skipped malformed anti-cheat entries", extra={"count": skipped})
        meta: dict[str, Any] = {}
        if source is not None and source.exists():
            meta = json.loads(source.read_text(encoding="utf-8"))
        info = DatasetInfo(
            name=str(meta.get("name", "AreWeAntiCheatYet")),
            url=str(meta.get("url", "https://areweanticheatyet.com/")),
            license=str(meta.get("license", "MIT")),
            commit=str(meta.get("commit", "")),
            commit_date=str(meta.get("commit_date", "")),
            path=str(dataset),
        )
        return cls(entries, info)

    def by_steam_id(self, appid: str | int) -> AntiCheatEntry | None:
        return self._by_steam.get(str(appid))

    def search(self, query: str, limit: int = 5) -> list[AntiCheatEntry]:
        """Exact (normalized) name match first, then close matches."""
        key = normalize(query)
        if not key:
            return []
        if query.strip().isdigit():
            hit = self.by_steam_id(query.strip())
            return [hit] if hit else []
        results: list[AntiCheatEntry] = []
        exact = self._by_name.get(key)
        if exact:
            results.append(exact)
        prefix = [e for n, e in self._by_name.items() if n.startswith(key) and e is not exact]
        results.extend(sorted(prefix, key=lambda e: len(e.name))[: limit - len(results)])
        if len(results) < limit:
            close = difflib.get_close_matches(key, list(self._by_name), n=limit, cutoff=0.72)
            for name in close:
                entry = self._by_name[name]
                if entry not in results:
                    results.append(entry)
        return results[:limit]


def community_links(steam_id: str | None, name: str) -> dict[str, str]:
    links: dict[str, str] = {}
    if steam_id:
        links["Steam store (Deck Verified badge)"] = f"https://store.steampowered.com/app/{steam_id}"
        links["ProtonDB community reports"] = f"https://www.protondb.com/app/{steam_id}"
        links["PCGamingWiki"] = f"https://www.pcgamingwiki.com/api/appid.php?appid={steam_id}"
    else:
        from urllib.parse import quote_plus

        links["ProtonDB search"] = f"https://www.protondb.com/search?q={quote_plus(name)}"
    return links


_STATUS_RULES: dict[str, tuple[str, str]] = {
    "Supported": (
        "likely",
        "The developer has enabled {ac} for Linux/Proton, so online play is expected to work.",
    ),
    "Running": (
        "likely",
        "Reported to run with {ac}, but the developer has not officially enabled Linux support. "
        "A future game update could break it.",
    ),
    "Planned": (
        "issues",
        "The developer has said Linux/Proton support for {ac} is planned. Online modes may not work yet.",
    ),
    "Broken": (
        "incompatible",
        "Online play is reported broken on Linux because of {ac}. Offline or single-player modes may still work.",
    ),
    "Denied": (
        "incompatible",
        "The developer blocks Linux/Proton players through {ac}. Tamarack OS cannot work around this, "
        "and bypassing anti-cheat would risk a ban. This game needs Windows for online play.",
    ),
}


def verdict(
    entry: AntiCheatEntry | None, info: DatasetInfo | None, *, name: str = "", steam_id: str | None = None
) -> Verdict:
    if entry is None:
        game = name or (f"Steam app {steam_id}" if steam_id else "Unknown game")
        return Verdict(
            game=game,
            steam_id=steam_id,
            category="untested",
            title=CATEGORIES["untested"].title,
            explanation=(
                "This game is not in the anti-cheat database. That usually means it has no anti-cheat; "
                "most such games run through Proton. Check community reports before buying."
            ),
            source=info.name if info else "",
            source_url=info.url if info else "",
            last_changed=info.commit_date if info else "",
            links=community_links(steam_id, game),
        )
    category, template = _STATUS_RULES.get(
        entry.status,
        ("untested", "The anti-cheat database lists an unrecognized status ({status}); treat this as untested."),
    )
    anticheat = ", ".join(entry.anticheats) or "its anti-cheat"
    explanation = template.format(ac=anticheat, status=entry.status)
    if entry.native:
        explanation += " A native Linux version exists."
    links = community_links(entry.steam_id, entry.name)
    if entry.slug:
        links = {"AreWeAntiCheatYet entry": f"https://areweanticheatyet.com/game/{entry.slug}", **links}
    return Verdict(
        game=entry.name,
        steam_id=entry.steam_id,
        category=category,
        title=CATEGORIES[category].title,
        explanation=explanation,
        anticheats=entry.anticheats,
        native_linux=entry.native,
        notes=entry.notes,
        source=info.name if info else "AreWeAntiCheatYet",
        source_url=info.url if info else "https://areweanticheatyet.com/",
        last_changed=entry.date_changed or (info.commit_date if info else ""),
        links=links,
    )


def check(db: AntiCheatDatabase, query: str) -> list[Verdict]:
    """Verdicts for a name or Steam app id; one "untested" verdict if no match."""
    query = query.strip()
    matches = db.search(query)
    if matches:
        return [verdict(m, db.info) for m in matches]
    steam_id = query if query.isdigit() else None
    return [verdict(None, db.info, name="" if steam_id else query, steam_id=steam_id)]


def summarize(verdicts: Iterable[Verdict]) -> dict[str, int]:
    counts = {cid: 0 for cid in CATEGORIES}
    for v in verdicts:
        counts[v.category] += 1
    return counts
