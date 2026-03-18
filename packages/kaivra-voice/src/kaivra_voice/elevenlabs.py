"""ElevenLabs voice synthesis provider."""

from __future__ import annotations

import os
import subprocess
import tempfile

from kaivra.audio.base import AudioResult, VoiceProvider


class ElevenLabsProvider(VoiceProvider):
    """Voice provider using the ElevenLabs text-to-speech API."""

    def __init__(self, voice_id: str = "rachel") -> None:
        self.voice_id = voice_id

    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        """Generate audio for a scene using ElevenLabs API.

        Requires ELEVENLABS_API_KEY environment variable.
        """
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY environment variable is required. "
                "Get your API key at https://elevenlabs.io"
            )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as exc:
            raise RuntimeError("elevenlabs package is required: pip install elevenlabs") from exc

        voice_id = kwargs.get("voice_id", self.voice_id)

        client = ElevenLabs(api_key=api_key)
        audio_iter = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            output_format="mp3_44100_128",
        )

        output_path = os.path.join(tempfile.gettempdir(), f"kaivra_{scene_id}.mp3")
        with open(output_path, "wb") as f:
            for chunk in audio_iter:
                f.write(chunk)

        duration = _measure_duration(output_path)
        return AudioResult(
            audio_path=output_path,
            duration_seconds=duration,
            scene_id=scene_id,
        )


def _measure_duration(path: str) -> float:
    """Measure audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    return float(proc.stdout.strip())
