"""Utilities for retiming a document against externally supplied audio metadata.

The retimer keeps the existing structure of a scene, but rescales animation
timestamps so the scene breathes with real audio durations and explicit cue
windows provided by the caller.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping

from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming
from kaivra.dsl.pacing import (
    document_has_narration,
    get_pacing_profile,
    resolve_meta_duration,
    scene_has_narration,
)
from kaivra.dsl.schema import parse_duration

EMPHASIS_ACTIONS = {"highlight", "pulse"}
REVEAL_ACTIONS = {"appear", "fade-in", "draw", "type", "replace"}
MIN_CUE_DURATION_SECONDS = 0.45
MIN_EMPHASIS_DURATION_SECONDS = 0.28
MIN_REVEAL_DURATION_SECONDS = 0.24
BROAD_EMPHASIS_FRACTION = 0.45
REVEAL_CUE_FRACTION = 0.72


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
    target_content: str = ""


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

        source_duration = estimate_scene_duration(scene, meta=retimed.get("meta"))
        target_duration = max(source_duration, float(timing.duration_seconds))
        scale = 1.0 if source_duration <= 0 else target_duration / source_duration
        scene_scales.append(scale)

        _retime_scene(scene, scale)
        if align_audio_cues and timing.cues:
            content_index = _build_content_index(
                scene.get("objects"),
                retimed.get("objects"),
            )
            _align_scene_events_to_cues(
                scene,
                list(timing.cues),
                persistent_ids,
                scene_duration=target_duration,
                content_index=content_index,
            )
        scene["duration"] = format_duration(target_duration)

    if not scene_scales:
        return retimed

    global_scale = median(scene_scales)
    meta = retimed.get("meta")
    include_narration = document_has_narration(retimed)
    if scale_meta and isinstance(meta, dict):
        for field_name in ("continuity_duration", "glow_release_padding"):
            resolved_value = resolve_meta_duration(
                meta,
                field_name,
                include_narration=include_narration,
            )
            meta[field_name] = format_duration(_parse_time(resolved_value, 0.0) * global_scale)

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
        align_audio_cues=False,
    )


def estimate_scene_duration(
    scene: Mapping[str, Any],
    *,
    meta: Mapping[str, Any] | None = None,
) -> float:
    """Estimate the effective duration of a scene in seconds."""
    raw_duration = scene.get("duration", "auto")
    if isinstance(raw_duration, str) and raw_duration != "auto":
        return parse_duration(raw_duration)

    max_end = 5.0
    for anim in scene.get("animations", []) or []:
        max_end = max(max_end, _estimate_animation_end(anim))

    focus_style = scene.get("focus_style")
    if isinstance(focus_style, dict):
        default_focus_duration = 1.2
        if meta is not None:
            profile = get_pacing_profile(
                meta.get("pacing"),
                include_narration=scene_has_narration(scene)
                or bool(meta.get("show_subtitles", meta.get("show_narration"))),
            )
            default_focus_duration = profile.focus_seconds
        start = _parse_time(focus_style.get("at"), 0.0)
        duration = _parse_time(focus_style.get("duration"), default_focus_duration)
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


def _align_scene_events_to_cues(
    scene: dict[str, Any],
    cues: list[AudioCue],
    persistent_ids: set[str],
    *,
    scene_duration: float,
    content_index: dict[str, str] | None = None,
) -> None:
    events = _collect_cue_aligned_events(
        scene,
        persistent_ids,
        scene_duration,
        content_index or {},
    )
    if not events:
        return

    matched_cues = _match_cues_to_events(cues, events)
    for event, cue in zip(events, matched_cues):
        if cue is None:
            continue
        if event.kind == "focus":
            _align_focus_style_to_cue(event.ref, cue)
        elif event.kind == "reveal":
            _align_reveal_to_cue(event.ref, cue)
        else:
            _align_animation_to_cue(event.ref, cue)


def _collect_cue_aligned_events(
    scene: Mapping[str, Any],
    persistent_ids: set[str],
    scene_duration: float,
    content_index: dict[str, str],
) -> list[_EmphasisEvent]:
    events: list[_EmphasisEvent] = []
    for idx, anim in enumerate(scene.get("animations", []) or []):
        if not isinstance(anim, dict):
            continue
        action = anim.get("action")
        targets = _normalize_targets(anim.get("target"))
        if action in EMPHASIS_ACTIONS:
            if not targets:
                continue
            duration = _parse_time(anim.get("duration"), 0.5)
            if scene_duration > 0 and duration >= scene_duration * BROAD_EMPHASIS_FRACTION:
                continue
            if all(target in persistent_ids for target in targets):
                continue
            event_kind = "animation"
        elif action in REVEAL_ACTIONS:
            if not targets:
                continue
            if all(target in persistent_ids for target in targets):
                continue
            event_kind = "reveal"
        else:
            continue

        target_content = _targets_to_content(targets, content_index)
        events.append(
            _EmphasisEvent(
                kind=event_kind,
                ref=anim,
                start=_parse_time(anim.get("at"), 0.0),
                scene_order=idx,
                target_content=target_content,
            )
        )

    focus_style = scene.get("focus_style")
    focus_target = scene.get("focus")
    if isinstance(focus_style, dict) and focus_target:
        focus_targets = _normalize_targets(focus_target)
        events.append(
            _EmphasisEvent(
                kind="focus",
                ref=focus_style,
                start=_parse_time(focus_style.get("at"), 0.0),
                scene_order=len(events) + 10_000,
                target_content=_targets_to_content(focus_targets, content_index),
            )
        )

    events.sort(key=lambda event: (event.start, event.scene_order))
    return events


def _match_cues_to_events(
    cues: list[AudioCue],
    events: list[_EmphasisEvent],
) -> list[AudioCue | None]:
    """Match cues to events using semantic content matching with positional fallback."""
    if not events:
        return []
    if not cues:
        return [None] * len(events)

    sorted_cues = sorted(cues, key=lambda c: c.start_seconds)
    result: list[AudioCue | None] = [None] * len(events)

    # Phase 1: Semantic matching — pair cues to events by content similarity.
    scores: list[tuple[float, int, int]] = []
    for ei, event in enumerate(events):
        for ci, cue in enumerate(sorted_cues):
            score = _semantic_score(cue.text or "", event.target_content)
            if score > 0:
                scores.append((score, ei, ci))

    scores.sort(key=lambda x: -x[0])
    used_events: set[int] = set()
    used_cues: set[int] = set()

    for score, ei, ci in scores:
        if ei not in used_events and ci not in used_cues:
            result[ei] = sorted_cues[ci]
            used_events.add(ei)
            used_cues.add(ci)

    # Phase 2: Positional fallback for events without a semantic match.
    unmatched = [i for i in range(len(events)) if i not in used_events]
    if unmatched:
        remaining = [c for ci, c in enumerate(sorted_cues) if ci not in used_cues]
        positional = _distribute_positionally(remaining, len(unmatched))
        for ue_idx, cue in zip(unmatched, positional):
            result[ue_idx] = cue

    return result


def _distribute_positionally(
    cues: list[AudioCue],
    count: int,
) -> list[AudioCue]:
    """Pick *count* evenly-spaced cues from the list, splitting if needed."""
    if count <= 0 or not cues:
        return []

    working = list(cues)
    while len(working) < count:
        split_index = max(range(len(working)), key=lambda idx: working[idx].duration_seconds)
        split_cue = working[split_index]
        if split_cue.duration_seconds < MIN_CUE_DURATION_SECONDS:
            break
        half = split_cue.duration_seconds / 2.0
        working[split_index : split_index + 1] = [
            AudioCue(
                start_seconds=split_cue.start_seconds,
                duration_seconds=half,
                text=split_cue.text,
                kind=split_cue.kind,
            ),
            AudioCue(
                start_seconds=split_cue.start_seconds + half,
                duration_seconds=half,
                text=split_cue.text,
                kind=split_cue.kind,
            ),
        ]

    if len(working) <= count:
        return working

    if count == 1:
        return [working[len(working) // 2]]

    matched: list[AudioCue] = []
    last_index = len(working) - 1
    for idx in range(count):
        cue_index = round(idx * last_index / (count - 1))
        matched.append(working[cue_index])
    return matched


def _align_animation_to_cue(anim: dict[str, Any], cue: AudioCue) -> None:
    """Snap the animation start to the cue, preserving authored duration."""
    anim["at"] = format_duration(max(0.0, cue.start_seconds))


def _align_reveal_to_cue(anim: dict[str, Any], cue: AudioCue) -> None:
    """Snap the reveal start to the cue, preserving authored duration."""
    anim["at"] = format_duration(max(0.0, cue.start_seconds))


def _align_focus_style_to_cue(focus_style: dict[str, Any], cue: AudioCue) -> None:
    focus_style["at"] = format_duration(max(0.0, cue.start_seconds))
    focus_style["duration"] = format_duration(max(0.5, cue.duration_seconds * 0.9))


def _normalize_targets(target: Any) -> list[str]:
    if isinstance(target, str):
        return [target]
    if isinstance(target, list):
        return [item for item in target if isinstance(item, str)]
    return []


def _build_content_index(
    *object_lists: list[dict[str, Any]] | None,
) -> dict[str, str]:
    """Map object id -> searchable text (id words, content, spoken aliases)."""
    index: dict[str, str] = {}
    for obj_list in object_lists:
        for obj in obj_list or []:
            if isinstance(obj, dict):
                _index_object(obj, index)
    return index


def _index_object(obj: dict[str, Any], index: dict[str, str]) -> None:
    obj_id = obj.get("id")
    if not isinstance(obj_id, str) or not obj_id:
        return
    content = obj.get("content", "")
    if not isinstance(content, str):
        content = ""
    spoken_forms = obj.get("spoken_forms")
    if isinstance(spoken_forms, list):
        aliases = " ".join(item for item in spoken_forms if isinstance(item, str))
    else:
        aliases = ""
    # Split camelCase / snake_case id into words for matching.
    id_words = re.sub(r"([a-z])([A-Z])", r"\1 \2", obj_id).replace("_", " ").replace("-", " ")
    index[obj_id] = f"{id_words} {content} {aliases}".lower().strip()
    for child in obj.get("children", []) or []:
        if isinstance(child, dict):
            _index_object(child, index)


def _targets_to_content(targets: list[str], content_index: dict[str, str]) -> str:
    parts = [content_index.get(t, t) for t in targets]
    return " ".join(parts).lower()


def _semantic_score(cue_text: str, target_content: str) -> float:
    """Score how well a cue's spoken text matches an animation target's content."""
    if not cue_text or not target_content:
        return 0.0
    cue_words = set(_normalize_for_match(cue_text).split())
    content_words = set(_normalize_for_match(target_content).split())
    if not cue_words or not content_words:
        return 0.0

    # Exact word overlap.
    overlap = cue_words & content_words
    if overlap:
        return float(len(overlap))

    # Substring match (e.g., "failure" ↔ "fail").
    for cw in cue_words:
        for tw in content_words:
            if len(cw) >= 3 and len(tw) >= 3 and (cw in tw or tw in cw):
                return 0.5
    return 0.0


def _normalize_for_match(text: str) -> str:
    text = re.sub(r"[-_/]", " ", text.lower())
    return re.sub(r"[^\w\s]", "", text).strip()


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


def _build_duration_only_timing_map(
    scene_durations: Mapping[str, float],
) -> dict[str, SceneAudioTiming]:
    return {
        scene_id: SceneAudioTiming(id=scene_id, duration_seconds=float(duration))
        for scene_id, duration in scene_durations.items()
    }
