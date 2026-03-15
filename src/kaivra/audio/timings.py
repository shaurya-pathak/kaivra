"""Load generic audio timing sidecars for animation retiming."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kaivra.dsl.schema import parse_duration

__all__ = [
    "AudioCue",
    "SceneAudioTiming",
    "AudioTimingData",
    "load_audio_timing_data",
    "load_audio_timings",
]


@dataclass(frozen=True)
class AudioCue:
    """A cue window within a scene's narration."""

    start_seconds: float
    duration_seconds: float
    text: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class SceneAudioTiming:
    """Timing metadata for a single scene."""

    id: str
    duration_seconds: float
    cues: tuple[AudioCue, ...] = ()


@dataclass(frozen=True)
class AudioTimingData:
    """Timing metadata for a whole document."""

    scenes: dict[str, SceneAudioTiming]

    def scene_durations(self) -> dict[str, float]:
        return {scene_id: timing.duration_seconds for scene_id, timing in self.scenes.items()}


def load_audio_timing_data(path: str | Path) -> AudioTimingData:
    """Load full timing data from a JSON sidecar.

    Supported shapes:
    - {"scenes": [{"id": "scene_id", "duration_seconds": 12.3, "cues": [...]}, ...]}
    - {"scenes": [{"id": "scene_id", "duration": "12.3s", "cues": [...]}, ...]}
    - {"scene_durations": {"scene_id": 12.3, ...}}

    Cue shapes:
    - {"start_seconds": 1.2, "duration_seconds": 0.9}
    - {"start_seconds": 1.2, "end_seconds": 2.1}
    - {"at": "1.2s", "duration": "0.9s"}
    - {"start": 1.2, "end": 2.1}
    """
    raw = _read_json_object(path)

    if "scene_durations" in raw:
        durations = _load_scene_duration_map(raw["scene_durations"])
        return AudioTimingData(
            scenes={
                scene_id: SceneAudioTiming(id=scene_id, duration_seconds=duration)
                for scene_id, duration in durations.items()
            }
        )
    if "scenes" in raw:
        return AudioTimingData(scenes=_load_scene_list(raw["scenes"]))

    raise ValueError("Audio timings file must contain 'scenes' or 'scene_durations'.")


def load_audio_timings(path: str | Path) -> dict[str, float]:
    """Backward-compatible loader that returns only scene durations."""
    return load_audio_timing_data(path).scene_durations()


def _load_scene_duration_map(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError("'scene_durations' must be an object mapping scene IDs to durations.")

    result: dict[str, float] = {}
    for scene_id, duration in raw.items():
        if not isinstance(scene_id, str) or not scene_id:
            raise ValueError("Scene IDs in 'scene_durations' must be non-empty strings.")
        result[scene_id] = _coerce_duration_seconds(duration, field=f"scene_durations.{scene_id}")
    return result


def _load_scene_list(raw: object) -> dict[str, SceneAudioTiming]:
    if not isinstance(raw, list):
        raise ValueError("'scenes' must be a list of scene timing objects.")

    result: dict[str, SceneAudioTiming] = {}
    for idx, scene in enumerate(raw):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene timing at index {idx} must be an object.")
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise ValueError(f"Scene timing at index {idx} is missing a valid 'id'.")

        if "duration_seconds" in scene:
            duration = _coerce_duration_seconds(scene["duration_seconds"], field=f"scenes[{idx}].duration_seconds")
        elif "duration" in scene:
            duration = _coerce_duration_seconds(scene["duration"], field=f"scenes[{idx}].duration")
        else:
            raise ValueError(f"Scene timing for {scene_id!r} must include 'duration_seconds' or 'duration'.")

        cues = _load_cues(scene.get("cues"), field=f"scenes[{idx}].cues")
        result[scene_id] = SceneAudioTiming(
            id=scene_id,
            duration_seconds=duration,
            cues=tuple(sorted(cues, key=lambda cue: cue.start_seconds)),
        )
    return result


def _load_cues(raw: object, *, field: str) -> list[AudioCue]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a list of cue objects.")

    cues: list[AudioCue] = []
    for idx, cue in enumerate(raw):
        if not isinstance(cue, dict):
            raise ValueError(f"{field}[{idx}] must be an object.")

        start = _coerce_optional_seconds(
            cue.get("start_seconds", cue.get("at", cue.get("start"))),
            field=f"{field}[{idx}].start",
        )
        if start is None:
            raise ValueError(f"{field}[{idx}] must include 'start_seconds', 'at', or 'start'.")

        duration_value = cue.get("duration_seconds", cue.get("duration"))
        end_value = cue.get("end_seconds", cue.get("end"))
        if duration_value is not None:
            duration = _coerce_duration_seconds(duration_value, field=f"{field}[{idx}].duration")
        elif end_value is not None:
            end = _coerce_duration_seconds(end_value, field=f"{field}[{idx}].end")
            duration = end - start
            if duration <= 0:
                raise ValueError(f"{field}[{idx}] end must be greater than start.")
        else:
            raise ValueError(f"{field}[{idx}] must include 'duration_seconds'/'duration' or 'end_seconds'/'end'.")

        text = cue.get("text")
        if text is not None and not isinstance(text, str):
            raise ValueError(f"{field}[{idx}].text must be a string when provided.")

        kind = cue.get("kind")
        if kind is not None and not isinstance(kind, str):
            raise ValueError(f"{field}[{idx}].kind must be a string when provided.")

        cues.append(AudioCue(start_seconds=start, duration_seconds=duration, text=text, kind=kind))
    return cues


def _coerce_duration_seconds(value: object, *, field: str) -> float:
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        seconds = parse_duration(value)
    else:
        raise ValueError(f"{field} must be a number of seconds or a duration string like '12.3s'.")

    if seconds <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return seconds


def _coerce_optional_seconds(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        seconds = parse_duration(value)
    else:
        raise ValueError(f"{field} must be a number of seconds or a duration string like '1.2s'.")

    if seconds < 0:
        raise ValueError(f"{field} must be zero or greater.")
    return seconds


def _read_json_object(path: str | Path) -> dict:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Audio timings file must be a JSON object.")
    return raw
