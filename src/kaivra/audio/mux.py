"""Mux external audio onto rendered animation videos."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

__all__ = [
    "append_silence_to_wav",
    "concat_audio",
    "measure_audio_duration",
    "mux_audio",
    "normalize_audio_to_wav",
    "prepend_silence_to_wav",
]


def mux_audio(video_path: str, audio_path: str, output_path: str) -> None:
    """Mux audio onto an existing rendered video.

    The output keeps the full video duration by padding short audio with silence,
    and trims long audio to the video length.
    """
    if output_path.endswith(".webm"):
        audio_codec = ["-c:a", "libopus", "-b:a", "128k"]
    else:
        audio_codec = ["-c:a", "aac", "-b:a", "192k"]

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "copy",
        *audio_codec,
        "-af",
        "apad",
        "-shortest",
        output_path,
    ]

    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio mux failed (exit {proc.returncode}):\n{proc.stderr}")


def normalize_audio_to_wav(input_path: str, output_path: str) -> None:
    """Re-encode audio to a canonical mono WAV for concat safety."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        output_path,
    ]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg WAV normalization failed (exit {proc.returncode}):\n{proc.stderr}"
        )


def measure_audio_duration(path: str) -> float:
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
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed (exit {proc.returncode}):\n{proc.stderr}")
    return float(proc.stdout.strip())


def concat_audio(audio_paths: list[str], output_path: str) -> None:
    """Concatenate multiple audio files in order using ffmpeg concat demuxer."""
    if not audio_paths:
        raise ValueError("No audio files to concatenate")

    if len(audio_paths) == 1:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio_paths[0], output_path)
        return

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="kaivra_concat_"
    ) as f:
        for path in audio_paths:
            f.write(f"file '{Path(path).resolve()}'\n")
        list_path = f.name

    try:
        codec_args = ["-c:a", "pcm_s16le"] if output_path.endswith(".wav") else ["-c", "copy"]
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            *codec_args,
            output_path,
        ]
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed (exit {proc.returncode}):\n{proc.stderr}")
    finally:
        Path(list_path).unlink(missing_ok=True)


def prepend_silence_to_wav(input_path: str, output_path: str, seconds: float) -> None:
    """Write a WAV with leading silence inserted before the source audio."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if seconds <= 0:
        shutil.copy2(input_path, output_path)
        return

    with wave.open(input_path, "rb") as source:
        frame_rate = source.getframerate()
        if frame_rate <= 0:
            raise RuntimeError(f"Generated WAV has invalid sample rate: {frame_rate}")
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        silence_frames = int(round(seconds * frame_rate))
        silence = b"\x00" * silence_frames * channels * sample_width

        with wave.open(output_path, "wb") as target:
            target.setparams(source.getparams())
            target.writeframes(silence)
            while True:
                chunk = source.readframes(4096)
                if not chunk:
                    break
                target.writeframes(chunk)


def append_silence_to_wav(input_path: str, output_path: str, seconds: float) -> None:
    """Write a WAV with trailing silence appended after the source audio."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if seconds <= 0:
        shutil.copy2(input_path, output_path)
        return

    with wave.open(input_path, "rb") as source:
        frame_rate = source.getframerate()
        if frame_rate <= 0:
            raise RuntimeError(f"Generated WAV has invalid sample rate: {frame_rate}")
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        silence_frames = int(round(seconds * frame_rate))
        silence = b"\x00" * silence_frames * channels * sample_width

        with wave.open(output_path, "wb") as target:
            target.setparams(source.getparams())
            while True:
                chunk = source.readframes(4096)
                if not chunk:
                    break
                target.writeframes(chunk)
            target.writeframes(silence)
