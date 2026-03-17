"""Tests for voice-related CLI flags."""

from click.testing import CliRunner

from kaivra.cli import main


def test_voice_and_audio_are_mutually_exclusive(tmp_path):
    """--voice cannot be combined with --audio."""
    dummy_audio = tmp_path / "audio.mp3"
    dummy_audio.write_bytes(b"\x00")
    dummy_input = tmp_path / "input.json"
    dummy_input.write_text('{"meta": {}, "scenes": []}')

    runner = CliRunner()
    result = runner.invoke(main, [
        "render", str(dummy_input),
        "-o", str(tmp_path / "out.mp4"),
        "--voice",
        "--audio", str(dummy_audio),
    ])
    assert result.exit_code != 0
    assert "--voice cannot be combined" in result.output


def test_voice_and_audio_timings_are_mutually_exclusive(tmp_path):
    """--voice cannot be combined with --audio-timings."""
    dummy_timings = tmp_path / "timings.json"
    dummy_timings.write_text('{"scene_durations": {}}')
    dummy_input = tmp_path / "input.json"
    dummy_input.write_text('{"meta": {}, "scenes": []}')

    runner = CliRunner()
    result = runner.invoke(main, [
        "render", str(dummy_input),
        "-o", str(tmp_path / "out.mp4"),
        "--voice",
        "--audio-timings", str(dummy_timings),
    ])
    assert result.exit_code != 0
    assert "--voice cannot be combined" in result.output
