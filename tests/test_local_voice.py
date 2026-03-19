from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from kaivra_voice.local import LocalProvider, _audio_samples_to_wav_bytes, resolve_local_model_paths


def test_local_provider_generate_autodiscovers_tokens_and_data_dir(tmp_path, monkeypatch):
    bundle_dir = _make_model_bundle(tmp_path / "amy")
    captured: dict[str, object] = {}

    class FakeVitsModelConfig:
        def __init__(self, *, model: str, tokens: str, data_dir: str) -> None:
            captured["model"] = model
            captured["tokens"] = tokens
            captured["data_dir"] = data_dir

    class FakeModelConfig:
        def __init__(self, *, vits: object) -> None:
            captured["vits"] = vits

    class FakeTtsConfig:
        def __init__(self, *, model: object) -> None:
            captured["tts_model"] = model

    class FakeAudio:
        sample_rate = 22050
        samples = [0.0, 0.25, -0.25]

    class FakeOfflineTts:
        def __init__(self, _config: object) -> None:
            pass

        @staticmethod
        def generate(_text: str) -> FakeAudio:
            return FakeAudio()

    fake_sherpa = types.SimpleNamespace(
        OfflineTtsVitsModelConfig=FakeVitsModelConfig,
        OfflineTtsModelConfig=FakeModelConfig,
        OfflineTtsConfig=FakeTtsConfig,
        OfflineTts=FakeOfflineTts,
    )

    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake_sherpa)
    monkeypatch.setattr("kaivra_voice.local._measure_duration", lambda _path: 1.25)

    provider = LocalProvider(model_path=str(bundle_dir))
    result = provider.generate("intro", "hello")

    assert result.scene_id == "intro"
    assert result.duration_seconds == 1.25
    assert Path(captured["model"]) == bundle_dir / "voice.onnx"
    assert Path(captured["tokens"]) == bundle_dir / "tokens.txt"
    assert Path(captured["data_dir"]) == bundle_dir / "espeak-ng-data"


def test_audio_samples_to_wav_bytes_clips_and_converts_float_samples() -> None:
    class FakeAudio:
        samples = [-1.5, -0.25, 0.0, 0.25, 1.5]

    pcm = _audio_samples_to_wav_bytes(FakeAudio())

    assert pcm == b"\x01\x80\x01\xe0\x00\x00\xff\x1f\xff\x7f"


@pytest.mark.integration
def test_local_provider_generate_with_real_sherpa_when_available() -> None:
    pytest.importorskip("sherpa_onnx")

    try:
        resolved = resolve_local_model_paths(model_path=None, tokens_path=None, data_dir=None)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    result = LocalProvider(
        model_path=resolved.model_path,
        tokens_path=resolved.tokens_path,
        data_dir=resolved.data_dir,
    ).generate("integration", "Hello from Kaivra.")

    assert result.duration_seconds > 0
    assert Path(result.audio_path).exists()


def test_resolve_local_model_paths_falls_back_to_default_download_root(tmp_path, monkeypatch):
    bundle_dir = _make_model_bundle(tmp_path / ".kaivra" / "models" / "amy")
    monkeypatch.setattr("kaivra_voice.local.Path.home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("SHERPA_MODEL_PATH", raising=False)

    resolved = resolve_local_model_paths(model_path=None, tokens_path=None, data_dir=None)

    assert resolved.model_path == str(bundle_dir / "voice.onnx")
    assert resolved.tokens_path == str(bundle_dir / "tokens.txt")
    assert resolved.data_dir == str(bundle_dir / "espeak-ng-data")


def test_resolve_local_model_paths_raises_clear_error_when_bundle_is_incomplete(tmp_path):
    bundle_dir = tmp_path / "broken"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "voice.onnx").write_bytes(b"onnx")

    with pytest.raises(RuntimeError, match="tokens.txt"):
        resolve_local_model_paths(model_path=str(bundle_dir), tokens_path=None, data_dir=None)


def _make_model_bundle(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "voice.onnx").write_bytes(b"onnx")
    (path / "tokens.txt").write_text("a", encoding="utf-8")
    (path / "espeak-ng-data").mkdir()
    return path
