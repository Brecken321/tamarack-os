from pathlib import Path

import pytest

from tamarack import steam, vdf

LIBRARY_FOLDERS = """
"libraryfolders"
{
    "0"
    {
        "path"      "{root}"
        "label"     ""
        "apps"      { "228980" "1" "1245620" "1" }
    }
    "1"
    {
        "path"      "{extra}"
    }
}
"""

MANIFEST = """
"AppState"
{{
    "appid"         "{appid}"
    "Universe"      "1"
    "name"          "{name}"
    "StateFlags"    "{flags}"
    "installdir"    "{dir}"
    "SizeOnDisk"    "123456789"
}}
"""

CONFIG = r"""
"InstallConfigStore"
{
    "Software"
    {
        "Valve"
        {
            "Steam"
            {
                // per-game compatibility tool choices
                "CompatToolMapping"
                {
                    "0" { "name" "proton_experimental" "config" "" "priority" "75" }
                    "1245620" { "name" "GE-Proton9-20" "config" "" "priority" "250" }
                }
            }
        }
    }
}
"""


def test_vdf_parses_nested_and_escapes() -> None:
    data = vdf.loads('"a" { "b" "x\\"y" "c" { "d" "1" } } // trailing comment')
    assert data == {"a": {"b": 'x"y', "c": {"d": "1"}}}
    assert vdf.get_dict(data, "A", "C") == {"d": "1"}
    assert vdf.get_dict(data, "a", "missing") == {}


@pytest.mark.parametrize("bad", ['"a" {', '"a" }', '"a" "b" "c"', '"unterminated'])
def test_vdf_rejects_malformed(bad: str) -> None:
    with pytest.raises(vdf.VdfError):
        vdf.loads(bad)


def _make_steam(home: Path) -> Path:
    root = home / ".local/share/Steam"
    extra = home / "Games/SteamLibrary"
    for lib in (root, extra):
        (lib / "steamapps/common").mkdir(parents=True)
    (root / "steamapps/libraryfolders.vdf").write_text(
        LIBRARY_FOLDERS.replace("{root}", root.as_posix()).replace("{extra}", extra.as_posix()), encoding="utf-8"
    )
    apps = [
        (root, "1245620", "ELDEN RING", 4, "ELDEN RING"),
        (root, "1493710", "Proton Experimental", 4, "Proton - Experimental"),
        (extra, "570", "Dota 2", 6, "dota 2 beta"),
    ]
    for lib, appid, name, flags, folder in apps:
        (lib / f"steamapps/appmanifest_{appid}.acf").write_text(
            MANIFEST.format(appid=appid, name=name, flags=flags, dir=folder), encoding="utf-8"
        )
    (root / "steamapps/common/Proton - Experimental").mkdir()
    (root / "compatibilitytools.d/GE-Proton9-20").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "config/config.vdf").write_text(CONFIG, encoding="utf-8")
    return root


def test_scan_finds_libraries_games_and_tools(tmp_path: Path) -> None:
    _make_steam(tmp_path)
    install = steam.scan(tmp_path)
    assert install is not None
    assert len(install.libraries) == 2
    names = {g.name for g in install.games}
    assert names == {"ELDEN RING", "Dota 2"}  # Proton itself is not listed as a game
    elden = next(g for g in install.games if g.appid == "1245620")
    assert elden.compat_tool == "GE-Proton9-20" and elden.installed
    assert install.default_compat_tool == "proton_experimental"
    assert install.proton_versions == ["Proton - Experimental"]
    assert install.custom_tools == ["GE-Proton9-20"]
    data = install.to_dict()
    assert [g["name"] for g in data["games"]] == ["Dota 2", "ELDEN RING"]


def test_no_steam(tmp_path: Path) -> None:
    assert steam.scan(tmp_path) is None


def test_proton_log(tmp_path: Path) -> None:
    assert steam.proton_log(tmp_path, "570") is None
    log = tmp_path / "steam-570.log"
    log.write_text("".join(f"line {i}\n" for i in range(100)), encoding="utf-8")
    assert steam.proton_log(tmp_path, "570") == log
    assert steam.tail(log, 3) == ["line 97\n", "line 98\n", "line 99\n"]
    assert steam.launch_uri("570") == "steam://rungameid/570"
