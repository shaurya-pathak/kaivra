"""Tests for the local Sherpa voice provider."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kaivra_voice.local import LocalProvider

from kaivra.audio.base import AudioResult, VoiceProvider


def test_implements_voice_provider():
    assert issubclass(LocalProvider, VoiceProvider)


def test_generate_returns_empty_cues(tmp_path):
    """Local provider returns empty cues (no word-level sync)."""
    mock_sherpa = MagicMock()
    mock_audio = MagicMock()
    mock_audio.samples = [0.1, 0.2, -0.1, 0.0]
    mock_audio.sample_rate = 22050
    mock_sherpa.OfflineTts.return_value.generate.return_value = mock_audio

    with (
        patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}),
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
    assert result.cues == ()
