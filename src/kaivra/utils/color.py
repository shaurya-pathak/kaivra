"""Color utilities."""

from __future__ import annotations


def hex_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    """Convert hex color to RGBA floats (0-1)."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return r / 255, g / 255, b / 255, 1.0
    elif len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        return r / 255, g / 255, b / 255, a / 255
    raise ValueError(f"Invalid hex color: {hex_color!r}")


def rgba_to_cairo(r: float, g: float, b: float, a: float = 1.0) -> tuple[float, float, float, float]:
    """Ensure RGBA values are in 0-1 range for Cairo."""
    return (
        max(0.0, min(1.0, r)),
        max(0.0, min(1.0, g)),
        max(0.0, min(1.0, b)),
        max(0.0, min(1.0, a)),
    )


def lerp_color(
    c1: tuple[float, float, float, float],
    c2: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    """Linearly interpolate between two RGBA colors."""
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))
