from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from kaivra.audio.base import AudioResult
from kaivra.dsl.parser import parse_string
from kaivra.render import orchestration


def test_render_document_artifact_voice_pipeline_normalizes_and_concats_wav(tmp_path, monkeypatch):
    doc = _narrated_doc()
    raw_audio = tmp_path / "intro.mp3"
    raw_audio.write_bytes(b"raw")
    steps: list[tuple[object, ...]] = []
    progress_messages: list[str] = []

    class DummyProvider:
        def generate(self, scene_id: str, _text: str, **kwargs) -> AudioResult:
            steps.append(("generate", scene_id, kwargs.get("voice_id")))
            return AudioResult(
                audio_path=str(raw_audio),
                duration_seconds=1.0,
                scene_id=scene_id,
            )

    class DummyRegistry:
        def discover(self) -> None:
            steps.append(("discover",))

        def get(self, name: str):
            steps.append(("provider", name))
            return DummyProvider

    def fake_normalize(input_path: str, output_path: str) -> None:
        steps.append(("normalize", Path(input_path).suffix, Path(output_path).suffix))
        Path(output_path).write_bytes(b"wav")

    def fake_build_render_graph(_doc, **_kwargs):
        steps.append(("retime", _doc.meta.show_subtitles, [scene.id for scene in _doc.scenes]))
        return SimpleNamespace(total_duration=2.25), object()

    def fake_export_video(_graph, _theme, output_path: str, **kwargs) -> None:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(1, 1)
        Path(output_path).write_bytes(b"video")

    def fake_concat(audio_paths: list[str], output_path: str) -> None:
        steps.append(
            ("concat", [Path(path).suffix for path in audio_paths], Path(output_path).suffix)
        )
        Path(output_path).write_bytes(b"concat")

    def fake_mux(_video_path: str, audio_path: str, output_path: str) -> None:
        steps.append(("mux", Path(audio_path).suffix, Path(output_path).suffix))
        Path(output_path).write_bytes(b"final")

    monkeypatch.setattr(orchestration, "ProviderRegistry", DummyRegistry)
    monkeypatch.setattr(orchestration, "normalize_audio_to_wav", fake_normalize)
    monkeypatch.setattr(orchestration, "measure_audio_duration", lambda _path: 2.25)
    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", fake_export_video)
    monkeypatch.setattr(orchestration, "concat_audio", fake_concat)
    monkeypatch.setattr(orchestration, "mux_audio", fake_mux)

    result = orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "narrated.mp4",
        voice=True,
        voice_provider="dummy",
        voice_id="voice-123",
        progress=lambda _value, message: progress_messages.append(message),
    )

    assert result.artifact_path == str(tmp_path / "narrated.mp4")
    assert result.duration_seconds == 2.25
    assert result.retimed_document_path == str(tmp_path / "narrated.retimed.json")
    assert Path(result.retimed_document_path).exists()
    assert ("provider", "dummy") in steps
    assert ("generate", "intro", "voice-123") in steps
    assert (
        "retime",
        False,
        ["__kaivra_video_intro__", "intro", "__kaivra_video_outro__"],
    ) in steps
    assert ("normalize", ".mp3", ".wav") in steps
    assert ("concat", [".wav", ".wav", ".wav"], ".wav") in steps
    assert ("mux", ".wav", ".mp4") in steps
    assert "Discovering voice provider: dummy." in progress_messages
    assert "Generating voice for scene intro." in progress_messages
    assert "Normalizing audio for scene intro." in progress_messages
    assert "Rendering a silent video." in progress_messages
    assert "Concatenating narration audio." in progress_messages
    assert "Muxing narration onto the rendered video." in progress_messages

    retimed = json.loads(Path(result.retimed_document_path).read_text(encoding="utf-8"))
    assert retimed["scenes"][0]["id"] == "__kaivra_video_intro__"
    assert retimed["scenes"][1]["duration"] == "2.25s"
    assert retimed["scenes"][-1]["id"] == "__kaivra_video_outro__"


def test_video_render_injects_intro_and_outro_bookends(tmp_path, monkeypatch):
    doc = _narrated_doc()
    seen_scene_ids: list[list[str]] = []

    def fake_build_render_graph(_doc, **_kwargs):
        seen_scene_ids.append([scene.id for scene in _doc.scenes])
        return SimpleNamespace(total_duration=4.6), object()

    def fake_export_video(_graph, _theme, output_path: str, **kwargs) -> None:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(1, 1)
        Path(output_path).write_bytes(b"video")

    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", fake_export_video)

    result = orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "silent.mp4",
    )

    assert result.artifact_path == str(tmp_path / "silent.mp4")
    assert seen_scene_ids == [["__kaivra_video_intro__", "intro", "__kaivra_video_outro__"]]


def test_video_render_can_disable_bookends_via_meta(tmp_path, monkeypatch):
    doc = _narrated_doc(video_bookends=False)
    seen_scene_ids: list[list[str]] = []

    def fake_build_render_graph(_doc, **_kwargs):
        seen_scene_ids.append([scene.id for scene in _doc.scenes])
        return SimpleNamespace(total_duration=1.0), object()

    def fake_export_video(_graph, _theme, output_path: str, **kwargs) -> None:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(1, 1)
        Path(output_path).write_bytes(b"video")

    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", fake_export_video)

    result = orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "silent.mp4",
    )

    assert result.artifact_path == str(tmp_path / "silent.mp4")
    assert seen_scene_ids == [["intro"]]


def test_resolve_theme_search_roots_prefers_nearest_ancestor_theme_dir(tmp_path):
    workspace = tmp_path / "workspace"
    docs_dir = workspace / "animations" / "nested"
    docs_dir.mkdir(parents=True)
    (workspace / "themes").mkdir()

    cwd = tmp_path / "cwd"
    (cwd / "themes").mkdir(parents=True)

    roots = orchestration.resolve_theme_search_roots(
        docs_dir / "demo.json",
        cwd=cwd,
    )

    assert roots == [workspace / "themes", cwd / "themes"]


def test_voice_render_preserves_explicit_subtitles_setting(tmp_path, monkeypatch):
    doc = _narrated_doc(show_subtitles=True)
    seen_subtitles: list[bool] = []

    monkeypatch.setattr(
        orchestration,
        "_render_with_voice",
        lambda _doc, **_kwargs: (
            seen_subtitles.append(_doc.meta.show_subtitles)
            or orchestration.RenderArtifact(
                artifact_path=str(tmp_path / "narrated.mp4"),
                duration_seconds=1.0,
            )
        ),
    )

    result = orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "narrated.mp4",
        voice=True,
        voice_provider="dummy",
    )

    assert result.artifact_path == str(tmp_path / "narrated.mp4")
    assert seen_subtitles == [True]


def _narrated_doc(
    *,
    show_subtitles: bool | None = None,
    legacy_show_narration: bool | None = None,
    video_bookends: bool | None = None,
):
    meta = {"title": "Narrated", "theme": "modern"}
    if show_subtitles is not None:
        meta["show_subtitles"] = show_subtitles
    if legacy_show_narration is not None:
        meta["show_narration"] = legacy_show_narration
    if video_bookends is not None:
        meta["video_bookends"] = video_bookends

    return parse_string(
        json.dumps(
            {
                "version": "1.1",
                "meta": meta,
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "1s",
                        "narration": "Hello there.",
                        "objects": [{"type": "text", "content": "Hello"}],
                    }
                ],
            }
        ),
        format="json",
    )
