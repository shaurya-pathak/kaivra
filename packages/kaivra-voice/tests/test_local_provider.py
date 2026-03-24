"""Tests for the local Sherpa voice provider with Whisper alignment."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kaivra_voice.local import LocalProvider, _align_words_whisper

from kaivra.audio.base import AudioResult, VoiceProvider


def test_implements_voice_provider():
    assert issubclass(LocalProvider, VoiceProvider)


def test_align_words_whisper_returns_cues():
    """When faster-whisper is available, word cues are produced."""
    mock_word_1 = MagicMock(word="Hello", start=0.0, end=0.4)
    mock_word_2 = MagicMock(word="world!", start=0.5, end=1.0)
    mock_segment = MagicMock(words=[mock_word_1, mock_word_2])

    mock_model_cls = MagicMock()
    mock_model = mock_model_cls.return_value
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    mock_faster_whisper = MagicMock()
    mock_faster_whisper.WhisperModel = mock_model_cls

    with patch.dict(sys.modules, {"faster_whisper": mock_faster_whisper}):
        cues = _align_words_whisper("/tmp/test.wav")

    assert len(cues) == 2
    assert cues[0].text == "Hello"
    assert cues[0].start_seconds == 0.0
    assert cues[0].duration_seconds == pytest.approx(0.4)
    assert cues[0].kind == "word"
    assert cues[1].text == "world"
    assert cues[1].start_seconds == 0.5
    assert cues[1].duration_seconds == pytest.approx(0.5)

    mock_model_cls.assert_called_once_with("tiny", device="cpu", compute_type="int8")
    mock_model.transcribe.assert_called_once_with("/tmp/test.wav", word_timestamps=True)


def test_align_words_whisper_graceful_without_package():
    """Without faster-whisper, returns empty cues (no error)."""
    with patch.dict(sys.modules, {"faster_whisper": None}):
        cues = _align_words_whisper("/tmp/test.wav")

    assert cues == ()


def test_align_words_whisper_graceful_on_error():
    """If whisper raises, returns empty cues (no crash)."""
    mock_faster_whisper = MagicMock()
    mock_faster_whisper.WhisperModel.side_effect = RuntimeError("model load failed")

    with patch.dict(sys.modules, {"faster_whisper": mock_faster_whisper}):
        cues = _align_words_whisper("/tmp/test.wav")

    assert cues == ()


def test_generate_includes_whisper_cues(tmp_path):
    """Full generate() flow returns cues when whisper is available."""
    mock_sherpa = MagicMock()
    mock_audio = MagicMock()
    mock_audio.samples = [0.1, 0.2, -0.1, 0.0]
    mock_audio.sample_rate = 22050
    mock_sherpa.OfflineTts.return_value.generate.return_value = mock_audio

    mock_word = MagicMock(word="Test", start=0.0, end=0.5)
    mock_segment = MagicMock(words=[mock_word])
    mock_model_cls = MagicMock()
    mock_model_cls.return_value.transcribe.return_value = ([mock_segment], MagicMock())
    mock_faster_whisper = MagicMock()
    mock_faster_whisper.WhisperModel = mock_model_cls

    with (
        patch.dict(
            sys.modules,
            {"sherpa_onnx": mock_sherpa, "faster_whisper": mock_faster_whisper},
        ),
        patch(
            "kaivra_voice.local.resolve_local_model_paths",
            return_value=MagicMock(
                model_path="/m/model.onnx",
                tokens_path="/m/tokens.txt",
                data_dir="/m/espeak-ng-data",
            ),
        ),
        patch("kaivra_voice.local._measure_duration", return_value=3.0),
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
    ):
        provider = LocalProvider()
        result = provider.generate("scene_01", "Test narration")

    assert isinstance(result, AudioResult)
    assert result.scene_id == "scene_01"
    assert result.duration_seconds == 3.0
    assert len(result.cues) == 1
    assert result.cues[0].text == "Test"
    assert result.cues[0].kind == "word"
