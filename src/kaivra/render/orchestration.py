"""Shared render orchestration used by the CLI and MCP flows."""

from __future__ import annotations

import json
import tempfile
import wave
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaivra.audio.base import ProviderRegistry, resolve_voice_provider_name
from kaivra.audio.mux import (
    concat_audio,
    measure_audio_duration,
    mux_audio,
    normalize_audio_to_wav,
)
from kaivra.audio.timings import AudioTimingData, SceneAudioTiming, load_audio_timing_data
from kaivra.dsl.parser import parse_string
from kaivra.dsl.retime import retime_document_to_audio_timings
from kaivra.dsl.schema import parse_duration
from kaivra.render.cairo_renderer import CairoRenderer
from kaivra.render.video.exporter import export_video
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.themes.registry import get_theme

ProgressReporter = Callable[[float, str], None]
_VIDEO_INTRO_SCENE_ID = "__kaivra_video_intro__"
_VIDEO_OUTRO_SCENE_ID = "__kaivra_video_outro__"


@dataclass(frozen=True)
class RenderArtifact:
    """Outcome of rendering a Kaivra document."""

    artifact_path: str
    duration_seconds: float
    warnings: tuple[str, ...] = ()
    retimed_document_path: str | None = None


def render_document_artifact(
    doc: Any,
    *,
    output_path: str | Path,
    fps: int | None = None,
    audio_path: str | Path | None = None,
    audio_timings_path: str | Path | None = None,
    voice: bool = False,
    voice_provider: str | None = None,
    voice_id: str | None = None,
    theme_search_roots: Iterable[str | Path] | None = None,
    progress: ProgressReporter | None = None,
    log_video_progress: bool = False,
) -> RenderArtifact:
    """Render a document to PNG, MP4, or WebM with optional audio orchestration."""
    artifact_path = Path(output_path)
    chosen_format = artifact_path.suffix.lower()
    if chosen_format not in {".png", ".mp4", ".webm"}:
        raise ValueError("Output path must end with .png, .mp4, or .webm.")

    audio_abs = Path(audio_path) if audio_path is not None else None
    audio_timings_abs = Path(audio_timings_path) if audio_timings_path is not None else None
    render_fps = fps or doc.meta.fps

    if voice and (audio_abs or audio_timings_abs):
        raise ValueError("Voice renders cannot be combined with external audio or audio timings.")

    if chosen_format == ".png":
        if audio_abs or audio_timings_abs or voice:
            raise ValueError("PNG renders do not accept audio_path, audio_timings_path, or voice.")
        _emit_progress(progress, 0.2, "Building the first frame.")
        graph, theme = build_render_graph(doc, theme_search_roots=theme_search_roots)
        CairoRenderer(theme).render_frame_to_file(graph, 0.0, str(artifact_path))
        _emit_progress(progress, 1.0, "PNG render complete.")
        return RenderArtifact(
            artifact_path=str(artifact_path),
            duration_seconds=0.0,
        )

    doc = _apply_video_bookends(doc)

    if voice:
        doc = _apply_voice_subtitle_defaults(doc)
        return _render_with_voice(
            doc,
            output_path=artifact_path,
            fps=render_fps,
            voice_provider=voice_provider,
            voice_id=voice_id,
            theme_search_roots=theme_search_roots,
            progress=progress,
        )

    _emit_progress(progress, 0.1, "Preparing the scene graph.")
    graph, theme = build_render_graph(
        doc,
        audio_timings_path=audio_timings_abs,
        theme_search_roots=theme_search_roots,
    )

    def video_progress(done: int, total: int) -> None:
        if total <= 0:
            return
        _emit_progress(progress, 0.15 + (done / total) * 0.75, "Rendering video frames.")

    if audio_abs is not None:
        _emit_progress(progress, 0.15, "Rendering a silent video before muxing audio.")
        with tempfile.NamedTemporaryFile(
            prefix=f"{artifact_path.stem}_silent_",
            suffix=chosen_format,
            dir=artifact_path.parent,
            delete=False,
        ) as tmp:
            silent_path = Path(tmp.name)

        try:
            export_video(
                graph,
                theme,
                str(silent_path),
                fps=render_fps,
                log_progress=log_video_progress,
                progress_callback=video_progress,
            )
            _emit_progress(progress, 0.92, "Muxing the external audio track.")
            mux_audio(str(silent_path), str(audio_abs), str(artifact_path))
        finally:
            silent_path.unlink(missing_ok=True)
    else:
        export_video(
            graph,
            theme,
            str(artifact_path),
            fps=render_fps,
            log_progress=log_video_progress,
            progress_callback=video_progress,
        )

    _emit_progress(progress, 1.0, "Video render complete.")
    warnings: list[str] = []
    if audio_timings_abs is not None and audio_abs is None:
        warnings.append("Applied audio timings for pacing, but no audio track was attached.")

    retimed_document_path = None
    if audio_timings_abs is not None:
        retimed_document_path = _write_retimed_sidecar(
            doc,
            artifact_path,
            audio_timings_path=audio_timings_abs,
        )

    return RenderArtifact(
        artifact_path=str(artifact_path),
        duration_seconds=round(graph.total_duration, 2),
        warnings=tuple(warnings),
        retimed_document_path=retimed_document_path,
    )


def build_render_graph(
    doc: Any,
    audio_timings_path: str | Path | None = None,
    *,
    audio_timing_data: AudioTimingData | None = None,
    theme_search_roots: Iterable[str | Path] | None = None,
) -> tuple[Any, Any]:
    """Resolve the theme and build the scene graph, optionally retimed to audio."""
    if audio_timings_path is not None and audio_timing_data is not None:
        raise ValueError("Provide either audio_timings_path or audio_timing_data, not both.")

    if audio_timings_path is not None:
        audio_timing_data = load_audio_timing_data(audio_timings_path)

    if audio_timing_data is not None:
        doc = _retime_document(doc, audio_timing_data)

    theme = get_theme(doc.meta.theme, search_roots=theme_search_roots)
    graph = build_scene_graph(doc, theme)
    return graph, theme


def resolve_theme_search_roots(
    document_path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> list[Path]:
    """Find theme roots near a document path, with a cwd fallback."""
    path = Path(document_path).expanduser().resolve()
    search_start = path if path.is_dir() else path.parent

    roots: list[Path] = []
    for parent in (search_start, *search_start.parents):
        candidate = parent / "themes"
        if candidate.is_dir():
            roots.append(candidate)
            break

    fallback_root = Path(cwd or Path.cwd()).expanduser().resolve() / "themes"
    if fallback_root not in roots:
        roots.append(fallback_root)
    return roots


def _apply_voice_subtitle_defaults(doc: Any) -> Any:
    """Hide subtitles by default for voice renders unless the user opted in."""
    if doc.meta.subtitles_were_explicitly_set():
        return doc
    return doc.model_copy(
        update={
            "meta": doc.meta.model_copy(update={"show_subtitles": False}),
        }
    )


def _retime_document(doc: Any, audio_timing_data: AudioTimingData) -> Any:
    raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
    retimed = retime_document_to_audio_timings(raw_doc, audio_timing_data)
    return parse_string(json.dumps(retimed), format="json")


def _write_retimed_sidecar(
    doc: Any,
    output_path: Path,
    *,
    audio_timing_data: AudioTimingData | None = None,
    audio_timings_path: str | Path | None = None,
) -> str | None:
    if audio_timing_data is None and audio_timings_path is None:
        return None
    if audio_timing_data is None:
        audio_timing_data = load_audio_timing_data(audio_timings_path)

    retimed_doc = _retime_document(doc, audio_timing_data)
    sidecar_path = output_path.with_name(f"{output_path.stem}.retimed.json")
    sidecar_path.write_text(
        json.dumps(
            retimed_doc.model_dump(mode="json", by_alias=True, exclude_none=True),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(sidecar_path)


def _apply_video_bookends(doc: Any) -> Any:
    scene_ids = [scene.id for scene in getattr(doc, "scenes", []) if getattr(scene, "id", None)]
    if not getattr(doc, "scenes", None):
        return doc
    if _VIDEO_INTRO_SCENE_ID in scene_ids or _VIDEO_OUTRO_SCENE_ID in scene_ids:
        return doc

    raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
    if not doc.meta.subtitles_were_explicitly_set():
        raw_doc.get("meta", {}).pop("show_subtitles", None)
    raw_doc["scenes"] = [
        _intro_scene(raw_doc.get("meta", {}).get("title")),
        *raw_doc.get("scenes", []),
        _outro_scene(raw_doc.get("meta", {}).get("title")),
    ]
    return parse_string(json.dumps(raw_doc), format="json")


def _intro_scene(title: str | None) -> dict[str, Any]:
    resolved_title = (title or "Untitled Animation").strip() or "Untitled Animation"
    return {
        "id": _VIDEO_INTRO_SCENE_ID,
        "duration": "1.8s",
        "layout": "center",
        "auto_visible": False,
        "continuity": False,
        "transition": {"type": "fade", "duration": "0.45s"},
        "objects": [
            {
                "type": "group",
                "id": "__kaivra_intro_stack",
                "layout": {
                    "type": "stack",
                    "direction": "vertical",
                    "gap": "medium",
                    "align": "center",
                },
                "children": [
                    {"type": "token", "id": "__kaivra_intro_token", "content": "Walkthrough"},
                    {
                        "type": "text",
                        "id": "__kaivra_intro_title",
                        "content": resolved_title,
                        "style": "heading",
                    },
                    {
                        "type": "text",
                        "id": "__kaivra_intro_caption",
                        "content": "Let's get oriented before we dive in.",
                        "style": "caption",
                    },
                ],
            }
        ],
        "animations": [
            {
                "action": "fade-in",
                "target": "__kaivra_intro_token",
                "at": "0.1s",
                "duration": "0.45s",
            },
            {
                "action": "fade-in",
                "target": "__kaivra_intro_title",
                "at": "0.3s",
                "duration": "0.65s",
            },
            {
                "action": "fade-in",
                "target": "__kaivra_intro_caption",
                "at": "0.85s",
                "duration": "0.45s",
            },
        ],
    }


def _outro_scene(title: str | None) -> dict[str, Any]:
    resolved_title = (title or "Untitled Animation").strip() or "Untitled Animation"
    return {
        "id": _VIDEO_OUTRO_SCENE_ID,
        "duration": "1.8s",
        "layout": "center",
        "auto_visible": False,
        "continuity": False,
        "objects": [
            {
                "type": "group",
                "id": "__kaivra_outro_stack",
                "layout": {
                    "type": "stack",
                    "direction": "vertical",
                    "gap": "medium",
                    "align": "center",
                },
                "children": [
                    {"type": "token", "id": "__kaivra_outro_token", "content": "Complete"},
                    {
                        "type": "text",
                        "id": "__kaivra_outro_title",
                        "content": resolved_title,
                        "style": "heading",
                    },
                    {
                        "type": "text",
                        "id": "__kaivra_outro_caption",
                        "content": "You've reached the end of the walkthrough.",
                        "style": "caption",
                    },
                ],
            }
        ],
        "animations": [
            {
                "action": "fade-in",
                "target": "__kaivra_outro_token",
                "at": "0.1s",
                "duration": "0.45s",
            },
            {
                "action": "fade-in",
                "target": "__kaivra_outro_title",
                "at": "0.3s",
                "duration": "0.65s",
            },
            {
                "action": "fade-in",
                "target": "__kaivra_outro_caption",
                "at": "0.85s",
                "duration": "0.45s",
            },
        ],
    }


def _bookend_durations(doc: Any) -> tuple[float, float]:
    scenes = list(getattr(doc, "scenes", []))
    intro = (
        parse_duration(scenes[0].duration)
        if scenes and scenes[0].id == _VIDEO_INTRO_SCENE_ID
        else 0.0
    )
    outro = (
        parse_duration(scenes[-1].duration)
        if scenes and scenes[-1].id == _VIDEO_OUTRO_SCENE_ID
        else 0.0
    )
    return intro, outro


def _write_silence_wav(path: Path, duration_seconds: float) -> None:
    sample_rate = 44100
    frame_count = max(0, int(round(duration_seconds * sample_rate)))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def _render_with_voice(
    doc: Any,
    *,
    output_path: Path,
    fps: int,
    voice_provider: str | None,
    voice_id: str | None,
    theme_search_roots: Iterable[str | Path] | None,
    progress: ProgressReporter | None,
) -> RenderArtifact:
    registry = ProviderRegistry()
    provider_name = resolve_voice_provider_name(voice_provider)
    _emit_progress(progress, 0.05, f"Discovering voice provider: {provider_name}.")
    registry.discover()
    provider_cls = registry.get(provider_name)
    provider = provider_cls()

    narrated_scenes = [scene for scene in doc.scenes if scene.narration]
    if not narrated_scenes:
        raise ValueError("No scenes have narration text for voice generation.")

    generate_kwargs = {"voice_id": voice_id} if voice_id is not None else {}
    generated_paths: list[Path] = []
    normalized_paths: list[Path] = []
    scene_timings: dict[str, SceneAudioTiming] = {}
    intro_duration, outro_duration = _bookend_durations(doc)

    with tempfile.NamedTemporaryFile(
        prefix=f"{output_path.stem}_silent_",
        suffix=output_path.suffix,
        dir=output_path.parent,
        delete=False,
    ) as tmp:
        silent_path = Path(tmp.name)

    concat_path = output_path.with_suffix(".concat.wav")
    retimed_document_path: str | None = None

    try:
        if intro_duration > 0:
            intro_silence = output_path.with_name(f"{output_path.stem}_intro_silence.wav")
            _write_silence_wav(intro_silence, intro_duration)
            normalized_paths.append(intro_silence)

        for index, scene in enumerate(narrated_scenes, start=1):
            progress_value = 0.1 + (index / len(narrated_scenes)) * 0.25
            _emit_progress(progress, progress_value, f"Generating voice for scene {scene.id}.")
            result = provider.generate(scene.id, scene.narration, **generate_kwargs)
            generated_paths.append(Path(result.audio_path))

            normalized_path = output_path.with_name(f"{output_path.stem}_{scene.id}_narration.wav")
            _emit_progress(
                progress,
                0.38 + (index / len(narrated_scenes)) * 0.18,
                f"Normalizing audio for scene {scene.id}.",
            )
            normalize_audio_to_wav(result.audio_path, str(normalized_path))
            normalized_paths.append(normalized_path)

            scene_timings[scene.id] = SceneAudioTiming(
                id=scene.id,
                duration_seconds=measure_audio_duration(str(normalized_path)),
            )

        if outro_duration > 0:
            outro_silence = output_path.with_name(f"{output_path.stem}_outro_silence.wav")
            _write_silence_wav(outro_silence, outro_duration)
            normalized_paths.append(outro_silence)

        timing_data = AudioTimingData(scenes=scene_timings)
        _emit_progress(progress, 0.58, "Retiming the animation to narration.")
        retimed_document_path = _write_retimed_sidecar(
            doc,
            output_path,
            audio_timing_data=timing_data,
        )
        graph, theme = build_render_graph(
            doc,
            audio_timing_data=timing_data,
            theme_search_roots=theme_search_roots,
        )

        def video_progress(done: int, total: int) -> None:
            if total <= 0:
                return
            _emit_progress(progress, 0.62 + (done / total) * 0.22, "Rendering a silent video.")

        export_video(
            graph,
            theme,
            str(silent_path),
            fps=fps,
            log_progress=False,
            progress_callback=video_progress,
        )
        _emit_progress(progress, 0.88, "Concatenating narration audio.")
        concat_audio([str(path) for path in normalized_paths], str(concat_path))
        _emit_progress(progress, 0.95, "Muxing narration onto the rendered video.")
        mux_audio(str(silent_path), str(concat_path), str(output_path))
    finally:
        silent_path.unlink(missing_ok=True)
        concat_path.unlink(missing_ok=True)
        for path in {*generated_paths, *normalized_paths}:
            path.unlink(missing_ok=True)

    _emit_progress(progress, 1.0, "Narrated render complete.")
    return RenderArtifact(
        artifact_path=str(output_path),
        duration_seconds=round(graph.total_duration, 2),
        retimed_document_path=retimed_document_path,
    )


def _emit_progress(progress: ProgressReporter | None, value: float, message: str) -> None:
    if progress is None:
        return
    progress(value, message)
