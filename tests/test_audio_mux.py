from __future__ import annotations

import subprocess
import wave
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


def test_concat_audio_writes_absolute_paths_into_concat_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    audio_a = tmp_path / "a.wav"
    audio_b = tmp_path / "b.wav"
    audio_a.write_bytes(b"a")
    audio_b.write_bytes(b"b")
    manifests: list[str] = []

    def fake_run(cmd, **_kwargs):
        manifest_path = Path(cmd[7])
        manifests.append(manifest_path.read_text(encoding="utf-8"))
        Path(cmd[-1]).write_bytes(b"concat")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mux.subprocess, "run", fake_run)

    mux.concat_audio([str(audio_a), str(audio_b)], str(tmp_path / "joined.wav"))

    assert manifests
    assert f"file '{audio_a.resolve()}'" in manifests[0]
    assert f"file '{audio_b.resolve()}'" in manifests[0]


def test_concat_audio_copies_single_file_without_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "single.wav"
    source.write_bytes(b"one")
    copied: list[tuple[str, str]] = []

    monkeypatch.setattr(
        mux.shutil,
        "copy2",
        lambda src, dst: (
            copied.append((src, str(dst))) or Path(dst).write_bytes(Path(src).read_bytes())
        ),
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


def test_prepend_silence_to_wav_increases_duration_and_preserves_audio(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    output = tmp_path / "prefixed.wav"

    with wave.open(str(source), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(10)
        wf.writeframes(b"\x01\x00" * 4)

    mux.prepend_silence_to_wav(str(source), str(output), 0.3)

    with wave.open(str(output), "rb") as wf:
        assert wf.getframerate() == 10
        assert wf.getnframes() == 7
        frames = wf.readframes(7)

    assert frames[:6] == b"\x00" * 6
    assert frames[6:] == b"\x01\x00" * 4
