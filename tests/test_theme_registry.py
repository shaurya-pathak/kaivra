from __future__ import annotations

import json
from pathlib import Path

from kaivra.themes.modern import MODERN
from kaivra.themes.registry import get_theme, load_theme_file, register_theme


def test_register_theme_accepts_name_and_dict_data() -> None:
    name = "test-name-dict-theme"
    theme = register_theme(
        name,
        {
            **MODERN.to_dict(),
            "accent": "#14b8a6",
        },
    )

    assert theme.name == name
    assert get_theme(name).accent == "#14b8a6"


def test_register_theme_keeps_existing_themespec_signature() -> None:
    name = "test-themespec-theme"
    theme = MODERN.__class__(**{**MODERN.to_dict(), "name": name, "accent": "#ef4444"})

    registered = register_theme(theme)

    assert registered is theme
    assert get_theme(name).accent == "#ef4444"


def test_load_theme_file_registers_theme_from_json(tmp_path: Path) -> None:
    path = tmp_path / "mint.json"
    path.write_text(
        json.dumps(
            {
                **MODERN.to_dict(),
                "name": "test-file-theme",
                "accent": "#22c55e",
            }
        ),
        encoding="utf-8",
    )

    theme = load_theme_file(path)

    assert theme.name == "test-file-theme"
    assert get_theme("test-file-theme").accent == "#22c55e"
