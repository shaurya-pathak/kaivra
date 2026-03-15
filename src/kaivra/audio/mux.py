"""Mux external audio onto rendered animation videos."""

from __future__ import annotations

import subprocess

__all__ = ["mux_audio"]


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
