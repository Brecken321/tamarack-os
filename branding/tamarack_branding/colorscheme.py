"""Generate KDE ``.colors`` schemes from the brand palette.

The file format follows KDE's color scheme layout (see Breeze's
BreezeDark.colors); every value is computed from brand.toml and the
results are checked against WCAG contrast targets in the test suite.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tamarack.brand import Brand
from tamarack.colors import BLACK, RGB, WHITE, best_text_on, contrast_ratio

# Foreground roles every color set must define, in KDE's key order.
_FG_KEYS = (
    "ForegroundActive",
    "ForegroundInactive",
    "ForegroundLink",
    "ForegroundNegative",
    "ForegroundNeutral",
    "ForegroundNormal",
    "ForegroundPositive",
    "ForegroundVisited",
)

# Same effect settings Breeze uses: disabled widgets fade, inactive windows
# keep their colors.
_COLOR_EFFECTS = """\
[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0
"""


@dataclass(frozen=True)
class ColorSet:
    background: RGB
    background_alt: RGB
    foreground: RGB
    foreground_inactive: RGB
    active: RGB
    link: RGB
    visited: RGB
    negative: RGB
    neutral: RGB
    positive: RGB
    focus: RGB
    hover: RGB

    def render(self, section: str) -> str:
        fg = {
            "ForegroundActive": self.active,
            "ForegroundInactive": self.foreground_inactive,
            "ForegroundLink": self.link,
            "ForegroundNegative": self.negative,
            "ForegroundNeutral": self.neutral,
            "ForegroundNormal": self.foreground,
            "ForegroundPositive": self.positive,
            "ForegroundVisited": self.visited,
        }
        lines = [
            f"[{section}]",
            f"BackgroundAlternate={self.background_alt.kde}",
            f"BackgroundNormal={self.background.kde}",
            f"DecorationFocus={self.focus.kde}",
            f"DecorationHover={self.hover.kde}",
        ]
        lines += [f"{key}={fg[key].kde}" for key in _FG_KEYS]
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Scheme:
    file_name: str
    display_name: str
    window: ColorSet
    view: ColorSet
    button: ColorSet
    header: ColorSet
    header_inactive: ColorSet
    selection: ColorSet
    tooltip: ColorSet
    complementary: ColorSet
    wm_active_bg: RGB
    wm_active_fg: RGB
    wm_inactive_bg: RGB
    wm_inactive_fg: RGB
    frame_contrast: int

    def render(self) -> str:
        sections = [
            "# Generated from branding/brand.toml by tamarack_branding. Do not edit.",
            "# SPDX-License-Identifier: Apache-2.0",
            "",
            _COLOR_EFFECTS,
            self.button.render("Colors:Button"),
            self.complementary.render("Colors:Complementary"),
            self.header.render("Colors:Header"),
            self.header_inactive.render("Colors:Header][Inactive"),
            self.selection.render("Colors:Selection"),
            self.tooltip.render("Colors:Tooltip"),
            self.view.render("Colors:View"),
            self.window.render("Colors:Window"),
            "[General]",
            f"ColorScheme={self.file_name}",
            f"Name={self.display_name}",
            "shadeSortColumn=true",
            "",
            "[KDE]",
            f"contrast={self.frame_contrast}",
            "",
            "[WM]",
            f"activeBackground={self.wm_active_bg.kde}",
            f"activeBlend={self.wm_active_fg.kde}",
            f"activeForeground={self.wm_active_fg.kde}",
            f"inactiveBackground={self.wm_inactive_bg.kde}",
            f"inactiveBlend={self.wm_inactive_fg.kde}",
            f"inactiveForeground={self.wm_inactive_fg.kde}",
        ]
        return "\n".join(sections) + "\n"


def ensure_contrast(color: RGB, against: RGB | Sequence[RGB], minimum: float, towards: RGB) -> RGB:
    """Blend ``color`` towards ``towards`` until it reaches ``minimum`` contrast on every background."""
    backgrounds = [against] if isinstance(against, RGB) else list(against)
    for step in range(0, 101):
        candidate = color.mix(towards, step / 100)
        if all(contrast_ratio(candidate, bg) >= minimum for bg in backgrounds):
            return candidate
    raise ValueError(f"cannot reach contrast {minimum} for {color.hex} on {[b.hex for b in backgrounds]}")


def selection_background(accent: RGB) -> RGB:
    """Accent adjusted so white (or black) selection text reaches WCAG AA (4.5:1)."""
    text = best_text_on(accent)
    if contrast_ratio(text, accent) >= 4.5:
        return accent
    towards = BLACK if text == WHITE else WHITE
    return ensure_contrast(accent, text, 4.5, towards)


def _semantic(brand: Brand, against: RGB | Sequence[RGB], towards: RGB) -> dict[str, RGB]:
    return {
        name: ensure_contrast(brand.color(name), against, 4.5, towards)
        for name in ("link", "visited", "negative", "neutral", "positive")
    }


def _set(bg: RGB, alt: RGB, fg: RGB, muted: RGB, active: RGB, sem: dict[str, RGB], focus: RGB) -> ColorSet:
    return ColorSet(
        background=bg,
        background_alt=alt,
        foreground=fg,
        foreground_inactive=muted,
        active=active,
        link=sem["link"],
        visited=sem["visited"],
        negative=sem["negative"],
        neutral=sem["neutral"],
        positive=sem["positive"],
        focus=focus,
        hover=focus,
    )


def _scheme(brand: Brand, dark: bool) -> Scheme:
    prefix = "dark" if dark else "light"
    window = brand.color(f"{prefix}_window")
    view = brand.color(f"{prefix}_view")
    alt = brand.color(f"{prefix}_alt")
    header = brand.color(f"{prefix}_header")
    text = brand.color(f"{prefix}_text")
    muted = brand.color(f"{prefix}_text_muted")
    accent = brand.color("accent")
    towards = WHITE if dark else BLACK
    button_bg = window.mix(towards, 0.06)
    # Text colors appear on every one of these backgrounds.
    backgrounds = [window, view, alt, header, button_bg, view.mix(alt, 0.5)]
    sem = _semantic(brand, backgrounds, towards)
    active = ensure_contrast(accent, backgrounds, 4.5, towards)
    focus = ensure_contrast(accent, [window, view, button_bg], 3.0, towards)
    sel_bg = selection_background(accent)
    sel_fg = best_text_on(sel_bg)
    sel_sem = {k: best_text_on(sel_bg) for k in sem}

    def std(bg: RGB, bg_alt: RGB) -> ColorSet:
        return _set(bg, bg_alt, text, muted, active, sem, focus)

    return Scheme(
        file_name=f"{brand.short_name}{'Dark' if dark else 'Light'}",
        display_name=f"{brand.short_name} {'Dark' if dark else 'Light'}",
        window=std(window, alt),
        view=std(view, view.mix(alt, 0.5)),
        button=std(button_bg, sel_bg.mix(window, 0.55)),
        header=std(header, window),
        header_inactive=std(window, header),
        selection=ColorSet(
            background=sel_bg,
            background_alt=sel_bg.mix(window, 0.55),
            foreground=sel_fg,
            foreground_inactive=sel_fg.mix(sel_bg, 0.25),
            active=sel_fg,
            link=sel_sem["link"],
            visited=sel_sem["visited"],
            negative=sel_sem["negative"],
            neutral=sel_sem["neutral"],
            positive=sel_sem["positive"],
            focus=focus,
            hover=focus,
        ),
        tooltip=std(alt, window),
        complementary=_set(
            brand.color("dark_window"),
            brand.color("dark_alt"),
            brand.color("dark_text"),
            brand.color("dark_text_muted"),
            ensure_contrast(accent, brand.color("dark_window"), 4.5, WHITE),
            _semantic(brand, brand.color("dark_window"), WHITE),
            ensure_contrast(accent, brand.color("dark_window"), 3.0, WHITE),
        ),
        wm_active_bg=header,
        wm_active_fg=text,
        wm_inactive_bg=window,
        wm_inactive_fg=muted,
        frame_contrast=4,
    )


def high_contrast_scheme(brand: Brand) -> Scheme:
    """Black/white/yellow scheme targeting WCAG AAA (7:1) for all text."""
    black, white = RGB(0, 0, 0), RGB(255, 255, 255)
    yellow = RGB(255, 214, 0)
    alt = RGB(26, 26, 26)
    sem = {
        "link": RGB(127, 212, 255),
        "visited": RGB(214, 170, 255),
        "negative": RGB(255, 128, 128),
        "neutral": RGB(255, 190, 92),
        "positive": RGB(110, 255, 150),
    }

    def hc(bg: RGB, bg_alt: RGB) -> ColorSet:
        return _set(bg, bg_alt, white, RGB(224, 224, 224), yellow, sem, yellow)

    return Scheme(
        file_name=f"{brand.short_name}HighContrast",
        display_name=f"{brand.short_name} High Contrast",
        window=hc(black, alt),
        view=hc(black, alt),
        button=hc(black, alt),
        header=hc(black, alt),
        header_inactive=hc(black, alt),
        selection=ColorSet(
            background=yellow,
            background_alt=RGB(128, 107, 0),
            foreground=black,
            foreground_inactive=black,
            active=black,
            link=black,
            visited=black,
            negative=black,
            neutral=black,
            positive=black,
            focus=white,
            hover=white,
        ),
        tooltip=hc(black, alt),
        complementary=hc(black, alt),
        wm_active_bg=black,
        wm_active_fg=white,
        wm_inactive_bg=alt,
        wm_inactive_fg=RGB(224, 224, 224),
        frame_contrast=10,
    )


def all_schemes(brand: Brand) -> list[Scheme]:
    return [_scheme(brand, dark=False), _scheme(brand, dark=True), high_contrast_scheme(brand)]
