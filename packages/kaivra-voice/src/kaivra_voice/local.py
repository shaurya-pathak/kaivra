"""Local voice synthesis provider using Sherpa-ONNX."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from array import array
from dataclasses import dataclass
from pathlib import Path

from kaivra.audio.base import AudioResult, VoiceProvider
from kaivra.audio.timings import AudioCue

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalModelPaths:
    """Resolved local Sherpa model bundle paths."""

    model_path: str
    tokens_path: str
    data_dir: str


class LocalProvider(VoiceProvider):
    """Voice provider using sherpa-onnx for local offline TTS."""

    def __init__(
        self,
        model_path: str | None = None,
        tokens_path: str | None = None,
        data_dir: str | None = None,
    ) -> None:
        self.model_path = model_path
        self.tokens_path = tokens_path
        self.data_dir = data_dir

    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        """Generate audio for a scene using local sherpa-onnx TTS."""
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError(
                "sherpa-onnx is required for local TTS: pip install kaivra-voice[local]"
            ) from exc

        resolved = resolve_local_model_paths(
            model_path=kwargs.get("model_path", self.model_path),
            tokens_path=kwargs.get("tokens_path", self.tokens_path),
            data_dir=kwargs.get("data_dir", self.data_dir),
        )

        tts_config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=resolved.model_path,
                    tokens=resolved.tokens_path,
                    data_dir=resolved.data_dir,
                ),
            ),
        )
        tts = sherpa_onnx.OfflineTts(tts_config)
        audio = tts.generate(text)

        output_path = os.path.join(tempfile.gettempdir(), f"kaivra_{scene_id}.wav")
        import wave

        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(_audio_samples_to_wav_bytes(audio))

        duration = _measure_duration(output_path)
        cues = _align_words_whisper(output_path)
        return AudioResult(
            audio_path=output_path,
            duration_seconds=duration,
            scene_id=scene_id,
            cues=cues,
        )


def resolve_local_model_paths(
    *,
    model_path: str | None,
    tokens_path: str | None,
    data_dir: str | None,
) -> LocalModelPaths:
    """Resolve the Sherpa model file, tokens, and data dir with autodiscovery."""
    explicit_model = model_path.strip() if isinstance(model_path, str) else None
    if explicit_model:
        resolved_model = _resolve_model_file(Path(explicit_model).expanduser())
    else:
        resolved_model = _discover_default_model_file()

    bundle_dir = resolved_model.parent
    resolved_tokens = _resolve_tokens_path(tokens_path, bundle_dir)
    resolved_data_dir = _resolve_data_dir(data_dir, bundle_dir)

    return LocalModelPaths(
        model_path=str(resolved_model),
        tokens_path=str(resolved_tokens),
        data_dir=str(resolved_data_dir),
    )


def _discover_default_model_file() -> Path:
    env_model = os.environ.get("SHERPA_MODEL_PATH", "").strip()
    if env_model:
        candidate = Path(env_model).expanduser()
        try:
            return _resolve_model_file(candidate)
        except RuntimeError:
            pass

    default_root = Path.home() / ".kaivra" / "models"
    if default_root.exists():
        model_file = _find_model_file(default_root)
        if model_file is not None:
            return model_file

    raise RuntimeError(
        "Could not locate a local Sherpa model. Set SHERPA_MODEL_PATH to a model file "
        "or downloaded model directory, or place a model bundle under ~/.kaivra/models/ "
        "with an .onnx file, tokens.txt, and espeak-ng-data/."
    )


def _resolve_model_file(candidate: Path) -> Path:
    if not candidate.exists():
        raise RuntimeError(
            f"Local Sherpa model path does not exist: {candidate}. "
            "Pass a valid model file or model directory."
        )

    if candidate.is_file():
        if candidate.suffix != ".onnx":
            raise RuntimeError(
                f"Local Sherpa model must be an .onnx file or a model directory: {candidate}"
            )
        return candidate

    model_file = _find_model_file(candidate)
    if model_file is None:
        raise RuntimeError(
            f"Could not find an .onnx model file under {candidate}. "
            "Point model_path or SHERPA_MODEL_PATH at the downloaded model file or bundle directory."
        )
    return model_file


def _find_model_file(root: Path) -> Path | None:
    if root.is_file() and root.suffix == ".onnx":
        return root

    if not root.exists() or not root.is_dir():
        return None

    for candidate in sorted(root.rglob("*.onnx")):
        if candidate.is_file():
            return candidate
    return None


def _resolve_tokens_path(tokens_path: str | None, bundle_dir: Path) -> Path:
    if tokens_path is not None and tokens_path.strip():
        candidate = Path(tokens_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate
        raise RuntimeError(f"Local Sherpa tokens.txt was not found at {candidate}.")

    candidate = bundle_dir / "tokens.txt"
    if candidate.exists() and candidate.is_file():
        return candidate

    raise RuntimeError(
        f"Could not find tokens.txt next to the local Sherpa model in {bundle_dir}. "
        "Pass tokens_path explicitly or redownload the model bundle."
    )


def _resolve_data_dir(data_dir: str | None, bundle_dir: Path) -> Path:
    if data_dir is not None and data_dir.strip():
        candidate = Path(data_dir).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        raise RuntimeError(f"Local Sherpa espeak-ng-data directory was not found at {candidate}.")

    candidate = bundle_dir / "espeak-ng-data"
    if candidate.exists() and candidate.is_dir():
        return candidate

    raise RuntimeError(
        f"Could not find espeak-ng-data next to the local Sherpa model in {bundle_dir}. "
        "Pass data_dir explicitly or redownload the model bundle."
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


def _audio_samples_to_wav_bytes(audio: object) -> bytes:
    """Convert Sherpa float samples into 16-bit PCM bytes."""
    samples = getattr(audio, "samples", None)
    if samples is None:
        raise RuntimeError("Local Sherpa audio result did not expose a samples array.")

    pcm = array("h")
    for sample in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        pcm.append(int(clipped * 32767))
    return pcm.tobytes()


def _align_words_whisper(audio_path: str) -> tuple[AudioCue, ...]:
    """Run forced alignment on generated audio using faster-whisper.

    Returns word-level AudioCue objects, or an empty tuple if
    faster-whisper is not installed.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.debug("faster-whisper not installed — skipping word alignment for local TTS")
        return ()

    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(audio_path, word_timestamps=True)

        cues: list[AudioCue] = []
        for segment in segments:
            for word in segment.words:
                text = re.sub(r"^[^\w]+|[^\w]+$", "", word.word)
                if not text:
                    continue
                start = float(word.start)
                end = float(word.end)
                if end <= start:
                    continue
                cues.append(
                    AudioCue(
                        start_seconds=start,
                        duration_seconds=end - start,
                        text=text,
                        kind="word",
                    )
                )
        return tuple(cues)
    except Exception:
        log.warning("Whisper word alignment failed — falling back to no cues", exc_info=True)
        return ()
