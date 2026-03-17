"""Local voice synthesis provider using Sherpa-ONNX."""

from __future__ import annotations

import os
import subprocess
import tempfile

from kaivra.audio.base import AudioResult, VoiceProvider


class LocalProvider(VoiceProvider):
    """Voice provider using sherpa-onnx for local offline TTS."""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path

    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        """Generate audio for a scene using local sherpa-onnx TTS."""
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError(
                "sherpa-onnx is required for local TTS: "
                "pip install kaivra-voice[local]"
            ) from exc

        model_path = kwargs.get("model_path", self.model_path)
        if model_path is None:
            model_path = os.environ.get("SHERPA_MODEL_PATH")
        if model_path is None:
            raise RuntimeError(
                "No model path provided. Set SHERPA_MODEL_PATH or pass --voice-model-path."
            )

        tts_config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=model_path,
                ),
            ),
        )
        tts = sherpa_onnx.OfflineTts(tts_config)
        audio = tts.generate(text)

        output_path = os.path.join(
            tempfile.gettempdir(), f"kaivra_{scene_id}.wav"
        )
        import wave
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(audio.samples_as_bytes())

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
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    return float(proc.stdout.strip())
