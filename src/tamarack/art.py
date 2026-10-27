"""Procedural SVG artwork: wallpapers, logo, boot wordmark and previews.

All randomness comes from a seeded ``random.Random`` so a rebuild produces
byte-identical SVGs. SVGs are rasterized later by ``rsvg-convert``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape

from tamarack.brand import Brand
from tamarack.colors import RGB
from tamarack.presets import Preset

Point = tuple[float, float]


@dataclass(frozen=True)
class SceneStyle:
    sky_top: str
    sky_horizon: str
    glow: str
    glow_opacity: float
    sun_x: float  # fraction of width
    sun_y: float  # fraction of height
    sun_radius: float  # fraction of height
    sun_color: str
    ridges: tuple[str, ...]  # back to front
    mist: str
    mist_opacity: float
    stars: int
    tree_density: float


# Two variants (light, dark) per wallpaper. Colors are hand-tuned around the
# brand palette; the front ridge always uses a deep forest green.
_SCENES: dict[str, dict[str, SceneStyle]] = {
    "Tamarack-Ridge": {
        "light": SceneStyle(
            "#8EC3D3",
            "#F6DDAE",
            "#FFE9B8",
            0.85,
            0.70,
            0.40,
            0.06,
            "#FFF4D6",
            ("#9DB9B5", "#7FA39A", "#5E8A78", "#3F6E57", "#24513C", "#143627"),
            "#F4F1E6",
            0.35,
            0,
            1.0,
        ),
        "dark": SceneStyle(
            "#0B141C",
            "#273A3E",
            "#9FB7B2",
            0.22,
            0.72,
            0.24,
            0.035,
            "#F3E7C9",
            ("#2C3F44", "#24363A", "#1C2D30", "#152427", "#0F1B1D", "#091214"),
            "#4C6C70",
            0.22,
            220,
            1.0,
        ),
    },
    "Tamarack-Dusk": {
        "light": SceneStyle(
            "#5B6E9A",
            "#F2A65A",
            "#FFC27A",
            0.9,
            0.36,
            0.58,
            0.11,
            "#FFD9A0",
            ("#B78A78", "#94706A", "#6E5859", "#4B4148", "#2E2C35", "#1A1C22"),
            "#F7C99B",
            0.30,
            0,
            0.8,
        ),
        "dark": SceneStyle(
            "#140F22",
            "#5A3348",
            "#E3A33B",
            0.45,
            0.36,
            0.60,
            0.09,
            "#F0B36A",
            ("#3D2A3B", "#322434", "#271E2C", "#1D1823", "#14121A", "#0C0B10"),
            "#7A4B5C",
            0.20,
            160,
            0.8,
        ),
    },
    "Tamarack-Mist": {
        "light": SceneStyle(
            "#C9D6D3",
            "#EEF0E8",
            "#FFFFFF",
            0.6,
            0.25,
            0.40,
            0.06,
            "#FFFFFF",
            ("#C2CEC9", "#AABBB4", "#8FA79C", "#6F8F80", "#4F7262", "#335445"),
            "#FFFFFF",
            0.55,
            0,
            0.7,
        ),
        "dark": SceneStyle(
            "#121A1D",
            "#2E3B3E",
            "#9CB5B0",
            0.18,
            0.25,
            0.40,
            0.04,
            "#DCE6E3",
            ("#33423F", "#2B3936", "#23302E", "#1B2725", "#141E1C", "#0D1513"),
            "#7F9994",
            0.30,
            90,
            0.7,
        ),
    },
}


def scene_names() -> list[str]:
    return list(_SCENES)


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _smooth_path(points: Sequence[Point]) -> str:
    """Catmull-Rom spline through ``points`` as SVG cubic Bezier commands."""
    if len(points) < 2:
        raise ValueError("need at least two points")
    parts = [f"M{_fmt(points[0][0])},{_fmt(points[0][1])}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        parts.append(f"C{_fmt(c1[0])},{_fmt(c1[1])} {_fmt(c2[0])},{_fmt(c2[1])} {_fmt(p2[0])},{_fmt(p2[1])}")
    return " ".join(parts)


def _ridge_function(rng: random.Random, base: float, amplitude: float) -> Callable[[float], float]:
    """A smooth, seeded mountain profile: y(x) for x in [0, 1] (screen units)."""
    waves = [
        (rng.uniform(1.2, 2.2), rng.uniform(0, math.tau), 0.55),
        (rng.uniform(3.0, 5.5), rng.uniform(0, math.tau), 0.30),
        (rng.uniform(8.0, 13.0), rng.uniform(0, math.tau), 0.15),
    ]

    def y(x: float) -> float:
        return base - amplitude * sum(w * math.sin(f * math.tau * x + p) for f, p, w in waves)

    return y


def _tree_path(x: float, ground: float, height: float, rng: random.Random) -> str:
    """Conifer silhouette: thin trunk plus drooping tiers narrowing upwards."""
    tiers = rng.randint(6, 9)
    width = height * rng.uniform(0.22, 0.30)
    path = [
        f"M{_fmt(x - height * 0.012)},{_fmt(ground)}h{_fmt(height * 0.024)}v{_fmt(-height * 0.25)}"
        f"h{_fmt(-height * 0.024)}z"
    ]
    top = ground - height
    for i in range(tiers):
        t = i / tiers
        tier_y = ground - height * 0.15 - (height * 0.85) * t
        half = width * (1 - t) * rng.uniform(0.85, 1.1) + height * 0.02
        tier_h = height * 0.85 / tiers * 1.9
        droop = tier_h * 0.18
        path.append(
            f"M{_fmt(x - half)},{_fmt(tier_y + droop)}"
            f"Q{_fmt(x - half * 0.4)},{_fmt(tier_y - tier_h * 0.25)} {_fmt(x)},{_fmt(max(tier_y - tier_h, top))}"
            f"Q{_fmt(x + half * 0.4)},{_fmt(tier_y - tier_h * 0.25)} {_fmt(x + half)},{_fmt(tier_y + droop)}z"
        )
    return "".join(path)


def scene_svg_body(name: str, variant: str, width: int, height: int, seed: int) -> str:
    """The landscape as SVG elements (no <svg> wrapper), for reuse in previews."""
    style = _SCENES[name][variant]
    # Seed by wallpaper name (not variant) so light and dark share terrain.
    rng = random.Random(f"{seed}:{name}")
    w, h = float(width), float(height)
    uid = f"{name}-{variant}-{width}x{height}".replace(" ", "")
    out: list[str] = [
        "<defs>",
        f'<linearGradient id="sky-{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{style.sky_top}"/>'
        f'<stop offset="0.62" stop-color="{style.sky_horizon}"/></linearGradient>',
        f'<radialGradient id="glow-{uid}" cx="{style.sun_x}" cy="{style.sun_y}" r="0.55" '
        f'gradientTransform="translate({style.sun_x},{style.sun_y}) scale({h / w},1) '
        f'translate({-style.sun_x},{-style.sun_y})">'
        f'<stop offset="0" stop-color="{style.glow}" stop-opacity="{style.glow_opacity}"/>'
        f'<stop offset="1" stop-color="{style.glow}" stop-opacity="0"/></radialGradient>',
        f'<linearGradient id="mist-{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{style.mist}" stop-opacity="0"/>'
        f'<stop offset="0.6" stop-color="{style.mist}" stop-opacity="{style.mist_opacity}"/>'
        f'<stop offset="1" stop-color="{style.mist}" stop-opacity="0"/></linearGradient>',
        f'<filter id="grain-{uid}" x="0" y="0" width="100%" height="100%">'
        f'<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="{seed % 997}"/>'
        f'<feColorMatrix type="saturate" values="0"/>'
        f'<feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer></filter>',
        "</defs>",
        f'<rect width="{_fmt(w)}" height="{_fmt(h)}" fill="url(#sky-{uid})"/>',
        f'<rect width="{_fmt(w)}" height="{_fmt(h)}" fill="url(#glow-{uid})"/>',
    ]
    star_rng = random.Random(f"{seed}:{name}:stars")
    for _ in range(style.stars):
        sx, sy = star_rng.uniform(0, w), star_rng.uniform(0, h * 0.42) ** 1.15 / (h * 0.42) ** 0.15
        r = star_rng.uniform(0.4, 1.4) * h / 1080
        out.append(
            f'<circle cx="{_fmt(sx)}" cy="{_fmt(sy)}" r="{r:.2f}" fill="#FFFFFF" '
            f'opacity="{star_rng.uniform(0.25, 0.9):.2f}"/>'
        )
    out.append(
        f'<circle cx="{_fmt(style.sun_x * w)}" cy="{_fmt(style.sun_y * h)}" '
        f'r="{_fmt(style.sun_radius * h)}" fill="{style.sun_color}" opacity="0.92"/>'
    )

    layers = len(style.ridges)
    samples = 96
    for i, color in enumerate(style.ridges):
        depth = i / (layers - 1)
        base = h * (0.50 + 0.085 * i)
        amplitude = h * (0.035 + 0.02 * depth)
        ridge = _ridge_function(rng, base, amplitude)
        pts = [(w * k / samples, ridge(k / samples)) for k in range(samples + 1)]
        path = _smooth_path(pts) + f" L{_fmt(w)},{_fmt(h)} L0,{_fmt(h)} Z"
        out.append(f'<path d="{path}" fill="{color}"/>')
        if i >= layers - 3 and style.tree_density > 0:
            tree_rng = random.Random(f"{seed}:{name}:trees:{i}")
            count = int((w / h) * (10 + 14 * depth) * style.tree_density)
            trees = []
            for _ in range(count):
                tx = tree_rng.uniform(-0.02, 1.02)
                # Cluster trees: skip some gaps to keep the skyline readable.
                if math.sin(tx * 17 + i) < -0.35:
                    continue
                th = h * tree_rng.uniform(0.035, 0.07) * (0.6 + depth)
                trees.append((tx * w, ridge(tx) + th * 0.12, th))
            trees.sort(key=lambda t: t[1])
            if trees:
                d = "".join(_tree_path(x, g, th, tree_rng) for x, g, th in trees)
                out.append(f'<path d="{d}" fill="{color}"/>')
        if i < layers - 1:
            out.append(
                f'<rect y="{_fmt(base - amplitude * 1.6)}" width="{_fmt(w)}" '
                f'height="{_fmt(amplitude * 3.2)}" fill="url(#mist-{uid})"/>'
            )
    out.append(f'<rect width="{_fmt(w)}" height="{_fmt(h)}" filter="url(#grain-{uid})"/>')
    return "\n".join(out)


def _wrap(body: str, width: int, height: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n{body}\n</svg>\n'
    )


def wallpaper_svg(name: str, variant: str, width: int, height: int, seed: int) -> str:
    return _wrap(scene_svg_body(name, variant, width, height, seed), width, height)


# The band of a 1920x1080 scene used for banners: the ridges and treeline.
BANNER_BAND = (420, 480)


def banner_svg(name: str, variant: str, seed: int) -> str:
    """A wide crop of a wallpaper scene, used as artwork behind page banners."""
    top, height = BANNER_BAND
    body = scene_svg_body(name, variant, 1920, 1080, seed)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="{height}" '
        f'viewBox="0 {top} 1920 {height}">\n{body}\n</svg>\n'
    )


# --- Logo -----------------------------------------------------------------

_TIERS = ((46.0, 34.0, 34.0), (84.0, 50.0, 44.0), (124.0, 66.0, 54.0))  # apex y, half-width, height


def _logo_tree(stroke: str, top_stroke: str, width: float) -> str:
    parts = [
        f'<path d="M128,66 L128,212" stroke="{stroke}" stroke-width="{width * 0.8:.0f}" '
        'stroke-linecap="round" fill="none"/>'
    ]
    for index, (apex, half, tier_h) in enumerate(_TIERS):
        color = top_stroke if index == 0 else stroke
        parts.append(
            f'<path d="M{128 - half},{apex + tier_h} L128,{apex} L{128 + half},{apex + tier_h}" '
            f'stroke="{color}" stroke-width="{width:.0f}" stroke-linecap="round" '
            'stroke-linejoin="round" fill="none"/>'
        )
    return "\n".join(parts)


def logo_svg(brand: Brand) -> str:
    """Full-color app/OS logo on a 256 grid."""
    accent = brand.color("accent")
    light = accent.mix(RGB(255, 255, 255), 0.18).hex
    dark = accent.mix(RGB(0, 0, 0), 0.30).hex
    body = (
        '<defs><linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/>'
        "</linearGradient></defs>\n"
        '<circle cx="128" cy="128" r="122" fill="url(#lg)"/>\n' + _logo_tree("#FFFFFF", brand.palette["amber"], 20)
    )
    return _wrap(body, 256, 256)


def logo_mono_svg(color: str = "#FFFFFF") -> str:
    """Single-color tree mark for dark backgrounds (boot splash, symbolic uses)."""
    return _wrap(_logo_tree(color, color, 20), 256, 256)


def wordmark_svg(brand: Brand, color: str = "#FFFFFF") -> str:
    """Logo mark plus product name, used as the boot (Plymouth) watermark."""
    width, height = 560, 128
    mark = _logo_tree(color, brand.palette["amber"], 20)
    body = (
        f'<g transform="translate(0,0) scale(0.5)">{mark}</g>\n'
        f'<text x="148" y="82" font-family="Noto Sans, sans-serif" font-size="56" font-weight="600" '
        f'letter-spacing="1" fill="{color}">{escape(brand.name)}</text>'
    )
    return _wrap(body, width, height)


# --- Previews ---------------------------------------------------------------


@dataclass(frozen=True)
class PreviewColors:
    window: str
    header: str
    view: str
    text: str
    accent: str
    panel: str
    panel_fg: str
    variant: str  # wallpaper variant


def preview_colors(brand: Brand, mode: str) -> PreviewColors:
    if mode == "high-contrast":
        return PreviewColors("#000000", "#000000", "#000000", "#FFFFFF", "#FFD600", "#000000", "#FFFFFF", "dark")
    dark = mode == "dark"
    p = "dark" if dark else "light"
    return PreviewColors(
        window=brand.palette[f"{p}_window"],
        header=brand.palette[f"{p}_header"],
        view=brand.palette[f"{p}_view"],
        text=brand.palette[f"{p}_text"],
        accent=brand.palette["accent"],
        panel=brand.palette[f"{p}_window"],
        panel_fg=brand.palette[f"{p}_text"],
        variant=p,
    )


def preview_svg(brand: Brand, preset: Preset, width: int = 480, height: int = 270, mode: str | None = None) -> str:
    """A miniature desktop showing the preset's panel, a window and colors."""
    mode = mode or preset.appearance.mode
    colors = preview_colors(brand, mode)
    s = height / 270  # layout designed at 480x270
    body = [scene_svg_body(preset.appearance.wallpaper, colors.variant, width, height, brand.art_seed)]
    panel = preset.panel
    thick = panel.thickness * 0.42 * s
    margin = (6 * s) if panel.floating else 0.0
    horizontal = panel.location in ("top", "bottom")
    items = len(panel.widgets) + max(len(panel.pins) - 1, 0)
    length_full = (width if horizontal else height) - 2 * margin
    length = min(length_full, items * thick * 1.15 + thick) if panel.length_mode == "fit" else length_full
    start = margin + {"left": 0.0, "center": (length_full - length) / 2, "right": length_full - length}[panel.alignment]
    if horizontal:
        py = margin if panel.location == "top" else height - margin - thick
        rect = (start, py, length, thick)
    else:
        px = margin if panel.location == "left" else width - margin - thick
        rect = (px, start, thick, length)
    radius = 5 * s if panel.floating else 0.0
    panel_opacity = 0.97 if panel.opacity == "opaque" else 0.88

    # Window mock, kept clear of the panel.
    wx, wy, ww, wh = 0.22 * width, 0.16 * height, 0.56 * width, 0.56 * height
    if panel.location == "left":
        wx += thick
    body.append(
        f'<rect x="{wx:.1f}" y="{wy:.1f}" width="{ww:.1f}" height="{wh:.1f}" rx="{4 * s:.1f}" '
        f'fill="{colors.view}" stroke="{colors.header}" stroke-width="{s:.1f}"/>'
        f'<rect x="{wx:.1f}" y="{wy:.1f}" width="{ww:.1f}" height="{16 * s:.1f}" rx="{4 * s:.1f}" '
        f'fill="{colors.header}"/>'
        f'<rect x="{wx + 10 * s:.1f}" y="{wy + 28 * s:.1f}" width="{ww * 0.5:.1f}" height="{6 * s:.1f}" '
        f'rx="{3 * s:.1f}" fill="{colors.text}" opacity="0.75"/>'
        f'<rect x="{wx + 10 * s:.1f}" y="{wy + 42 * s:.1f}" width="{ww * 0.7:.1f}" height="{5 * s:.1f}" '
        f'rx="{2.5 * s:.1f}" fill="{colors.text}" opacity="0.45"/>'
        f'<rect x="{wx + 10 * s:.1f}" y="{wy + wh - 26 * s:.1f}" width="{40 * s:.1f}" height="{14 * s:.1f}" '
        f'rx="{3 * s:.1f}" fill="{colors.accent}"/>'
    )
    body.append(
        f'<rect x="{rect[0]:.1f}" y="{rect[1]:.1f}" width="{rect[2]:.1f}" height="{rect[3]:.1f}" '
        f'rx="{radius:.1f}" fill="{colors.panel}" opacity="{panel_opacity}"/>'
    )
    # Panel contents along the main axis.
    icon = thick * 0.62
    pos = (rect[0] if horizontal else rect[1]) + thick * 0.25
    end = (rect[0] + rect[2] if horizontal else rect[1] + rect[3]) - thick * 0.25
    cross = (rect[1] if horizontal else rect[0]) + (thick - icon) / 2

    def place(at: float, shape: str) -> None:
        x, y = (at, cross) if horizontal else (cross, at)
        if shape == "launcher":
            body.append(
                f'<circle cx="{x + icon / 2:.1f}" cy="{y + icon / 2:.1f}" r="{icon / 2:.1f}" fill="{colors.accent}"/>'
            )
        elif shape == "app":
            body.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{icon:.1f}" height="{icon:.1f}" rx="{icon * 0.25:.1f}" '
                f'fill="{colors.panel_fg}" opacity="0.55"/>'
            )
        elif shape == "label":
            lw = icon * 2.6 if horizontal else icon
            lh = icon if horizontal else icon * 2.6
            body.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{lw:.1f}" height="{lh:.1f}" rx="{icon * 0.2:.1f}" '
                f'fill="{colors.panel_fg}" opacity="0.35"/>'
            )
        elif shape == "dot":
            body.append(
                f'<circle cx="{x + icon / 2:.1f}" cy="{y + icon / 2:.1f}" r="{icon / 4:.1f}" '
                f'fill="{colors.panel_fg}" opacity="0.7"/>'
            )

    step = icon * 1.25
    tail = [w for w in panel.widgets if w in ("tray", "clock", "showdesktop")]
    head = [w for w in panel.widgets if w not in tail]
    labels = panel.task_manager == "tasks"
    for widget in head:
        if widget == "launcher":
            place(pos, "launcher")
            pos += step
        elif widget == "tasks":
            if "spacer" in head and head.index("spacer") < head.index("tasks"):
                pos = max(
                    pos, (rect[0] + rect[2] / 2 if horizontal else rect[1] + rect[3] / 2) - step * len(panel.pins) / 2
                )
            for _ in panel.pins[:5]:
                place(pos, "label" if labels else "app")
                pos += step * 2.3 if labels and horizontal else step
        elif widget == "pager":
            place(pos, "app")
            pos += step
    at = end - step * len(tail)
    for _ in tail:
        place(at, "dot")
        at += step
    return _wrap("\n".join(body), width, height)
