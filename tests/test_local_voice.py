import json
from pathlib import Path
import wave

from click.testing import CliRunner

from kaivra.audio.local_voice import LocalVoiceConfig, synthesize_local_voice_assets
from kaivra.cli import main
from kaivra.dsl.parser import parse_string


def _write_fake_sherpa_binary(tmp_path: Path) -> Path:
    script = tmp_path / "fake_sherpa_tts.py"
    script.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import math
import sys
import wave

output = None
text = None
for arg in sys.argv[1:]:
    if arg.startswith("--output-filename="):
        output = Path(arg.split("=", 1)[1])
    elif not arg.startswith("--"):
        text = arg

if output is None:
    raise SystemExit("missing --output-filename")

sample_rate = 24000
duration_seconds = 0.25 if text else 0.0
frame_count = int(sample_rate * duration_seconds)

output.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(output), "wb") as writer:
    writer.setnchannels(1)
    writer.setsampwidth(2)
    writer.setframerate(sample_rate)
    for index in range(frame_count):
        amplitude = int(4000 * math.sin(2 * math.pi * 220 * index / sample_rate))
        writer.writeframesraw(amplitude.to_bytes(2, byteorder="little", signed=True))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_fake_sherpa_assets(tmp_path: Path) -> Path:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.onnx").write_bytes(b"fake")
    (model_dir / "tokens.txt").write_text("a\nb\n", encoding="utf-8")
    (model_dir / "espeak-ng-data").mkdir()
    return model_dir


def _read_wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as reader:
        return reader.getnframes() / reader.getframerate()


def test_synthesize_local_voice_assets_with_fake_sherpa(tmp_path: Path):
    fake_binary = _write_fake_sherpa_binary(tmp_path)
    model_dir = _write_fake_sherpa_assets(tmp_path)
    document = parse_string(
        json.dumps(
            {
                "version": "1.1",
                "meta": {"title": "Voice Test", "theme": "modern"},
                "scenes": [
                    {
                        "id": "spoken",
                        "duration": "1s",
                        "narration": "Hello from local voice.",
                        "objects": [],
                    },
                    {
                        "id": "quiet",
                        "duration": "1.4s",
                        "objects": [],
                    },
                ],
            }
        ),
        format="json",
    )

    config = LocalVoiceConfig.from_sources(
        model_path=str(model_dir),
        tokens_path=None,
        data_dir=None,
        lexicon_path=None,
        rule_fsts=None,
        speaker_id=None,
        speed=None,
        pad_seconds=0.5,
        binary_name=str(fake_binary),
    )
    assets = synthesize_local_voice_assets(document, tmp_path / "artifacts", config, stem="demo")

    timings_payload = json.loads(assets.timings_path.read_text(encoding="utf-8"))
    assert timings_payload["scene_durations"]["spoken"] == 1.0
    assert timings_payload["scene_durations"]["quiet"] == 1.4
    assert round(_read_wav_duration(assets.audio_path), 2) == 2.4


def test_cli_render_supports_local_voice_mode(tmp_path: Path, monkeypatch):
    fake_binary = _write_fake_sherpa_binary(tmp_path)
    model_dir = _write_fake_sherpa_assets(tmp_path)
    animation_path = tmp_path / "animation.json"
    animation_path.write_text(
        json.dumps(
            {
                "version": "1.1",
                "meta": {"title": "Voice CLI", "theme": "modern"},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "1s",
                        "narration": "A narrated scene.",
                        "objects": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_export_video(graph, theme, output, fps=30):
        Path(output).write_bytes(b"silent-video")

    def fake_mux_audio(video_path, audio_path, output_path):
        assert Path(video_path).exists()
        assert Path(audio_path).exists()
        Path(output_path).write_bytes(b"voiced-video")

    monkeypatch.setattr("kaivra.render.video.exporter.export_video", fake_export_video)
    monkeypatch.setattr("kaivra.audio.mux.mux_audio", fake_mux_audio)

    output = tmp_path / "voice.mp4"
    artifacts_dir = tmp_path / "voice_artifacts"
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "render",
            str(animation_path),
            "-o",
            str(output),
            "--voice-mode",
            "local",
            "--voice-model",
            str(model_dir),
            "--voice-binary",
            str(fake_binary),
            "--voice-artifacts-dir",
            str(artifacts_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert (artifacts_dir / "voice_local_voice.wav").exists()
    assert (artifacts_dir / "voice_local_voice_timings.json").exists()


def test_cli_rejects_manual_audio_with_local_voice(tmp_path: Path):
    animation_path = tmp_path / "animation.json"
    animation_path.write_text(
        json.dumps(
            {
                "version": "1.1",
                "meta": {"title": "Conflict", "theme": "modern"},
                "scenes": [{"id": "intro", "duration": "1s", "narration": "Hi", "objects": []}],
            }
        ),
        encoding="utf-8",
    )
    audio_path = tmp_path / "manual.wav"
    audio_path.write_bytes(b"manual")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "render",
            str(animation_path),
            "-o",
            str(tmp_path / "out.mp4"),
            "--audio",
            str(audio_path),
            "--voice-mode",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "Use either manual --audio/--audio-timings inputs or --voice-mode local" in result.output
