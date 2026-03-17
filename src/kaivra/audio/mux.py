"""Mux external audio onto rendered animation videos."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

__all__ = ["concat_audio", "mux_audio"]


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
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        *audio_codec,
        "-af", "apad",
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


def concat_audio(audio_paths: list[str], output_path: str) -> None:
    """Concatenate multiple audio files in order using ffmpeg concat demuxer."""
    if not audio_paths:
        raise ValueError("No audio files to concatenate")

    if len(audio_paths) == 1:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(audio_paths[0], output_path)
        return

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="kaivra_concat_"
    ) as f:
        for path in audio_paths:
            f.write(f"file '{path}'\n")
        list_path = f.name

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
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
                f"ffmpeg concat failed (exit {proc.returncode}):\n{proc.stderr}"
            )
    finally:
        Path(list_path).unlink(missing_ok=True)
