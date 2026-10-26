import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from tamarack.brand import Brand, brand_from_mapping, load_runtime_brand
from tamarack.colors import RGB, contrast_ratio
from tamarack_branding.__main__ import main as generate
from tamarack_branding.colorscheme import all_schemes

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("branding")
    assert (
        generate(
            [
                "--brand",
                str(ROOT / "branding/brand.toml"),
                "--presets",
                str(ROOT / "branding/presets"),
                "--out",
                str(target),
                "--no-render",
            ]
        )
        == 0
    )
    return target


def _scheme_values(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("["):
            current = line.strip("[]")
            sections[current] = {}
        elif "=" in line and current:
            key, value = line.split("=", 1)
            sections[current][key] = value
    return sections


def _rgb(value: str) -> RGB:
    r, g, b = (int(x) for x in value.split(","))
    return RGB(r, g, b)


@pytest.mark.parametrize("index,minimum", [(0, 4.5), (1, 4.5), (2, 7.0)])
def test_color_schemes_meet_wcag(brand: Brand, index: int, minimum: float) -> None:
    scheme = all_schemes(brand)[index]
    sections = _scheme_values(scheme.render())
    for name in ("Colors:View", "Colors:Window", "Colors:Button", "Colors:Tooltip"):
        bg = _rgb(sections[name]["BackgroundNormal"])
        fg = _rgb(sections[name]["ForegroundNormal"])
        assert contrast_ratio(fg, bg) >= minimum, (scheme.file_name, name)
        for key in ("ForegroundLink", "ForegroundNegative", "ForegroundPositive", "ForegroundNeutral"):
            assert contrast_ratio(_rgb(sections[name][key]), bg) >= 4.5, (scheme.file_name, name, key)
    selection = sections["Colors:Selection"]
    assert contrast_ratio(_rgb(selection["ForegroundNormal"]), _rgb(selection["BackgroundNormal"])) >= 4.5
    # Focus indicators must be visible against the window (WCAG non-text contrast 3:1).
    window = _rgb(sections["Colors:Window"]["BackgroundNormal"])
    assert contrast_ratio(_rgb(sections["Colors:Window"]["DecorationFocus"]), window) >= 3.0


def test_scheme_file_structure(brand: Brand) -> None:
    text = all_schemes(brand)[1].render()
    for section in (
        "[Colors:View]",
        "[Colors:Window]",
        "[Colors:Selection]",
        "[Colors:Header][Inactive]",
        "[General]",
        "[WM]",
        "[ColorEffects:Disabled]",
    ):
        assert section in text
    assert "ColorScheme=TamarackDark" in text


def test_generator_outputs(out: Path, brand: Brand) -> None:
    share = out / "usr/share"
    assert (share / "tamarack/brand.json").exists()
    for lnf in ("light", "dark", "highcontrast"):
        base = share / f"plasma/look-and-feel/{brand.reverse_dns}.{lnf}.desktop"
        meta = json.loads((base / "metadata.json").read_text(encoding="utf-8"))
        assert meta["KPackageStructure"] == "Plasma/LookAndFeel"
        assert meta["KPlugin"]["Id"] == base.name
        assert (base / "contents/layouts/org.kde.plasma.desktop-layout.js").exists()
        assert f"Theme={base.name}" in (base / "contents/defaults").read_text(encoding="utf-8")
    for name in brand.wallpapers:
        meta = json.loads((share / f"wallpapers/{name}/metadata.json").read_text(encoding="utf-8"))
        assert meta["KPlugin"]["Id"] == name
    assert len(list((share / "tamarack/presets").glob("*.toml"))) == 7
    assert (out / f"etc/xdg/autostart/{brand.reverse_dns}.Welcome.desktop").exists()


def test_generated_svgs_are_well_formed(out: Path) -> None:
    svgs = list(out.rglob("*.svg"))
    assert len(svgs) > 40
    for svg in svgs:
        root = ElementTree.parse(svg).getroot()
        assert root.tag.endswith("svg"), svg


def test_artwork_is_deterministic(tmp_path: Path) -> None:
    def run(target: Path) -> dict[str, bytes]:
        generate(
            [
                "--brand",
                str(ROOT / "branding/brand.toml"),
                "--presets",
                str(ROOT / "branding/presets"),
                "--out",
                str(target),
                "--no-render",
            ]
        )
        return {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*.svg")}

    assert run(tmp_path / "a") == run(tmp_path / "b")


def test_desktop_entries(out: Path, brand: Brand) -> None:
    center = (out / f"usr/share/applications/{brand.center_app_id}.desktop").read_text(encoding="utf-8")
    assert "Exec=tamarack-center\n" in center
    assert f"Name={brand.short_name} Center" in center
    autostart = (out / f"etc/xdg/autostart/{brand.reverse_dns}.Welcome.desktop").read_text(encoding="utf-8")
    assert "--first-run-only" in autostart


def test_branding_env_is_shell_safe(out: Path) -> None:
    env = (out / "usr/share/tamarack/branding.env").read_text(encoding="utf-8")
    assert "BRAND_NAME='Tamarack OS'" in env
    for line in env.splitlines()[1:]:
        assert re.match(r"^BRAND_[A-Z_]+=", line), line


def test_runtime_brand_roundtrip(out: Path, brand: Brand) -> None:
    assert load_runtime_brand(out / "usr/share/tamarack/brand.json") == brand


def test_brand_validation() -> None:
    with pytest.raises(ValueError, match="os-release ID"):
        brand_from_mapping({"product": {"id": "Tamarack OS"}})


def test_layouts_are_valid_javascript(out: Path, node: str) -> None:
    for js in out.rglob("*-layout.js"):
        result = subprocess.run([node, "--check", str(js)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
