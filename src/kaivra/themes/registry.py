"""Theme registry."""

from kaivra.themes.base import ThemeSpec
from kaivra.themes.whiteboard import WHITEBOARD
from kaivra.themes.modern import MODERN

_THEMES: dict[str, ThemeSpec] = {
    "whiteboard": WHITEBOARD,
    "modern": MODERN,
}


def get_theme(name: str) -> ThemeSpec:
    """Get a theme by name."""
    theme = _THEMES.get(name)
    if theme is None:
        available = ", ".join(_THEMES.keys())
        raise ValueError(f"Unknown theme: {name!r}. Available: {available}")
    return theme


def register_theme(theme: ThemeSpec) -> None:
    """Register a custom theme."""
    _THEMES[theme.name] = theme
