"""Utilities for retiming a document against externally-derived scene durations.

This is useful for audio-first workflows where scene timing is known only after
TTS has been generated. The retimer keeps the existing structure of a scene, but
rescales animation timestamps so the scene breathes with the real narration.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from statistics import median
from typing import Any, Mapping

from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming
from kaivra.dsl.schema import parse_duration

EMPHASIS_ACTIONS = {"highlight", "pulse"}
MIN_CUE_DURATION_SECONDS = 0.45
MIN_EMPHASIS_DURATION_SECONDS = 0.28
BROAD_EMPHASIS_FRACTION = 0.45


def format_duration(seconds: float) -> str:
    """Format seconds as a DSL duration string."""
    value = max(0.0, float(seconds))
    if value == 0:
        return "0s"
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text}s"


@dataclass
class _EmphasisEvent:
    kind: str
    ref: dict[str, Any]
    start: float
    scene_order: int


def retime_document_to_audio_timings(
    document: Mapping[str, Any],
    audio_timings: AudioTimingData,
    *,
    scale_meta: bool = True,
    scale_persistent_objects: bool = True,
    align_audio_cues: bool = True,
) -> dict[str, Any]:
    """Return a copy of ``document`` retimed to external audio metadata."""
    retimed = deepcopy(document)
    scenes = retimed.get("scenes", [])
    if not scenes:
        return retimed

    persistent_ids = _collect_object_ids(retimed.get("objects", []))
    scene_scales: list[float] = []
    for scene in scenes:
        scene_id = scene.get("id")
        if not scene_id:
            continue

        timing = audio_timings.scenes.get(scene_id)
        if timing is None:
            continue

        target_duration = max(0.0, float(timing.duration_seconds))
        source_duration = estimate_scene_duration(scene)
        scale = 1.0 if source_duration <= 0 else target_duration / source_duration
        scene_scales.append(scale)

        _retime_scene(scene, scale)
        if align_audio_cues:
            cues = list(timing.cues) or _infer_narration_cues(scene, target_duration, persistent_ids)
            if cues:
                _align_scene_emphasis_to_cues(scene, cues, persistent_ids, scene_duration=target_duration)
        scene["duration"] = format_duration(target_duration)

    if not scene_scales:
        return retimed

    global_scale = median(scene_scales)
    meta = retimed.get("meta")
    if scale_meta and isinstance(meta, dict):
        _scale_duration_field(meta, "continuity_duration", global_scale)
        _scale_duration_field(meta, "glow_release_padding", global_scale)

    if scale_persistent_objects:
        for obj in retimed.get("objects", []):
            _retime_object(obj, global_scale)

    return retimed


def retime_document_to_scene_durations(
    document: Mapping[str, Any],
    scene_durations: Mapping[str, float],
    *,
    scale_meta: bool = True,
    scale_persistent_objects: bool = True,
) -> dict[str, Any]:
    """Return a copy of ``document`` with scene timings scaled to new durations.

    ``scene_durations`` maps scene IDs to their new duration in seconds.
    Scenes not present in the mapping are left unchanged.
    """
    timing_data = AudioTimingData(scenes=_build_duration_only_timing_map(scene_durations))
    return retime_document_to_audio_timings(
        document,
        timing_data,
        scale_meta=scale_meta,
        scale_persistent_objects=scale_persistent_objects,
        align_audio_cues=True,
    )


def estimate_scene_duration(scene: Mapping[str, Any]) -> float:
    """Estimate the effective duration of a scene in seconds."""
    raw_duration = scene.get("duration", "auto")
    if isinstance(raw_duration, str) and raw_duration != "auto":
        return parse_duration(raw_duration)

    max_end = 5.0
    for anim in scene.get("animations", []) or []:
        max_end = max(max_end, _estimate_animation_end(anim))

    for anim in scene.get("camera_animations", []) or []:
        start = _parse_time(anim.get("at"), 0.0)
        duration = _parse_time(anim.get("duration"), 1.0)
        max_end = max(max_end, start + duration)

    focus_style = scene.get("focus_style")
    if isinstance(focus_style, dict):
        start = _parse_time(focus_style.get("at"), 0.0)
        duration = _parse_time(focus_style.get("duration"), 1.2)
        max_end = max(max_end, start + duration)

    for obj in scene.get("objects", []) or []:
        max_end = max(max_end, _estimate_object_end(obj))

    transition = scene.get("transition")
    if isinstance(transition, dict):
        max_end += _parse_time(transition.get("duration"), 0.5)

    return max_end


def _retime_scene(scene: dict[str, Any], scale: float) -> None:
    for anim in scene.get("animations", []) or []:
        _retime_animation(anim, scale)

    for anim in scene.get("camera_animations", []) or []:
        _scale_duration_field(anim, "at", scale)
        _scale_duration_field(anim, "duration", scale)

    focus_style = scene.get("focus_style")
    if isinstance(focus_style, dict):
        _scale_duration_field(focus_style, "at", scale)
        _scale_duration_field(focus_style, "duration", scale)

    transition = scene.get("transition")
    if isinstance(transition, dict):
        _scale_duration_field(transition, "duration", scale)

    for obj in scene.get("objects", []) or []:
        _retime_object(obj, scale)


def _retime_animation(anim: dict[str, Any], scale: float) -> None:
    _scale_duration_field(anim, "at", scale)
    _scale_duration_field(anim, "duration", scale)
    _scale_duration_field(anim, "stagger", scale)

    for phase in anim.get("phases", []) or []:
        _scale_duration_field(phase, "at", scale)
        _scale_duration_field(phase, "duration", scale)
        _scale_duration_field(phase, "stagger", scale)


def _retime_object(obj: dict[str, Any], scale: float) -> None:
    for key in ("enter", "exit", "idle"):
        motion = obj.get(key)
        if isinstance(motion, dict):
            _scale_duration_field(motion, "at", scale)
            _scale_duration_field(motion, "duration", scale)

    for child in obj.get("children", []) or []:
        _retime_object(child, scale)


def _estimate_animation_end(anim: Mapping[str, Any]) -> float:
    start = _parse_time(anim.get("at"), 0.0)
    duration = _parse_time(anim.get("duration"), 0.5)
    stagger = _parse_time(anim.get("stagger"), 0.0)

    target = anim.get("target")
    n_targets = len(target) if isinstance(target, list) else 1
    end = start + duration + stagger * max(0, n_targets - 1)

    for phase in anim.get("phases", []) or []:
        phase_start = _parse_time(phase.get("at"), 0.0)
        phase_duration = _parse_time(phase.get("duration"), 1.0)
        phase_stagger = _parse_time(phase.get("stagger"), 0.0)
        end = max(end, phase_start + phase_duration + phase_stagger * max(0, n_targets - 1))

    return end


def _estimate_object_end(obj: Mapping[str, Any]) -> float:
    max_end = 0.0
    for key, default_duration in (("enter", 0.6), ("exit", 0.6), ("idle", 0.6)):
        motion = obj.get(key)
        if not isinstance(motion, dict):
            continue
        start = _parse_time(motion.get("at"), 0.0)
        duration = _parse_time(motion.get("duration"), default_duration)
        max_end = max(max_end, start + duration)

    for child in obj.get("children", []) or []:
        max_end = max(max_end, _estimate_object_end(child))

    return max_end


def _scale_duration_field(obj: dict[str, Any], field: str, scale: float) -> None:
    value = obj.get(field)
    if value is None:
        return
    obj[field] = format_duration(_parse_time(value, 0.0) * scale)


def _parse_time(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return parse_duration(value)
    raise TypeError(f"Unsupported time value: {value!r}")


def _align_scene_emphasis_to_cues(
    scene: dict[str, Any],
    cues: list[AudioCue],
    persistent_ids: set[str],
    *,
    scene_duration: float,
) -> None:
    events = _collect_emphasis_events(scene, persistent_ids, scene_duration)
    if not events:
        return

    matched_cues = _match_cues_to_events(cues, len(events), scene_duration)
    for event, cue in zip(events, matched_cues):
        if event.kind == "focus":
            _align_focus_style_to_cue(event.ref, cue)
        else:
            _align_animation_to_cue(event.ref, cue)


def _collect_emphasis_events(
    scene: Mapping[str, Any],
    persistent_ids: set[str],
    scene_duration: float,
) -> list[_EmphasisEvent]:
    events: list[_EmphasisEvent] = []
    for idx, anim in enumerate(scene.get("animations", []) or []):
        if not isinstance(anim, dict):
            continue
        action = anim.get("action")
        if action not in EMPHASIS_ACTIONS:
            continue
        targets = _normalize_targets(anim.get("target"))
        if not targets:
            continue

        duration = _parse_time(anim.get("duration"), 0.5)
        if scene_duration > 0 and duration >= scene_duration * BROAD_EMPHASIS_FRACTION:
            continue
        if all(target in persistent_ids for target in targets):
            continue

        events.append(
            _EmphasisEvent(
                kind="animation",
                ref=anim,
                start=_parse_time(anim.get("at"), 0.0),
                scene_order=idx,
            )
        )

    focus_style = scene.get("focus_style")
    focus_target = scene.get("focus")
    if isinstance(focus_style, dict) and focus_target:
        events.append(
            _EmphasisEvent(
                kind="focus",
                ref=focus_style,
                start=_parse_time(focus_style.get("at"), 0.0),
                scene_order=len(events) + 10_000,
            )
        )

    events.sort(key=lambda event: (event.start, event.scene_order))
    return events


def _match_cues_to_events(cues: list[AudioCue], event_count: int, scene_duration: float) -> list[AudioCue]:
    if event_count <= 0:
        return []

    if not cues:
        return _fallback_even_cues(scene_duration, event_count)

    working = list(sorted(cues, key=lambda cue: cue.start_seconds))
    while len(working) < event_count:
        split_index = max(range(len(working)), key=lambda idx: working[idx].duration_seconds)
        split_cue = working[split_index]
        if split_cue.duration_seconds < MIN_CUE_DURATION_SECONDS:
            break

        half = split_cue.duration_seconds / 2.0
        working[split_index : split_index + 1] = [
            AudioCue(start_seconds=split_cue.start_seconds, duration_seconds=half, text=split_cue.text, kind=split_cue.kind),
            AudioCue(start_seconds=split_cue.start_seconds + half, duration_seconds=half, text=split_cue.text, kind=split_cue.kind),
        ]

    if len(working) < event_count:
        return _fallback_even_cues(scene_duration, event_count)

    if len(working) == event_count:
        return working

    if event_count == 1:
        return [working[len(working) // 2]]

    matched: list[AudioCue] = []
    last_index = len(working) - 1
    for idx in range(event_count):
        cue_index = round(idx * last_index / (event_count - 1))
        matched.append(working[cue_index])
    return matched


def _align_animation_to_cue(anim: dict[str, Any], cue: AudioCue) -> None:
    start = max(0.0, cue.start_seconds)
    targets = _normalize_targets(anim.get("target"))
    target_count = max(1, len(targets))
    original_duration = _parse_time(anim.get("duration"), 0.5)
    original_stagger = _parse_time(anim.get("stagger"), 0.0)
    original_total = original_duration + original_stagger * max(0, target_count - 1)

    target_total = max(MIN_CUE_DURATION_SECONDS, cue.duration_seconds * 0.84)
    scale = target_total / original_total if original_total > 0 else 1.0

    anim["at"] = format_duration(start)
    anim["duration"] = format_duration(max(MIN_EMPHASIS_DURATION_SECONDS, original_duration * scale))
    if "stagger" in anim or original_stagger > 0:
        anim["stagger"] = format_duration(max(0.0, original_stagger * scale))


def _align_focus_style_to_cue(focus_style: dict[str, Any], cue: AudioCue) -> None:
    focus_style["at"] = format_duration(max(0.0, cue.start_seconds))
    focus_style["duration"] = format_duration(max(0.5, cue.duration_seconds * 0.9))


def _infer_narration_cues(scene: Mapping[str, Any], scene_duration: float, persistent_ids: set[str]) -> list[AudioCue]:
    events = _collect_emphasis_events(scene, persistent_ids, scene_duration)
    event_count = len(events)
    if event_count <= 0:
        return []

    narration = scene.get("narration")
    if not isinstance(narration, str):
        return []

    text = " ".join(narration.split())
    if not text:
        return []

    phrases = _split_narration_into_phrases(text)
    if not phrases:
        return _fallback_even_cues(scene_duration, event_count)

    if len(phrases) < event_count:
        phrases = _split_into_even_word_chunks(text, event_count)

    phrase_windows = _phrases_to_cues(phrases, scene_duration)
    return _match_cues_to_events(phrase_windows, event_count, scene_duration)


def _split_narration_into_phrases(text: str) -> list[str]:
    parts = [segment.strip(" ,") for segment in re.split(r"\s*(?:[.!?]+|[;:])\s*|\s+[—–-]\s+", text) if segment.strip(" ,")]
    if len(parts) <= 1:
        comma_parts = [segment.strip() for segment in re.split(r"\s*,\s*", text) if segment.strip()]
        if len(comma_parts) > 1:
            return comma_parts
    return parts


def _split_into_even_word_chunks(text: str, chunk_count: int) -> list[str]:
    words = text.split()
    if chunk_count <= 1 or len(words) <= 1:
        return [text]

    chunk_size = max(1, round(len(words) / chunk_count))
    chunks: list[str] = []
    for idx in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[idx : idx + chunk_size]))

    while len(chunks) > chunk_count:
        right = chunks.pop()
        chunks[-1] = f"{chunks[-1]} {right}".strip()

    return [chunk for chunk in chunks if chunk]


def _phrases_to_cues(phrases: list[str], scene_duration: float) -> list[AudioCue]:
    if not phrases:
        return []

    lead_in = min(0.8, scene_duration * 0.08)
    tail = min(1.0, scene_duration * 0.1)
    active_duration = max(scene_duration - lead_in - tail, scene_duration * 0.65)

    word_counts = [max(1, len(phrase.split())) for phrase in phrases]
    total_words = sum(word_counts)

    cues: list[AudioCue] = []
    cursor = lead_in
    for phrase, word_count in zip(phrases, word_counts):
        phrase_duration = active_duration * (word_count / total_words)
        cues.append(
            AudioCue(
                start_seconds=cursor,
                duration_seconds=max(0.5, phrase_duration),
                text=phrase,
                kind="phrase",
            )
        )
        cursor += phrase_duration
    return cues


def _fallback_even_cues(scene_duration: float, count: int) -> list[AudioCue]:
    if count <= 0:
        return []

    lead_in = min(0.7, scene_duration * 0.08)
    tail = min(0.9, scene_duration * 0.1)
    active = max(scene_duration - lead_in - tail, scene_duration * 0.6)
    step = active / max(1, count)
    span = max(0.45, step * 0.8)
    return [
        AudioCue(
            start_seconds=lead_in + idx * step,
            duration_seconds=min(
                span,
                max(MIN_CUE_DURATION_SECONDS, scene_duration - (lead_in + idx * step)),
            ),
        )
        for idx in range(count)
    ]


def _normalize_targets(target: Any) -> list[str]:
    if isinstance(target, str):
        return [target]
    if isinstance(target, list):
        return [item for item in target if isinstance(item, str)]
    return []


def _collect_object_ids(objects: list[dict[str, Any]] | None) -> set[str]:
    result: set[str] = set()
    for obj in objects or []:
        if not isinstance(obj, dict):
            continue
        obj_id = obj.get("id")
        if isinstance(obj_id, str) and obj_id:
            result.add(obj_id)
        children = obj.get("children")
        if isinstance(children, list):
            result.update(_collect_object_ids(children))
    return result


def _build_duration_only_timing_map(scene_durations: Mapping[str, float]) -> dict[str, SceneAudioTiming]:
    return {
        scene_id: SceneAudioTiming(id=scene_id, duration_seconds=float(duration))
        for scene_id, duration in scene_durations.items()
    }
