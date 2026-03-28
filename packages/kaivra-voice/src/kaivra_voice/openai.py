"""OpenAI voice synthesis provider."""

from __future__ import annotations

import os
import tempfile
import wave

from kaivra.audio.base import AudioResult, VoiceProvider

_DEFAULT_MODEL = "gpt-4o-mini-tts"
_DEFAULT_VOICE = "alloy"


class OpenAIProvider(VoiceProvider):
    """Voice provider using the OpenAI speech API."""

    def __init__(self, voice_id: str = _DEFAULT_VOICE, model: str = _DEFAULT_MODEL) -> None:
        self.voice_id = voice_id
        self.model = model

    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        """Generate WAV audio for a scene using the OpenAI speech API."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is required. "
                "Get your API key at https://platform.openai.com/api-keys"
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required: pip install openai") from exc

        voice_id = kwargs.get("voice_id", self.voice_id)
        model = kwargs.get("model", self.model)
        output_path = os.path.join(tempfile.gettempdir(), f"kaivra_{scene_id}.wav")

        client = OpenAI(api_key=api_key)
        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice_id,
            input=text,
            response_format="wav",
        ) as response:
            response.stream_to_file(output_path)

        duration = _measure_duration(output_path)
        return AudioResult(
            audio_path=output_path,
            duration_seconds=duration,
            scene_id=scene_id,
            cues=(),
        )


def _measure_duration(path: str) -> float:
    """Measure generated WAV duration in seconds without shelling out."""
    with wave.open(path, "rb") as wf:
        frame_rate = wf.getframerate()
        if frame_rate <= 0:
            raise RuntimeError(f"Generated WAV has invalid sample rate: {frame_rate}")
        return wf.getnframes() / frame_rate
