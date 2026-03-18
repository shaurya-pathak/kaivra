"""Tests for the ElevenLabs voice provider."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add kaivra-voice src to path for direct testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kaivra_voice.elevenlabs import ElevenLabsProvider

from kaivra.audio.base import AudioResult, VoiceProvider


def test_implements_voice_provider():
    assert issubclass(ElevenLabsProvider, VoiceProvider)


def test_missing_api_key_raises():
    provider = ElevenLabsProvider()
    with patch.dict(os.environ, {}, clear=True):
        # Ensure ELEVENLABS_API_KEY is not set
        os.environ.pop("ELEVENLABS_API_KEY", None)
        with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
            provider.generate("scene_01", "Hello world")


def test_default_voice_id():
    provider = ElevenLabsProvider()
    assert provider.voice_id == "rachel"


def test_custom_voice_id():
    provider = ElevenLabsProvider(voice_id="adam")
    assert provider.voice_id == "adam"


def test_generate_calls_elevenlabs_api(tmp_path):
    mock_client_cls = MagicMock()
    mock_client = mock_client_cls.return_value
    mock_client.text_to_speech.convert.return_value = [b"\x00" * 100]

    mock_elevenlabs = MagicMock()
    mock_elevenlabs.client.ElevenLabs = mock_client_cls

    with (
        patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}),
        patch.dict(
            sys.modules,
            {"elevenlabs": mock_elevenlabs, "elevenlabs.client": mock_elevenlabs.client},
        ),
        patch("kaivra_voice.elevenlabs._measure_duration", return_value=5.2),
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
    ):
        provider = ElevenLabsProvider(voice_id="rachel")
        result = provider.generate("scene_01", "Hello world")

    assert isinstance(result, AudioResult)
    assert result.scene_id == "scene_01"
    assert result.duration_seconds == 5.2
    mock_client.text_to_speech.convert.assert_called_once_with(
        text="Hello world",
        voice_id="rachel",
        output_format="mp3_44100_128",
    )
