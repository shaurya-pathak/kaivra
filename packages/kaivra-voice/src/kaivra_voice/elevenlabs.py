"""ElevenLabs voice synthesis provider."""

from __future__ import annotations

import base64
import os
import re
import subprocess
import tempfile

from kaivra.audio.base import AudioResult, VoiceProvider
from kaivra.audio.timings import AudioCue


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
        response = client.text_to_speech.convert_with_timestamps(
            text=text,
            voice_id=voice_id,
            output_format="mp3_44100_128",
        )

        output_path = os.path.join(tempfile.gettempdir(), f"kaivra_{scene_id}.mp3")
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(response.audio_base_64))

        duration = _measure_duration(output_path)
        return AudioResult(
            audio_path=output_path,
            duration_seconds=duration,
            scene_id=scene_id,
            cues=_cues_from_alignment(response.normalized_alignment or response.alignment),
        )


def _cues_from_alignment(alignment: object | None) -> tuple[AudioCue, ...]:
    if alignment is None:
        return ()

    characters = getattr(alignment, "characters", None) or []
    starts = getattr(alignment, "character_start_times_seconds", None) or []
    ends = getattr(alignment, "character_end_times_seconds", None) or []
    if not (len(characters) == len(starts) == len(ends)):
        return ()

    cues: list[AudioCue] = []
    word_chars: list[str] = []
    word_start: float | None = None
    word_end: float | None = None

    for char, start, end in zip(characters, starts, ends, strict=False):
        if char.isspace():
            _flush_word(cues, word_chars, word_start, word_end)
            word_chars = []
            word_start = None
            word_end = None
            continue

        if word_start is None:
            word_start = float(start)
        word_end = float(end)
        word_chars.append(char)

    _flush_word(cues, word_chars, word_start, word_end)
    return tuple(cues)


def _flush_word(
    cues: list[AudioCue],
    word_chars: list[str],
    word_start: float | None,
    word_end: float | None,
) -> None:
    if not word_chars or word_start is None or word_end is None or word_end <= word_start:
        return
    word_text = re.sub(r"^[^\w]+|[^\w]+$", "", "".join(word_chars))
    if not word_text:
        return
    cues.append(
        AudioCue(
            start_seconds=word_start,
            duration_seconds=word_end - word_start,
            text=word_text,
            kind="word",
        )
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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffprobe is required to measure generated ElevenLabs audio. "
            "Install ffmpeg so ffprobe is available on PATH."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    return float(proc.stdout.strip())
