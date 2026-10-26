"""Product identity, loaded from branding/brand.toml (build) or brand.json (runtime)."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .colors import RGB

RUNTIME_BRAND_JSON = Path("/usr/share/tamarack/brand.json")
_OS_ID_RE = re.compile(r"^[a-z0-9._-]+$")


@dataclass(frozen=True)
class Brand:
    name: str
    short_name: str
    id: str
    reverse_dns: str
    tagline: str
    vendor: str
    home_url: str
    documentation_url: str
    support_url: str
    bug_report_url: str
    based_on: str
    default_hostname: str
    registry: str
    image_main: str
    image_nvidia: str
    default_tag: str
    palette: dict[str, str]
    wallpapers: tuple[str, ...]
    wallpaper_sizes: tuple[tuple[int, int], ...]
    art_seed: int

    def color(self, key: str) -> RGB:
        return RGB.parse(self.palette[key])

    @property
    def logo_icon(self) -> str:
        return f"{self.id}-logo"

    @property
    def center_app_id(self) -> str:
        return f"{self.reverse_dns}.Center"

    def to_json(self) -> str:
        data = asdict(self)
        data["wallpapers"] = list(self.wallpapers)
        data["wallpaper_sizes"] = [f"{w}x{h}" for w, h in self.wallpaper_sizes]
        return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{3,5})x(\d{3,5})", value)
    if not match:
        raise ValueError(f"bad wallpaper size {value!r}, expected WIDTHxHEIGHT")
    return int(match.group(1)), int(match.group(2))


def _require(table: dict[str, Any], key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}.{key} must be a non-empty string")
    return value


def brand_from_mapping(data: dict[str, Any]) -> Brand:
    product = data.get("product", {})
    image = data.get("image", {})
    palette = data.get("palette", {})
    art = data.get("art", {})
    os_id = _require(product, "id", "product")
    if not _OS_ID_RE.match(os_id):
        raise ValueError("product.id must match [a-z0-9._-]+ (os-release ID rules)")
    if not isinstance(palette, dict) or not palette:
        raise ValueError("[palette] table is required")
    for key, value in palette.items():
        RGB.parse(value)  # raises with the offending value
        if not isinstance(key, str):
            raise ValueError("palette keys must be strings")
    for required in (
        "accent",
        "amber",
        "dark_window",
        "dark_view",
        "dark_text",
        "light_window",
        "light_view",
        "light_text",
    ):
        if required not in palette:
            raise ValueError(f"palette.{required} is required")
    wallpapers = art.get("wallpapers")
    if not isinstance(wallpapers, list) or not wallpapers or not all(isinstance(w, str) for w in wallpapers):
        raise ValueError("art.wallpapers must be a non-empty list of names")
    sizes = art.get("sizes")
    if not isinstance(sizes, list) or not sizes:
        raise ValueError("art.sizes must be a non-empty list")
    seed = art.get("seed", 0)
    if not isinstance(seed, int):
        raise ValueError("art.seed must be an integer")
    return Brand(
        name=_require(product, "name", "product"),
        short_name=_require(product, "short_name", "product"),
        id=os_id,
        reverse_dns=_require(product, "reverse_dns", "product"),
        tagline=_require(product, "tagline", "product"),
        vendor=_require(product, "vendor", "product"),
        home_url=_require(product, "home_url", "product"),
        documentation_url=_require(product, "documentation_url", "product"),
        support_url=_require(product, "support_url", "product"),
        bug_report_url=_require(product, "bug_report_url", "product"),
        based_on=_require(product, "based_on", "product"),
        default_hostname=_require(product, "default_hostname", "product"),
        registry=_require(image, "registry", "image"),
        image_main=_require(image, "main", "image"),
        image_nvidia=_require(image, "nvidia", "image"),
        default_tag=_require(image, "default_tag", "image"),
        palette=dict(palette),
        wallpapers=tuple(wallpapers),
        wallpaper_sizes=tuple(_parse_size(s) for s in sizes),
        art_seed=seed,
    )


def load_brand_toml(path: Path) -> Brand:
    with path.open("rb") as fh:
        return brand_from_mapping(tomllib.load(fh))


def load_runtime_brand(path: Path = RUNTIME_BRAND_JSON) -> Brand:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Brand(
        **{
            **data,
            "wallpapers": tuple(data["wallpapers"]),
            "wallpaper_sizes": tuple(_parse_size(s) for s in data["wallpaper_sizes"]),
        }
    )
