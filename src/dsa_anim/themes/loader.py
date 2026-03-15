"""Theme resolution helpers for built-in and external themes."""

from __future__ import annotations

from pathlib import Path

from dsa_anim.themes.base import ThemeSpec
from dsa_anim.themes.file_schema import ThemeFileSpec, load_theme_file
from dsa_anim.themes.registry import get_theme


def resolve_theme(theme_name: str, theme_file: str | Path | None = None) -> ThemeSpec:
    """Resolve a theme from either the built-in registry or an external file."""
    if theme_file is not None:
        return load_theme_file(theme_file)
    return get_theme(theme_name)


def theme_schema() -> dict:
    """Return the JSON Schema for external theme files."""
    return ThemeFileSpec.model_json_schema()
