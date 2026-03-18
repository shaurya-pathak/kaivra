from __future__ import annotations

import subprocess
from pathlib import Path

from kaivra.audio import mux


def test_concat_audio_writes_wav_with_pcm_codec(tmp_path: Path, monkeypatch) -> None:
    audio_a = tmp_path / "a.wav"
    audio_b = tmp_path / "b.wav"
    audio_a.write_bytes(b"a")
    audio_b.write_bytes(b"b")
    commands: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        Path(cmd[-1]).write_bytes(b"concat")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mux.subprocess, "run", fake_run)

    mux.concat_audio([str(audio_a), str(audio_b)], str(tmp_path / "joined.wav"))

    assert commands
    assert ["-c:a", "pcm_s16le"] == commands[0][8:10]
    assert commands[0][-1].endswith("joined.wav")


def test_concat_audio_copies_single_file_without_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "single.wav"
    source.write_bytes(b"one")
    copied: list[tuple[str, str]] = []

    monkeypatch.setattr(
        mux.shutil,
        "copy2",
        lambda src, dst: copied.append((src, str(dst))) or Path(dst).write_bytes(Path(src).read_bytes()),
    )

    mux.concat_audio([str(source)], str(tmp_path / "single-copy.wav"))

    assert copied == [(str(source), str(tmp_path / "single-copy.wav"))]


def test_mux_audio_uses_output_codec_for_mp4_and_webm(tmp_path: Path, monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mux.subprocess, "run", fake_run)

    mux.mux_audio("video.mp4", "audio.wav", str(tmp_path / "out.mp4"))
    mux.mux_audio("video.webm", "audio.wav", str(tmp_path / "out.webm"))

    assert ["-c:a", "aac", "-b:a", "192k"] == commands[0][8:12]
    assert ["-c:a", "libopus", "-b:a", "128k"] == commands[1][8:12]
