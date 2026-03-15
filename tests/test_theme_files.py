import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dsa_anim.cli import main
from dsa_anim.render.web.exporter import _serialize_theme
from dsa_anim.themes.file_schema import load_theme_file, load_theme_file_raw
from dsa_anim.themes.loader import resolve_theme


ROOT = Path(__file__).resolve().parents[1]
NVIDIA_THEME = ROOT / "examples" / "themes" / "nvidia.json"


def _write_animation(tmp_path: Path) -> Path:
    doc = {
        "version": "1.1",
        "meta": {
            "title": "Theme Smoke",
            "theme": "whiteboard",
            "show_narration": True,
        },
        "scenes": [
            {
                "id": "intro",
                "duration": "2s",
                "show_progress": True,
                "layout": "stack",
                "auto_visible": True,
                "narration": "NVIDIA themed preview smoke test.",
                "objects": [
                    {"type": "text", "id": "title", "content": "GPU Stack", "style": "heading"},
                    {"type": "box", "id": "engine", "content": "TensorRT"},
                    {"type": "token", "id": "precision", "content": "FP8", "token_id": 208},
                ],
            }
        ],
    }
    path = tmp_path / "animation.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _write_theme(tmp_path: Path, raw: dict, name: str = "theme.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_load_theme_file_parses_nvidia_theme():
    theme = load_theme_file(NVIDIA_THEME)

    assert theme.name == "nvidia"
    assert theme.background_color == "#0B0B0B"
    assert theme.resolve_style("code")["font_family"] == "Roboto Mono"
    assert theme.callout_border_color == "#76B900"
    assert theme.progress_bar_color == "#76B900"


def test_theme_file_rejects_missing_required_section(tmp_path: Path):
    raw = load_theme_file_raw(NVIDIA_THEME)
    del raw["chrome"]
    path = _write_theme(tmp_path, raw, "missing_chrome.json")

    with pytest.raises(ValueError) as excinfo:
        load_theme_file(path)

    assert "[chrome]" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)


def test_theme_file_rejects_unknown_field(tmp_path: Path):
    raw = load_theme_file_raw(NVIDIA_THEME)
    raw["palette"]["bogus"] = "#FFFFFF"
    path = _write_theme(tmp_path, raw, "unknown_field.json")

    with pytest.raises(ValueError) as excinfo:
        load_theme_file(path)

    assert "palette -> bogus" in str(excinfo.value)
    assert "Extra inputs are not permitted" in str(excinfo.value)


def test_resolve_theme_falls_back_to_builtin_without_theme_file():
    theme = resolve_theme("modern")

    assert theme.name == "modern"
    assert theme.background_color == "#F7F7FB"


def test_web_theme_serialization_includes_new_chrome_tokens():
    theme = load_theme_file(NVIDIA_THEME)
    serialized = _serialize_theme(theme)

    assert serialized["displayFontCss"].startswith('"NVIDIA Sans"')
    assert serialized["codeFontCss"].startswith('"Roboto Mono"')
    assert serialized["calloutBorderColor"] == "#76B900"
    assert serialized["narrationBackgroundColor"] == "#000000D9"
    assert serialized["progressBarColor"] == "#76B900"
    assert serialized["previewButtonFill"] == "#76B900"


def test_cli_theme_schema_validate_and_override(tmp_path: Path):
    animation = _write_animation(tmp_path)
    runner = CliRunner()

    schema_result = runner.invoke(main, ["theme-schema"])
    assert schema_result.exit_code == 0, schema_result.output
    assert '"typography"' in schema_result.output
    assert '"chrome"' in schema_result.output

    validate_theme_result = runner.invoke(main, ["validate-theme", str(NVIDIA_THEME)])
    assert validate_theme_result.exit_code == 0, validate_theme_result.output
    assert "Valid theme: nvidia" in validate_theme_result.output

    validate_result = runner.invoke(
        main,
        ["validate", str(animation), "--theme-file", str(NVIDIA_THEME)],
    )
    assert validate_result.exit_code == 0, validate_result.output
    assert "theme: nvidia" in validate_result.output


def test_cli_render_and_audit_with_theme_file(tmp_path: Path):
    animation = _write_animation(tmp_path)
    output = tmp_path / "frame.png"
    runner = CliRunner()

    render_result = runner.invoke(
        main,
        ["render", str(animation), "-o", str(output), "--theme-file", str(NVIDIA_THEME)],
    )
    assert render_result.exit_code == 0, render_result.output
    assert output.exists()

    audit_result = runner.invoke(
        main,
        ["audit", str(animation), "--theme-file", str(NVIDIA_THEME)],
    )
    assert audit_result.exit_code == 0, audit_result.output
    assert "Audit passed" in audit_result.output
