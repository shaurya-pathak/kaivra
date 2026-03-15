"""Local/offline narration synthesis helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import wave

from kaivra.audio.timings import AudioTimingData, SceneAudioTiming
from kaivra.dsl.retime import estimate_scene_duration
from kaivra.dsl.schema import DocumentSpec

__all__ = [
    "DEFAULT_SHERPA_BINARY",
    "GeneratedLocalVoiceAssets",
    "LocalVoiceConfig",
    "synthesize_local_voice_assets",
]

DEFAULT_SHERPA_BINARY = "sherpa-onnx-offline-tts"


@dataclass(frozen=True)
class LocalVoiceConfig:
    """Configuration for locally synthesized narration audio."""

    model_path: Path | None
    tokens_path: Path | None
    data_dir: Path | None
    lexicon_path: Path | None
    rule_fsts: str | None
    speaker_id: int
    speed: float
    pad_seconds: float
    binary_name: str

    @classmethod
    def from_sources(
        cls,
        *,
        model_path: str | None,
        tokens_path: str | None,
        data_dir: str | None,
        lexicon_path: str | None,
        rule_fsts: str | None,
        speaker_id: int | None,
        speed: float | None,
        pad_seconds: float | None,
        binary_name: str | None,
    ) -> "LocalVoiceConfig":
        return cls(
            model_path=_option_or_env_path(model_path, "KAIVRA_SHERPA_MODEL"),
            tokens_path=_option_or_env_path(tokens_path, "KAIVRA_SHERPA_TOKENS"),
            data_dir=_option_or_env_path(data_dir, "KAIVRA_SHERPA_DATA_DIR"),
            lexicon_path=_option_or_env_path(lexicon_path, "KAIVRA_SHERPA_LEXICON"),
            rule_fsts=rule_fsts or os.getenv("KAIVRA_SHERPA_RULE_FSTS"),
            speaker_id=_option_or_env_int(speaker_id, "KAIVRA_SHERPA_SPEAKER", default=0),
            speed=_option_or_env_float(speed, "KAIVRA_SHERPA_SPEED", default=1.0),
            pad_seconds=_option_or_env_float(pad_seconds, "KAIVRA_SHERPA_PAD", default=0.8),
            binary_name=binary_name or os.getenv("KAIVRA_SHERPA_BIN") or DEFAULT_SHERPA_BINARY,
        )


@dataclass(frozen=True)
class GeneratedLocalVoiceAssets:
    """Generated local voice artifacts for a rendered animation."""

    audio_path: Path
    timings_path: Path
    timing_data: AudioTimingData
    artifacts_dir: Path


@dataclass(frozen=True)
class _WaveFormat:
    channels: int
    sample_width: int
    sample_rate: int
    compression_type: str
    compression_name: str

    @classmethod
    def from_reader(cls, reader: wave.Wave_read) -> "_WaveFormat":
        return cls(
            channels=reader.getnchannels(),
            sample_width=reader.getsampwidth(),
            sample_rate=reader.getframerate(),
            compression_type=reader.getcomptype(),
            compression_name=reader.getcompname(),
        )


@dataclass(frozen=True)
class _GeneratedSceneClip:
    scene_id: str
    text: str | None
    authored_duration_seconds: float
    raw_path: Path | None
    raw_duration_seconds: float


@dataclass(frozen=True)
class _ResolvedSherpaConfig:
    binary_path: str | None
    model_path: Path
    tokens_path: Path
    data_dir: Path
    lexicon_path: Path | None
    rule_fsts: str | None
    speaker_id: int
    speed: float
    pad_seconds: float


def synthesize_local_voice_assets(
    document: DocumentSpec,
    artifacts_dir: str | Path,
    config: LocalVoiceConfig,
    *,
    stem: str = "voice",
) -> GeneratedLocalVoiceAssets:
    """Generate scene narration audio and timing metadata with local Sherpa TTS."""
    resolved = _resolve_sherpa_config(config)
    if resolved.speed <= 0:
        raise ValueError("Local voice speed must be greater than zero.")
    if resolved.pad_seconds < 0:
        raise ValueError("Local voice pad must be zero or greater.")

    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scene_audio_dir = artifacts_dir / "scene_audio"
    scene_audio_dir.mkdir(parents=True, exist_ok=True)

    raw_clips: list[_GeneratedSceneClip] = []
    wave_format: _WaveFormat | None = None
    python_tts = _build_python_tts(resolved) if resolved.binary_path is None else None
    for index, scene in enumerate(document.scenes):
        scene_id = scene.id or f"scene_{index + 1}"
        text = _normalize_text(scene.narration)
        authored_duration = _authored_scene_duration_seconds(scene)
        raw_path: Path | None = None
        raw_duration = 0.0

        if text:
            raw_path = scene_audio_dir / f"{index + 1:02d}_{_slugify(scene_id)}_raw.wav"
            _run_sherpa_tts(text, raw_path, resolved, python_tts=python_tts)
            clip_format, raw_duration = _read_wav_metadata(raw_path)
            if wave_format is None:
                wave_format = clip_format
            elif clip_format != wave_format:
                raise RuntimeError(
                    "Sherpa produced inconsistent WAV formats across scenes. "
                    "Use a single voice model for the whole render."
                )

        raw_clips.append(
            _GeneratedSceneClip(
                scene_id=scene_id,
                text=text,
                authored_duration_seconds=authored_duration,
                raw_path=raw_path,
                raw_duration_seconds=raw_duration,
            )
        )

    if wave_format is None:
        raise ValueError("Local voice mode needs at least one scene with narration text.")

    scene_durations: dict[str, float] = {}
    rendered_scene_paths: list[Path] = []
    for index, clip in enumerate(raw_clips):
        output_path = scene_audio_dir / f"{index + 1:02d}_{_slugify(clip.scene_id)}.wav"
        if clip.raw_path is not None:
            target_duration = max(
                clip.authored_duration_seconds,
                clip.raw_duration_seconds + resolved.pad_seconds,
            )
            _copy_wav_with_padding(clip.raw_path, output_path, target_duration, wave_format)
        else:
            target_duration = clip.authored_duration_seconds
            _write_silence_wav(output_path, target_duration, wave_format)

        scene_durations[clip.scene_id] = target_duration
        rendered_scene_paths.append(output_path)

    audio_path = artifacts_dir / f"{stem}_local_voice.wav"
    _concatenate_wav_files(rendered_scene_paths, audio_path, wave_format)

    timings_path = artifacts_dir / f"{stem}_local_voice_timings.json"
    timings_payload = {"scene_durations": scene_durations}
    timings_path.write_text(json.dumps(timings_payload, indent=2), encoding="utf-8")

    timing_data = AudioTimingData(
        scenes={
            scene_id: SceneAudioTiming(id=scene_id, duration_seconds=duration)
            for scene_id, duration in scene_durations.items()
        }
    )
    return GeneratedLocalVoiceAssets(
        audio_path=audio_path,
        timings_path=timings_path,
        timing_data=timing_data,
        artifacts_dir=artifacts_dir,
    )


def _resolve_sherpa_config(config: LocalVoiceConfig) -> _ResolvedSherpaConfig:
    model_path = _resolve_model_path(config.model_path)
    if model_path is None:
        raise ValueError(
            "Local voice mode requires a Sherpa model. "
            "Pass --voice-model or set KAIVRA_SHERPA_MODEL."
        )
    binary_path = _resolve_binary(config.binary_name)

    tokens_path = _resolve_required_path(
        provided=config.tokens_path,
        default=model_path.parent / "tokens.txt",
        flag_name="--voice-tokens",
        env_name="KAIVRA_SHERPA_TOKENS",
        description="Sherpa tokens file",
    )
    data_dir = _resolve_required_path(
        provided=config.data_dir,
        default=model_path.parent / "espeak-ng-data",
        flag_name="--voice-data-dir",
        env_name="KAIVRA_SHERPA_DATA_DIR",
        description="Sherpa data directory",
    )
    lexicon_path = _resolve_optional_existing_path(
        config.lexicon_path,
        default=model_path.parent / "lexicon.txt",
    )

    return _ResolvedSherpaConfig(
        binary_path=binary_path,
        model_path=model_path,
        tokens_path=tokens_path,
        data_dir=data_dir,
        lexicon_path=lexicon_path,
        rule_fsts=config.rule_fsts,
        speaker_id=config.speaker_id,
        speed=config.speed,
        pad_seconds=config.pad_seconds,
    )
def _run_sherpa_tts(
    text: str,
    output_path: Path,
    config: _ResolvedSherpaConfig,
    *,
    python_tts=None,
) -> None:
    if config.binary_path is None:
        _run_sherpa_python_tts(text, output_path, config, python_tts=python_tts)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        config.binary_path,
        f"--vits-model={config.model_path}",
        f"--vits-tokens={config.tokens_path}",
        f"--vits-data-dir={config.data_dir}",
        f"--sid={config.speaker_id}",
        f"--speed={config.speed}",
        f"--output-filename={output_path}",
    ]
    if config.lexicon_path is not None:
        cmd.append(f"--vits-lexicon={config.lexicon_path}")
    if config.rule_fsts:
        cmd.append(f"--tts-rule-fsts={config.rule_fsts}")
    cmd.append(text)

    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Sherpa local TTS failed (exit {proc.returncode}):\n{proc.stderr}")
    if not output_path.exists():
        raise RuntimeError(
            "Sherpa local TTS completed without writing audio. "
            "Check the selected model and voice binary."
        )


def _run_sherpa_python_tts(
    text: str,
    output_path: Path,
    config: _ResolvedSherpaConfig,
    *,
    python_tts,
) -> None:
    if python_tts is None:
        python_tts = _build_python_tts(config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated = python_tts.generate(text, sid=config.speaker_id, speed=config.speed)

    try:
        import sherpa_onnx
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Sherpa Python module is not installed. Install the local voice extra first."
        ) from exc

    ok = sherpa_onnx.write_wave(str(output_path), generated.samples, generated.sample_rate)
    if not ok:
        raise RuntimeError("Sherpa Python TTS generated audio but failed to write the WAV file.")


def _build_python_tts(config: _ResolvedSherpaConfig):
    try:
        import sherpa_onnx
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Could not find the Sherpa Python package. "
            "Install it with `python -m pip install -e '.[local-voice]'`."
        ) from exc

    vits = sherpa_onnx.OfflineTtsVitsModelConfig(
        model=str(config.model_path),
        tokens=str(config.tokens_path),
        data_dir=str(config.data_dir),
        lexicon=str(config.lexicon_path or ""),
    )
    model = sherpa_onnx.OfflineTtsModelConfig(vits=vits)
    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=model,
        rule_fsts=config.rule_fsts or "",
    )
    if not tts_config.validate():
        raise RuntimeError("Sherpa local TTS config is invalid. Check the selected model assets.")
    return sherpa_onnx.OfflineTts(tts_config)


def _resolve_binary(binary_name: str) -> str | None:
    candidate = Path(binary_name).expanduser()
    if candidate.exists():
        return str(candidate)

    resolved = shutil.which(binary_name)
    if resolved:
        return resolved

    return None


def _resolve_model_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    path = path.expanduser()
    if not path.exists():
        raise ValueError(f"Sherpa model path does not exist: {path}")
    if path.is_file():
        return path

    candidates = sorted(path.glob("*.onnx"))
    if len(candidates) == 1:
        return candidates[0]

    preferred = path / "model.onnx"
    if preferred.exists():
        return preferred

    raise ValueError(
        f"Sherpa model directory {path} must contain exactly one .onnx file or a model.onnx file."
    )


def _resolve_required_path(
    *,
    provided: Path | None,
    default: Path,
    flag_name: str,
    env_name: str,
    description: str,
) -> Path:
    path = _resolve_optional_existing_path(provided, default=default)
    if path is not None:
        return path
    raise ValueError(
        f"Could not find {description}. Pass {flag_name} or set {env_name}."
    )


def _resolve_optional_existing_path(path: Path | None, *, default: Path | None = None) -> Path | None:
    candidate = (path or default)
    if candidate is None:
        return None
    candidate = candidate.expanduser()
    if candidate.exists():
        return candidate
    if path is not None:
        raise ValueError(f"Configured Sherpa asset path does not exist: {candidate}")
    return None


def _option_or_env_path(value: str | None, env_name: str) -> Path | None:
    raw = value or os.getenv(env_name)
    if not raw:
        return None
    return Path(raw).expanduser()


def _option_or_env_int(value: int | None, env_name: str, *, default: int) -> int:
    if value is not None:
        return value
    raw = os.getenv(env_name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer.") from exc


def _option_or_env_float(value: float | None, env_name: str, *, default: float) -> float:
    if value is not None:
        return value
    raw = os.getenv(env_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a number.") from exc


def _authored_scene_duration_seconds(scene) -> float:
    payload = scene.model_dump(mode="json", by_alias=True, exclude_none=True)
    return estimate_scene_duration(payload)


def _normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = " ".join(text.split())
    return normalized or None


def _slugify(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "_" for ch in value]
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "scene"


def _read_wav_metadata(path: Path) -> tuple[_WaveFormat, float]:
    with wave.open(str(path), "rb") as reader:
        fmt = _WaveFormat.from_reader(reader)
        duration = reader.getnframes() / fmt.sample_rate
    return fmt, duration


def _copy_wav_with_padding(
    source_path: Path,
    output_path: Path,
    target_duration_seconds: float,
    fmt: _WaveFormat,
) -> None:
    with wave.open(str(source_path), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
        nframes = reader.getnframes()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as writer:
        _apply_wave_format(writer, fmt)
        writer.writeframes(frames)
        target_frames = max(nframes, int(round(target_duration_seconds * fmt.sample_rate)))
        padding_frames = max(0, target_frames - nframes)
        if padding_frames:
            writer.writeframes(_silence_bytes(padding_frames, fmt))


def _write_silence_wav(path: Path, duration_seconds: float, fmt: _WaveFormat) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(0, int(round(duration_seconds * fmt.sample_rate)))
    with wave.open(str(path), "wb") as writer:
        _apply_wave_format(writer, fmt)
        if frame_count:
            writer.writeframes(_silence_bytes(frame_count, fmt))


def _concatenate_wav_files(paths: list[Path], output_path: Path, fmt: _WaveFormat) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as writer:
        _apply_wave_format(writer, fmt)
        for path in paths:
            with wave.open(str(path), "rb") as reader:
                clip_format = _WaveFormat.from_reader(reader)
                if clip_format != fmt:
                    raise RuntimeError("Cannot concatenate WAV files with different formats.")
                writer.writeframes(reader.readframes(reader.getnframes()))


def _apply_wave_format(writer: wave.Wave_write, fmt: _WaveFormat) -> None:
    writer.setnchannels(fmt.channels)
    writer.setsampwidth(fmt.sample_width)
    writer.setframerate(fmt.sample_rate)
    writer.setcomptype(fmt.compression_type, fmt.compression_name)


def _silence_bytes(frame_count: int, fmt: _WaveFormat) -> bytes:
    bytes_per_frame = fmt.channels * fmt.sample_width
    return b"\x00" * frame_count * bytes_per_frame
