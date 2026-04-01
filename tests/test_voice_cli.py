"""Tests for voice-related CLI flags."""

from click.testing import CliRunner

import kaivra.cli as cli_module
from kaivra.cli import main


def test_voice_and_audio_are_mutually_exclusive(tmp_path):
    """--voice cannot be combined with --audio."""
    dummy_audio = tmp_path / "audio.mp3"
    dummy_audio.write_bytes(b"\x00")
    dummy_input = tmp_path / "input.json"
    dummy_input.write_text('{"meta": {}, "scenes": []}')

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "render",
            str(dummy_input),
            "-o",
            str(tmp_path / "out.mp4"),
            "--voice",
            "--audio",
            str(dummy_audio),
        ],
    )
    assert result.exit_code != 0
    assert "--voice cannot be combined" in result.output


def test_voice_and_audio_timings_are_mutually_exclusive(tmp_path):
    """--voice cannot be combined with --audio-timings."""
    dummy_timings = tmp_path / "timings.json"
    dummy_timings.write_text('{"scene_durations": {}}')
    dummy_input = tmp_path / "input.json"
    dummy_input.write_text('{"meta": {}, "scenes": []}')

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "render",
            str(dummy_input),
            "-o",
            str(tmp_path / "out.mp4"),
            "--voice",
            "--audio-timings",
            str(dummy_timings),
        ],
    )
    assert result.exit_code != 0
    assert "--voice cannot be combined" in result.output


def test_render_help_mentions_openai_default_provider() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["render", "--help"])
    assert result.exit_code == 0
    assert "KAIVRA_VOICE_PROVIDER" in result.output
    assert "openai" in result.output


def test_quick_render_voice_surfaces_provider_setup_errors(tmp_path, monkeypatch):
    input_file = tmp_path / "demo.json"
    input_file.write_text(
        '{"version":"1.2","meta":{"title":"Demo","theme":"modern"},"scenes":[]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "kaivra.mcp.workspace.KaivraWorkspace.check_animation",
        lambda *args, **kwargs: {
            "valid": True,
            "warnings": [],
            "blocking_issues": [],
        },
    )
    monkeypatch.setattr(
        "kaivra.mcp.workspace.KaivraWorkspace.preflight_command",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "kaivra.mcp.workspace.KaivraWorkspace.validate_voice_setup",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY missing")),
    )
    monkeypatch.setattr(cli_module, "_render_to_output", lambda **kwargs: None)

    runner = CliRunner()
    result = runner.invoke(main, ["quick-render", str(input_file), "--voice"])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY missing" in result.output
