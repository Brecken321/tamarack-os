"""Color parsing and WCAG contrast math used by the theme generator and tests."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class RGB:
    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for channel in (self.r, self.g, self.b):
            if not 0 <= channel <= 255:
                raise ValueError(f"color channel out of range: {channel}")

    @classmethod
    def parse(cls, value: str) -> RGB:
        """Parse ``#RRGGBB`` (leading ``#`` optional)."""
        match = _HEX_RE.match(value.strip())
        if not match:
            raise ValueError(f"not a #RRGGBB color: {value!r}")
        raw = match.group(1)
        return cls(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))

    @property
    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def kde(self) -> str:
        """KDE color-scheme notation: ``r,g,b``."""
        return f"{self.r},{self.g},{self.b}"

    def mix(self, other: RGB, amount: float) -> RGB:
        """Linear blend towards ``other``; ``amount`` 0 keeps self, 1 gives other."""
        if not 0.0 <= amount <= 1.0:
            raise ValueError("amount must be within [0, 1]")
        return RGB(
            round(self.r + (other.r - self.r) * amount),
            round(self.g + (other.g - self.g) * amount),
            round(self.b + (other.b - self.b) * amount),
        )

    def relative_luminance(self) -> float:
        """WCAG 2.x relative luminance."""

        def channel(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(self.r) + 0.7152 * channel(self.g) + 0.0722 * channel(self.b)


WHITE = RGB(255, 255, 255)
BLACK = RGB(0, 0, 0)


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio between two colors (1.0 - 21.0)."""
    la, lb = a.relative_luminance(), b.relative_luminance()
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def best_text_on(background: RGB) -> RGB:
    """Return white or black, whichever is more legible on ``background``."""
    return WHITE if contrast_ratio(WHITE, background) >= contrast_ratio(BLACK, background) else BLACK
