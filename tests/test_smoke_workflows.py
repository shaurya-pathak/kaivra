from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from kaivra.audio.base import AudioResult
from kaivra.cli import main
from kaivra.mcp.workspace import KaivraWorkspace


def test_workspace_doctor_runs_real_smoke_render(tmp_path: Path) -> None:
    report = KaivraWorkspace(tmp_path).run_doctor(
        required_checks={"python_package", "pycairo", "workspace_write", "smoke_render"},
        include_smoke=True,
    )

    checks = {check["name"]: check for check in report["checks"]}

    assert report["ok"] is True
    assert checks["smoke_render"]["ok"] is True


def test_quick_render_smoke_renders_real_png(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "quick-render-smoke.png"

    monkeypatch.chdir(repo_root)
    result = runner.invoke(
        main,
        [
            "quick-render",
            "examples/algorithms/bubble_sort.json",
            "--format",
            "png",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    doctor_result = runner.invoke(main, ["doctor", "--json"])
    assert doctor_result.exit_code == 0, doctor_result.output
    parsed = json.loads(doctor_result.output)
    assert "checks" in parsed


def test_quick_render_smoke_with_voice_renders_mp4(tmp_path: Path, monkeypatch) -> None:
    import kaivra.render.orchestration as orchestration

    raw_audio = tmp_path / "intro.mp3"
    raw_audio.write_bytes(b"raw")
    input_path = tmp_path / "voice-smoke.json"
    output_path = tmp_path / "voice-smoke.mp4"
    input_path.write_text(
        json.dumps(
            {
                "version": "1.1",
                "meta": {"title": "Voice Smoke", "theme": "modern"},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "2s",
                        "narration": "Hello from Kaivra voice smoke.",
                        "objects": [{"id": "title", "type": "text", "content": "Voice Smoke"}],
                        "animations": [{"action": "appear", "target": "title", "at": "0s"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class DummyProvider:
        def generate(self, scene_id: str, _text: str, **kwargs) -> AudioResult:
            return AudioResult(
                audio_path=str(raw_audio),
                duration_seconds=1.0,
                scene_id=scene_id,
            )

    class DummyRegistry:
        def discover(self) -> None:
            return None

        def get(self, _name: str):
            return DummyProvider

    def fake_normalize(_input_path: str, output_path: str) -> None:
        Path(output_path).write_bytes(b"wav")

    def fake_export_video(_graph, _theme, output: str, **kwargs) -> None:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(1, 1)
        Path(output).write_bytes(b"video")

    def fake_concat(_audio_paths: list[str], output: str) -> None:
        Path(output).write_bytes(b"concat")

    def fake_mux(_video_path: str, _audio_path: str, output: str) -> None:
        Path(output).write_bytes(b"voiced")

    monkeypatch.setattr("kaivra.cli._run_preflight_for_render", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestration, "ProviderRegistry", DummyRegistry)
    monkeypatch.setattr(orchestration, "normalize_audio_to_wav", fake_normalize)
    monkeypatch.setattr(orchestration, "measure_audio_duration", lambda _path: 1.8)
    monkeypatch.setattr(orchestration, "export_video", fake_export_video)
    monkeypatch.setattr(orchestration, "concat_audio", fake_concat)
    monkeypatch.setattr(orchestration, "mux_audio", fake_mux)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "quick-render",
            str(input_path),
            "--voice",
            "--voice-provider",
            "dummy",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert "Generating voice for scene intro." in result.output
    assert "Muxing narration onto the rendered video." in result.output
    assert "Rendered video with voice" in result.output
