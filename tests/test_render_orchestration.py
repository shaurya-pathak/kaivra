from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from kaivra.audio.base import AudioResult
from kaivra.audio.timings import AudioCue
from kaivra.dsl.parser import parse_string
from kaivra.render import orchestration
from kaivra.render.web.exporter import build_web_preview_html


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
                cues=(
                    AudioCue(
                        start_seconds=0.2,
                        duration_seconds=0.4,
                        text="Hello",
                        kind="word",
                    ),
                ),
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

    def fake_prepend(_input_path: str, output_path: str, seconds: float) -> None:
        steps.append(("leadin", Path(output_path).name, seconds))
        Path(output_path).write_bytes(b"wav+silence")

    def fake_append(_input_path: str, output_path: str, seconds: float) -> None:
        steps.append(("pad", Path(output_path).name, seconds))
        Path(output_path).write_bytes(b"wav+tail")

    def fake_build_render_graph(_doc, **_kwargs):
        steps.append(("retime", _doc.meta.show_subtitles, [scene.id for scene in _doc.scenes]))
        timing_data = _kwargs.get("audio_timing_data")
        if timing_data is not None:
            steps.append(
                (
                    "cues",
                    len(timing_data.scenes["intro"].cues),
                    timing_data.scenes["intro"].cues[0].text
                    if timing_data.scenes["intro"].cues
                    else None,
                )
            )
        return (
            SimpleNamespace(
                total_duration=7.4,
                scenes=[
                    SimpleNamespace(id="__kaivra_video_intro__", duration=2.25),
                    SimpleNamespace(id="intro", duration=2.9),
                    SimpleNamespace(id="__kaivra_video_outro__", duration=2.25),
                ],
            ),
            object(),
        )

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
    monkeypatch.setattr(orchestration, "prepend_silence_to_wav", fake_prepend)
    monkeypatch.setattr(orchestration, "append_silence_to_wav", fake_append)
    monkeypatch.setattr(
        orchestration,
        "measure_audio_duration",
        lambda path: 2.9 if "intro_leadin" in Path(path).name else 2.25,
    )
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
    assert result.duration_seconds == 7.4
    assert result.retimed_document_path == str(tmp_path / "narrated.retimed.json")
    assert Path(result.retimed_document_path).exists()
    assert ("provider", "dummy") in steps
    assert ("generate", "__kaivra_video_intro__", "voice-123") in steps
    assert ("generate", "intro", "voice-123") in steps
    assert ("generate", "__kaivra_video_outro__", "voice-123") in steps
    assert (
        "retime",
        False,
        ["__kaivra_video_intro__", "intro", "__kaivra_video_outro__"],
    ) in steps
    assert ("normalize", ".mp3", ".wav") in steps
    assert ("leadin", "narrated_intro_leadin.wav", 0.65) in steps
    assert ("cues", 1, "Hello") in steps
    assert ("concat", [".wav", ".wav", ".wav"], ".wav") in steps
    assert ("mux", ".wav", ".mp4") in steps
    assert not [step for step in steps if step[0] == "pad"]
    assert "Discovering voice provider: dummy." in progress_messages
    assert "Generating voice for scene intro." in progress_messages
    assert "Normalizing audio for scene intro." in progress_messages
    assert "Rendering a silent video." in progress_messages
    assert "Concatenating narration audio." in progress_messages
    assert "Muxing narration onto the rendered video." in progress_messages

    retimed = json.loads(Path(result.retimed_document_path).read_text(encoding="utf-8"))
    assert retimed["scenes"][0]["id"] == "__kaivra_video_intro__"
    # Bookend scenes keep their authored duration when TTS audio is shorter.
    assert retimed["scenes"][0]["duration"] == "3.8s"
    assert retimed["scenes"][1]["duration"] == "3.45s"
    assert retimed["scenes"][-1]["id"] == "__kaivra_video_outro__"
    assert retimed["scenes"][-1]["duration"] == "3.4s"


def test_openai_voice_pipeline_uses_scene_level_timing_without_word_cues(tmp_path, monkeypatch):
    doc = _narrated_doc()
    raw_audio = tmp_path / "intro.wav"
    raw_audio.write_bytes(b"raw")
    captured_cue_counts: list[int] = []

    class DummyProvider:
        def generate(self, scene_id: str, _text: str, **kwargs) -> AudioResult:
            return AudioResult(
                audio_path=str(raw_audio),
                duration_seconds=1.0,
                scene_id=scene_id,
                cues=(),
            )

    class DummyRegistry:
        def discover(self) -> None:
            return None

        def get(self, name: str):
            assert name == "openai"
            return DummyProvider

    def fake_normalize(_input_path: str, output_path: str) -> None:
        Path(output_path).write_bytes(b"wav")

    def fake_prepend(_input_path: str, output_path: str, _seconds: float) -> None:
        Path(output_path).write_bytes(b"wav+silence")

    def fake_build_render_graph(_doc, **kwargs):
        timing_data = kwargs.get("audio_timing_data")
        if timing_data is not None:
            captured_cue_counts.append(len(timing_data.scenes["intro"].cues))
        return (
            SimpleNamespace(
                total_duration=6.75,
                scenes=[
                    SimpleNamespace(id="__kaivra_video_intro__", duration=2.25),
                    SimpleNamespace(id="intro", duration=2.25),
                    SimpleNamespace(id="__kaivra_video_outro__", duration=2.25),
                ],
            ),
            object(),
        )

    monkeypatch.setattr(orchestration, "ProviderRegistry", DummyRegistry)
    monkeypatch.setattr(orchestration, "validate_voice_provider_setup", lambda provider: provider)
    monkeypatch.setattr(orchestration, "normalize_audio_to_wav", fake_normalize)
    monkeypatch.setattr(orchestration, "prepend_silence_to_wav", fake_prepend)
    monkeypatch.setattr(orchestration, "append_silence_to_wav", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestration, "measure_audio_duration", lambda _path: 2.25)
    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestration, "concat_audio", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestration, "mux_audio", lambda *_args, **_kwargs: None)

    orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "narrated.mp4",
        voice=True,
        voice_provider="openai",
    )

    assert captured_cue_counts == [0]


def test_voice_pipeline_pads_audio_to_match_retimed_video_duration(tmp_path, monkeypatch):
    doc = _narrated_doc()
    raw_audio = tmp_path / "intro.wav"
    raw_audio.write_bytes(b"raw")
    padded_calls: list[tuple[str, float]] = []

    class DummyProvider:
        def generate(self, scene_id: str, _text: str, **_kwargs) -> AudioResult:
            return AudioResult(
                audio_path=str(raw_audio),
                duration_seconds=3.0,
                scene_id=scene_id,
                cues=(),
            )

    class DummyRegistry:
        def discover(self) -> None:
            return None

        def get(self, _name: str):
            return DummyProvider

    def fake_normalize(_input_path: str, output_path: str) -> None:
        Path(output_path).write_bytes(b"wav")

    def fake_prepend(_input_path: str, output_path: str, _seconds: float) -> None:
        Path(output_path).write_bytes(b"wav+silence")

    def fake_append(_input_path: str, output_path: str, seconds: float) -> None:
        padded_calls.append((Path(output_path).name, seconds))
        Path(output_path).write_bytes(b"wav+padded")

    def fake_measure(path: str) -> float:
        name = Path(path).name
        if "intro_padded" in name:
            return 15.0
        if "intro_leadin" in name:
            return 3.2
        return 3.0

    def fake_build_render_graph(_doc, **_kwargs):
        return (
            SimpleNamespace(
                total_duration=21.8,
                scenes=[
                    SimpleNamespace(id="__kaivra_video_intro__", duration=3.4),
                    SimpleNamespace(id="intro", duration=15.0),
                    SimpleNamespace(id="__kaivra_video_outro__", duration=3.4),
                ],
            ),
            object(),
        )

    monkeypatch.setattr(orchestration, "ProviderRegistry", DummyRegistry)
    monkeypatch.setattr(orchestration, "validate_voice_provider_setup", lambda provider: provider)
    monkeypatch.setattr(orchestration, "normalize_audio_to_wav", fake_normalize)
    monkeypatch.setattr(orchestration, "prepend_silence_to_wav", fake_prepend)
    monkeypatch.setattr(orchestration, "append_silence_to_wav", fake_append)
    monkeypatch.setattr(orchestration, "measure_audio_duration", fake_measure)
    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestration, "concat_audio", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestration, "mux_audio", lambda *_args, **_kwargs: None)

    orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "narrated.mp4",
        voice=True,
        voice_provider="local",
    )

    assert any(
        name == "narrated_intro_padded.wav" and abs(seconds - 11.8) < 1e-6
        for name, seconds in padded_calls
    )


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


def test_video_bookends_include_narration(tmp_path, monkeypatch):
    doc = _narrated_doc()
    captured_narration: list[tuple[str, str | None]] = []

    def fake_build_render_graph(_doc, **_kwargs):
        captured_narration.extend((scene.id, scene.narration) for scene in _doc.scenes)
        return SimpleNamespace(total_duration=4.6), object()

    def fake_export_video(_graph, _theme, output_path: str, **kwargs) -> None:
        callback = kwargs.get("progress_callback")
        if callback is not None:
            callback(1, 1)
        Path(output_path).write_bytes(b"video")

    monkeypatch.setattr(orchestration, "build_render_graph", fake_build_render_graph)
    monkeypatch.setattr(orchestration, "export_video", fake_export_video)

    orchestration.render_document_artifact(
        doc,
        output_path=tmp_path / "silent.mp4",
    )

    assert captured_narration[0] == (
        "__kaivra_video_intro__",
        "Welcome. In this video, we'll walk through Narrated step by step.",
    )
    assert captured_narration[-1] == (
        "__kaivra_video_outro__",
        "That's the full walkthrough of Narrated. Thanks for watching.",
    )


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


def test_elevenlabs_voice_render_preserves_explicit_subtitles_setting(tmp_path, monkeypatch):
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
        voice_provider="elevenlabs",
    )

    assert result.artifact_path == str(tmp_path / "narrated.mp4")
    assert seen_subtitles == [True]


def test_local_voice_render_forces_subtitles_off_and_spokenizes_narration(tmp_path, monkeypatch):
    seen: list[tuple[bool, str | None]] = []

    monkeypatch.setattr(
        orchestration,
        "_render_with_voice",
        lambda _doc, **_kwargs: (
            seen.append((_doc.meta.show_subtitles, _doc.scenes[1].narration))
            or orchestration.RenderArtifact(
                artifact_path=str(tmp_path / "narrated.mp4"),
                duration_seconds=1.0,
            )
        ),
    )

    local_doc = parse_string(
        json.dumps(
            {
                "version": "1.3",
                "meta": {"title": "Narrated", "theme": "modern", "show_subtitles": True},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "3s",
                        "narration": "GET /users/42: fetch profile & settings",
                        "objects": [{"id": "title", "type": "text", "content": "Narrated"}],
                        "animations": [{"action": "appear", "target": "title", "at": "0s"}],
                    }
                ],
            }
        ),
        format="json",
    )

    result = orchestration.render_document_artifact(
        local_doc,
        output_path=tmp_path / "narrated.mp4",
        voice=True,
        voice_provider="local",
    )

    assert result.artifact_path == str(tmp_path / "narrated.mp4")
    assert seen == [(False, "GET slash users slash 42. fetch profile and settings.")]


def test_web_preview_html_includes_transition_and_highlight_preview_logic() -> None:
    doc = parse_string(
        json.dumps(
            {
                "version": "1.3",
                "meta": {"title": "Preview", "theme": "modern"},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "4s",
                        "narration": "Preview parity",
                        "objects": [{"id": "box", "type": "box", "content": "Box"}],
                        "animations": [
                            {"action": "highlight", "target": "box", "at": "0s", "duration": "2s"}
                        ],
                        "transition": {"type": "fade", "duration": "0.5s"},
                    },
                    {
                        "id": "next",
                        "duration": "2s",
                        "objects": [{"id": "next_box", "type": "box", "content": "Next"}],
                    },
                ],
            }
        ),
        format="json",
    )

    html = build_web_preview_html(doc)

    assert "return { scene, sceneIndex: index, localTime, blend, nextScene, nextLocalTime }" in html
    assert "if (blend > 0 && nextScene)" in html
    assert "if (progress < 0.25) return progress / 0.25;" in html
    assert "drawHighlight(ctx, node);" in html


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
                "version": "1.3",
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
