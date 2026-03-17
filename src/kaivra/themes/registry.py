"""Theme registry."""

import json
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from kaivra.themes.base import ThemeSpec
from kaivra.themes.modern import MODERN
from kaivra.themes.whiteboard import WHITEBOARD

_THEMES: dict[str, ThemeSpec] = {
    "whiteboard": WHITEBOARD,
    "modern": MODERN,
}


def get_theme(name: str, *, search_roots: Iterable[str | Path] | None = None) -> ThemeSpec:
    """Get a theme by name."""
    theme = _THEMES.get(name)
    if theme is None:
        theme = _load_named_theme(name, search_roots=search_roots)
    if theme is None:
        available = ", ".join(_THEMES.keys())
        raise ValueError(f"Unknown theme: {name!r}. Available: {available}")
    return theme


def register_theme(theme: ThemeSpec) -> None:
    """Register a custom theme."""
    _THEMES[theme.name] = theme


def load_theme_file(path: str | Path) -> ThemeSpec:
    """Load a theme from a JSON file and register it."""
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Theme files must be JSON objects.")

    theme = theme_from_dict(raw)
    register_theme(theme)
    return theme


def write_theme_file(theme: ThemeSpec, path: str | Path) -> Path:
    """Write a theme JSON file to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(theme.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def theme_from_dict(raw: dict) -> ThemeSpec:
    """Construct a ThemeSpec from JSON-like data."""
    valid_fields = {field.name for field in fields(ThemeSpec)}
    unknown = sorted(set(raw) - valid_fields)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown theme field(s): {joined}")
    try:
        return ThemeSpec(**raw)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc


def list_theme_names() -> list[str]:
    """Return the currently registered theme names."""
    return sorted(_THEMES)


def theme_field_names() -> list[str]:
    """Return the supported JSON field names for a theme file."""
    return sorted(field.name for field in fields(ThemeSpec))


def _load_named_theme(name: str, *, search_roots: Iterable[str | Path] | None = None) -> ThemeSpec | None:
    for candidate in _theme_candidates(name, search_roots=search_roots):
        if not candidate.exists():
            continue
        return load_theme_file(candidate)
    return None


def _theme_candidates(name: str, *, search_roots: Iterable[str | Path] | None = None) -> list[Path]:
    roots = [Path.cwd() / "themes"]
    if search_roots is not None:
        roots.extend(Path(root) for root in search_roots)

    candidates: list[Path] = []
    for root in roots:
        if root.suffix == ".json":
            candidates.append(root)
        else:
            candidates.append(root / f"{name}.json")
    return candidates
