"""Tests for the OpenAI voice provider."""

import os
import sys
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kaivra_voice.openai import OpenAIProvider

from kaivra.audio.base import AudioResult, VoiceProvider


def test_implements_voice_provider():
    assert issubclass(OpenAIProvider, VoiceProvider)


def test_missing_api_key_raises():
    provider = OpenAIProvider()
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            provider.generate("scene_01", "Hello world")


def test_default_voice_and_model():
    provider = OpenAIProvider()
    assert provider.voice_id == "alloy"
    assert provider.model == "gpt-4o-mini-tts"


def test_generate_calls_openai_speech_api(tmp_path):
    mock_client_cls = MagicMock()
    mock_client = mock_client_cls.return_value
    mock_response = MagicMock()

    def stream_to_file(path: str) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

    mock_response.stream_to_file.side_effect = stream_to_file
    mock_streaming = MagicMock()
    mock_streaming.create.return_value.__enter__.return_value = mock_response
    mock_streaming.create.return_value.__exit__.return_value = None
    mock_client.audio.speech.with_streaming_response = mock_streaming

    mock_openai_module = SimpleNamespace(OpenAI=mock_client_cls)

    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
        patch.dict(sys.modules, {"openai": mock_openai_module}),
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
    ):
        provider = OpenAIProvider(voice_id="verse")
        result = provider.generate("scene_01", "Hello world")

    assert isinstance(result, AudioResult)
    assert result.scene_id == "scene_01"
    assert result.audio_path.endswith(".wav")
    assert result.duration_seconds == 1.0
    assert result.cues == ()
    mock_streaming.create.assert_called_once_with(
        model="gpt-4o-mini-tts",
        voice="verse",
        input="Hello world",
        response_format="wav",
    )
