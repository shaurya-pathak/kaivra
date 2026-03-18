"""Shared pacing profiles for starter generation and runtime defaults."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from kaivra.dsl.schema import PacingPreset


def format_duration(seconds: float) -> str:
    """Format seconds as a DSL duration string."""
    value = max(0.0, float(seconds))
    if value == 0:
        return "0s"
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text}s"


@dataclass(frozen=True)
class PacingProfile:
    """Canonical timing defaults for a pacing preset."""

    preset: PacingPreset
    scene_min_seconds: int
    scene_max_seconds: int
    scene_base_seconds: int
    scene_words_per_step: int
    continuity_seconds: float
    focus_seconds: float
    highlight_seconds: float
    scale_seconds: float

    @property
    def continuity_duration(self) -> str:
        return format_duration(self.continuity_seconds)

    @property
    def focus_duration(self) -> str:
        return format_duration(self.focus_seconds)

    @property
    def highlight_duration(self) -> str:
        return format_duration(self.highlight_seconds)

    @property
    def scale_duration(self) -> str:
        return format_duration(self.scale_seconds)

    @property
    def glow_release_padding(self) -> str:
        # Leave enough tail time for a glow envelope to fade before scene end.
        return format_duration(self.highlight_seconds / 2.0)

    def scene_duration_seconds(self, word_count: int) -> int:
        """Resolve a scene duration from authored beat text length."""
        return min(
            self.scene_max_seconds,
            max(
                self.scene_min_seconds,
                self.scene_base_seconds + round(max(0, word_count) / self.scene_words_per_step),
            ),
        )

    def scene_duration(self, word_count: int) -> str:
        return format_duration(self.scene_duration_seconds(word_count))


PACING_PROFILES: dict[PacingPreset, PacingProfile] = {
    PacingPreset.QUICK_DEMO: PacingProfile(
        preset=PacingPreset.QUICK_DEMO,
        scene_min_seconds=5,
        scene_max_seconds=8,
        scene_base_seconds=4,
        scene_words_per_step=5,
        continuity_seconds=0.6,
        focus_seconds=1.0,
        highlight_seconds=1.6,
        scale_seconds=0.8,
    ),
    PacingPreset.BALANCED: PacingProfile(
        preset=PacingPreset.BALANCED,
        scene_min_seconds=6,
        scene_max_seconds=10,
        scene_base_seconds=5,
        scene_words_per_step=4,
        continuity_seconds=0.9,
        focus_seconds=1.2,
        highlight_seconds=2.0,
        scale_seconds=1.0,
    ),
    PacingPreset.EDUCATIONAL: PacingProfile(
        preset=PacingPreset.EDUCATIONAL,
        scene_min_seconds=8,
        scene_max_seconds=16,
        scene_base_seconds=6,
        scene_words_per_step=3,
        continuity_seconds=1.3,
        focus_seconds=1.4,
        highlight_seconds=2.8,
        scale_seconds=1.2,
    ),
}


def resolve_pacing_preset(
    pacing: str | PacingPreset | None,
    *,
    include_narration: bool,
) -> PacingPreset:
    """Resolve a pacing preset, including narration-aware defaults."""
    if isinstance(pacing, PacingPreset):
        return pacing
    if isinstance(pacing, str) and pacing.strip():
        return PacingPreset(pacing.strip())
    return PacingPreset.EDUCATIONAL if include_narration else PacingPreset.BALANCED


def get_pacing_profile(
    pacing: str | PacingPreset | None,
    *,
    include_narration: bool,
) -> PacingProfile:
    """Return the canonical profile for a pacing value."""
    preset = resolve_pacing_preset(pacing, include_narration=include_narration)
    return PACING_PROFILES[preset]


def resolve_meta_duration(
    meta: BaseModel | Mapping[str, Any] | None,
    field_name: str,
    *,
    include_narration: bool | None = None,
) -> str:
    """Resolve a pacing-aware duration field from meta, honoring explicit values."""
    profile = get_pacing_profile(
        _get_field(meta, "pacing"),
        include_narration=_coerce_bool(
            include_narration
            if include_narration is not None
            else _get_field(meta, "show_subtitles")
        ),
    )
    default_value = getattr(profile, field_name)

    if meta is None:
        return default_value

    if isinstance(meta, BaseModel):
        if field_name in meta.model_fields_set:
            value = getattr(meta, field_name, None)
            return value or default_value
        return default_value

    value = meta.get(field_name)
    if isinstance(value, str) and value:
        return value
    return default_value


def _get_field(meta: BaseModel | Mapping[str, Any] | None, field_name: str) -> Any:
    if meta is None:
        return None
    if isinstance(meta, BaseModel):
        return getattr(meta, field_name, None)
    if field_name == "show_subtitles":
        return meta.get("show_subtitles", meta.get("show_narration"))
    return meta.get(field_name)


def scene_has_narration(scene: BaseModel | Mapping[str, Any] | None) -> bool:
    """Return whether a scene includes authored narration text."""
    if scene is None:
        return False
    if isinstance(scene, BaseModel):
        return bool(getattr(scene, "narration", None))
    return bool(scene.get("narration"))


def document_has_narration(document: BaseModel | Mapping[str, Any] | None) -> bool:
    """Return whether any scene in a document includes narration text."""
    if document is None:
        return False
    if isinstance(document, BaseModel):
        scenes = getattr(document, "scenes", None) or []
    else:
        scenes = document.get("scenes", []) or []
    return any(scene_has_narration(scene) for scene in scenes)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return bool(value)
