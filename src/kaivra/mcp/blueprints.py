"""Starter blueprints for guided Kaivra authoring."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from kaivra.dsl.pacing import PacingProfile, format_duration, get_pacing_profile
from kaivra.dsl.parser import parse_string
from kaivra.dsl.schema import DocumentSpec, PacingPreset

DEFAULT_PATTERN = "algorithm_walkthrough"
DEFAULT_NARRATED_PATTERN = "visual_explainer"
SUPPORTED_PATTERNS = (
    "algorithm_walkthrough",
    "architecture_explainer",
    "before_after_comparison",
    "visual_explainer",
)
DEFAULT_THEME = "modern"


@dataclass(frozen=True)
class Beat:
    """Structured beat content used by the starter blueprints."""

    index: int
    slug: str
    title: str
    detail: str

    @property
    def label(self) -> str:
        return f"{self.index + 1}  {_truncate(self.title, 16)}"


def build_starter_document(
    *,
    title: str,
    pattern: str | None,
    beats: list[Any] | None,
    theme: str | None,
    audience: str | None,
    include_narration: bool,
    show_subtitles: bool | None = None,
    pacing: str | PacingPreset | None = None,
) -> DocumentSpec:
    """Build a valid Kaivra starter document for the requested pattern."""
    chosen_pattern = _normalize_pattern(
        pattern or _default_pattern(include_narration), include_narration
    )
    if chosen_pattern not in SUPPORTED_PATTERNS:
        supported = ", ".join(SUPPORTED_PATTERNS)
        raise ValueError(f"Unsupported pattern {chosen_pattern!r}. Choose one of: {supported}.")

    chosen_theme = (theme or DEFAULT_THEME).strip()
    if not chosen_theme:
        raise ValueError("Theme names cannot be empty.")

    parsed_beats = _coerce_beats(beats, title=title)
    pacing_profile = get_pacing_profile(pacing, include_narration=include_narration)
    subtitle_visibility = bool(show_subtitles) if show_subtitles is not None else False

    from kaivra.version import CURRENT_DSL_VERSION

    raw = {
        "version": CURRENT_DSL_VERSION,
        "meta": {
            "title": title,
            "resolution": [1920, 1080],
            "fps": 30,
            "theme": chosen_theme,
            "show_subtitles": subtitle_visibility,
            "pacing": pacing_profile.preset.value,
            "continuity": True,
            "continuity_duration": pacing_profile.continuity_duration,
            "glow_release_padding": pacing_profile.glow_release_padding,
        },
        "objects": _build_step_footer(parsed_beats),
        "scenes": _build_scenes(
            title=title,
            pattern=chosen_pattern,
            beats=parsed_beats,
            audience=audience,
            include_narration=include_narration,
            pacing_profile=pacing_profile,
        ),
    }
    return parse_string(json.dumps(raw), format="json")


def dump_document_json(doc: DocumentSpec) -> str:
    """Serialize a document in the normalized JSON shape we want on disk."""
    return json.dumps(
        doc.model_dump(mode="json", by_alias=True, exclude_none=True),
        indent=2,
    )


def infer_slug(title: str) -> str:
    """Build a filesystem-friendly slug from a title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return slug or "animation"


def _default_pattern(include_narration: bool) -> str:
    return DEFAULT_NARRATED_PATTERN if include_narration else DEFAULT_PATTERN


def _normalize_pattern(pattern: str, include_narration: bool) -> str:
    chosen_pattern = pattern.strip()
    if chosen_pattern == "process_explainer":
        return DEFAULT_NARRATED_PATTERN if include_narration else DEFAULT_PATTERN
    return chosen_pattern


def _coerce_beats(raw_beats: list[Any] | None, *, title: str) -> list[Beat]:
    items = raw_beats or [
        {"title": "The goal", "detail": title},
        {"title": "How it works", "detail": f"The core idea behind {title}."},
        {"title": "Why it matters", "detail": f"The key takeaway for {title}."},
    ]

    beats: list[Beat] = []
    for index, item in enumerate(items[:8]):
        beats.append(_coerce_beat(item, index=index))
    return beats


def _coerce_beat(item: Any, *, index: int) -> Beat:
    if isinstance(item, str):
        title, detail = _split_beat_text(item)
    elif isinstance(item, dict):
        raw_title = item.get("title") or item.get("name") or item.get("label")
        raw_detail = item.get("detail") or item.get("summary") or item.get("content")
        if raw_title is None and raw_detail is None:
            raise ValueError(f"Beat {index + 1} must include title/detail content.")
        if raw_title is None:
            title, detail = _split_beat_text(str(raw_detail))
        elif raw_detail is None:
            title, detail = _split_beat_text(str(raw_title))
        else:
            title = _clean_text(str(raw_title))
            detail = _clean_text(str(raw_detail))
    else:
        raise ValueError(f"Beat {index + 1} must be a string or object.")

    return Beat(
        index=index,
        slug=f"beat_{index + 1:02d}",
        title=title,
        detail=detail,
    )


def _split_beat_text(text: str) -> tuple[str, str]:
    cleaned = _clean_text(text)
    if ":" in cleaned:
        title, detail = cleaned.split(":", 1)
        return _clean_text(title), _clean_text(detail)
    if " - " in cleaned:
        title, detail = cleaned.split(" - ", 1)
        return _clean_text(title), _clean_text(detail)

    parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    if len(parts) == 2:
        return _clean_text(parts[0]), _clean_text(parts[1])
    return _truncate(cleaned, 32), cleaned


def _build_step_footer(beats: list[Beat]) -> list[dict[str, Any]]:
    if len(beats) <= 1:
        return []

    return [
        {
            "type": "group",
            "id": "steps",
            "position": "bottom",
            "layout": {
                "type": "carousel",
                "gap": "large",
                "curve": 12,
            },
            "children": [
                {
                    "type": "token",
                    "id": f"step_{beat.index + 1}",
                    "content": beat.label,
                }
                for beat in beats
            ],
        }
    ]


def _build_scenes(
    *,
    title: str,
    pattern: str,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> list[dict[str, Any]]:
    if pattern == "algorithm_walkthrough":
        return [
            _build_algorithm_scene(
                animation_title=title,
                beat=beat,
                beats=beats,
                audience=audience,
                include_narration=include_narration,
                pacing_profile=pacing_profile,
            )
            for beat in beats
        ]
    if pattern == "architecture_explainer":
        return [
            _build_architecture_scene(
                animation_title=title,
                beat=beat,
                beats=beats,
                audience=audience,
                include_narration=include_narration,
                pacing_profile=pacing_profile,
            )
            for beat in beats
        ]
    if pattern == "before_after_comparison":
        return _build_comparison_scenes(
            animation_title=title,
            beats=beats,
            audience=audience,
            include_narration=include_narration,
            pacing_profile=pacing_profile,
        )
    if pattern == "visual_explainer":
        return [
            _build_visual_scene(
                animation_title=title,
                beat=beat,
                beats=beats,
                audience=audience,
                include_narration=include_narration,
                pacing_profile=pacing_profile,
            )
            for beat in beats
        ]
    raise ValueError(f"Unsupported pattern {pattern!r}.")


def _build_process_scene(
    *,
    animation_title: str,
    beat: Beat,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> dict[str, Any]:
    scene_id = beat.slug
    title_id = "process_heading"
    focus_id = "process_focus_card"
    stage_id = "process_stage_badge"
    context_id = "process_context_token"
    outcome_id = "process_outcome_token"
    connector_ids = ["process_context_link", "process_outcome_link"]
    duration = _scene_duration(beat, pacing_profile)

    lane_children = [
        {
            "type": "token",
            "id": context_id,
            "content": _neighbor_title(beats, beat.index, -1, fallback="Context"),
        },
        {
            "type": "box",
            "id": focus_id,
            "content": _truncate(beat.title, 24),
            "style": "primary",
        },
        {
            "type": "token",
            "id": outcome_id,
            "content": _neighbor_title(beats, beat.index, 1, fallback="Outcome"),
        },
    ]

    panel_children: list[dict[str, Any]] = [
        {
            "type": "token",
            "id": stage_id,
            "content": beat.label,
        },
        {
            "type": "group",
            "id": "process_lane",
            "layout": {
                "type": "flow",
                "direction": "horizontal",
                "gap": "large",
                "align": "center",
            },
            "children": lane_children,
        },
    ]
    if not include_narration:
        panel_children.append(
            _text_stack(
                group_id=f"{scene_id}_detail",
                lines=_wrap_lines(beat.detail, width=34, max_lines=3),
                style="body",
            )
        )

    objects: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": title_id,
            "content": _truncate(beat.title, 26),
            "style": "heading",
        },
        *_connectors(
            ("process_context_link", context_id, focus_id),
            ("process_outcome_link", focus_id, outcome_id),
        ),
        {
            "type": "group",
            "id": "process_panel",
            "layout": {
                "type": "stack",
                "gap": "large",
                "align": "center",
            },
            "children": panel_children,
        },
    ]
    caption = _caption_group(
        scene_id=scene_id, audience=audience, include_narration=include_narration
    )
    if caption is not None:
        objects.append(caption)

    extra_animations = _connector_draw_animations(
        connector_ids, pacing_profile=pacing_profile, start=0.15
    )
    extra_animations.append(
        {
            "action": "pulse",
            "target": outcome_id,
            "at": format_duration(0.5 + pacing_profile.continuity_seconds),
            "duration": pacing_profile.highlight_duration,
            "color": "accent",
        }
    )

    return {
        "id": scene_id,
        "duration": duration,
        "template": "one-column",
        "layout": {"type": "stack", "gap": "large", "align": "center"},
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": focus_id,
        "focus_style": {
            "at": "0.45s",
            "duration": pacing_profile.focus_duration,
            "scale": 1.08,
            "color": "accent",
        },
        "objects": objects,
        "animations": _step_animations(
            beat=beat,
            duration=duration,
            target_id=focus_id,
            pacing_profile=pacing_profile,
            step_target_id=_step_target_id(beats, beat),
            reveal_target_ids=_reveal_object_ids(objects) if include_narration else None,
            extra_animations=extra_animations,
        ),
        "auto_visible": not include_narration,
    }


def _build_visual_scene(
    *,
    animation_title: str,
    beat: Beat,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> dict[str, Any]:
    scene_id = beat.slug
    focus_id = "visual_focus_card"
    source_id = "visual_source_token"
    result_id = "visual_result_token"
    connector_ids = ["visual_source_link", "visual_result_link"]
    duration = _scene_duration(beat, pacing_profile)

    panel_children: list[dict[str, Any]] = [
        {
            "type": "token",
            "id": "visual_stage_badge",
            "content": beat.label,
        },
        {
            "type": "group",
            "id": "visual_lane",
            "layout": {
                "type": "flow",
                "direction": "horizontal",
                "gap": "large",
                "align": "center",
            },
            "children": [
                _labelled_group(
                    "visual_source_group",
                    _truncate(beat.detail, 16) if beat.detail else "Context",
                    {
                        "type": "token",
                        "id": source_id,
                        "content": _neighbor_title(
                            beats, beat.index, -1, fallback=_truncate(animation_title, 18)
                        ),
                    },
                ),
                _labelled_group(
                    "visual_focus_group",
                    _truncate(beat.title, 16),
                    {
                        "type": "box",
                        "id": focus_id,
                        "content": _truncate(beat.title, 24),
                        "style": "accent",
                    },
                ),
                _labelled_group(
                    "visual_result_group",
                    _neighbor_title(beats, beat.index, 1, fallback="Outcome"),
                    {
                        "type": "token",
                        "id": result_id,
                        "content": _neighbor_title(beats, beat.index, 1, fallback="Takeaway"),
                    },
                ),
            ],
        },
    ]
    if not include_narration:
        panel_children.append(
            _text_stack(
                group_id=f"{scene_id}_detail",
                lines=_wrap_lines(beat.detail, width=34, max_lines=3),
                style="body",
            )
        )

    objects: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "visual_heading",
            "content": _truncate(beat.title, 26),
            "style": "heading",
        },
        *_connectors(
            ("visual_source_link", source_id, focus_id),
            ("visual_result_link", focus_id, result_id),
        ),
        {
            "type": "group",
            "id": "visual_panel",
            "layout": {
                "type": "stack",
                "gap": "large",
                "align": "center",
            },
            "children": panel_children,
        },
    ]
    caption = _caption_group(
        scene_id=scene_id, audience=audience, include_narration=include_narration
    )
    if caption is not None:
        objects.append(caption)

    extra_animations = _connector_draw_animations(
        connector_ids, pacing_profile=pacing_profile, start=0.2
    )
    extra_animations.extend(
        [
            {
                "action": "pulse",
                "target": source_id,
                "at": "0.2s",
                "duration": pacing_profile.highlight_duration,
                "color": "accent",
            },
            {
                "action": "pulse",
                "target": result_id,
                "at": format_duration(0.8 + pacing_profile.continuity_seconds),
                "duration": pacing_profile.highlight_duration,
                "color": "success",
            },
        ]
    )

    return {
        "id": scene_id,
        "duration": duration,
        "template": "one-column",
        "layout": {"type": "stack", "gap": "large", "align": "center"},
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": focus_id,
        "focus_style": {
            "at": "0.45s",
            "duration": pacing_profile.focus_duration,
            "scale": 1.1,
            "color": "accent",
        },
        "objects": objects,
        "animations": _step_animations(
            beat=beat,
            duration=duration,
            target_id=focus_id,
            pacing_profile=pacing_profile,
            step_target_id=_step_target_id(beats, beat),
            reveal_target_ids=_reveal_object_ids(objects) if include_narration else None,
            extra_animations=extra_animations,
        ),
        "auto_visible": not include_narration,
    }


def _build_algorithm_scene(
    *,
    animation_title: str,
    beat: Beat,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> dict[str, Any]:
    scene_id = beat.slug
    current_card_id = "algorithm_current_card"
    connector_ids = ["algorithm_prev_link", "algorithm_next_link"]
    duration = _scene_duration(beat, pacing_profile)

    lane_children = []
    for label, item, suffix, style in _algorithm_neighbors(beats, beat.index):
        lane_children.append(
            _labelled_group(
                f"algorithm_{suffix}",
                label,
                {
                    "type": "box",
                    "id": f"algorithm_{suffix}_card",
                    "content": _truncate(item.title, 20),
                    "style": style,
                },
            )
        )

    panel_children: list[dict[str, Any]] = [
        {
            "type": "token",
            "id": "algorithm_stage_badge",
            "content": beat.label,
        },
        {
            "type": "group",
            "id": "algorithm_lane",
            "layout": {
                "type": "flow",
                "direction": "horizontal",
                "gap": "large",
                "align": "center",
            },
            "children": lane_children,
        },
    ]
    if not include_narration:
        panel_children.append(
            _text_stack(
                group_id=f"{scene_id}_detail",
                lines=_wrap_lines(beat.detail, width=38, max_lines=3),
                style="body",
            )
        )

    objects: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "algorithm_heading",
            "content": _truncate(beat.title, 28),
            "style": "heading",
        },
        *_connectors(
            ("algorithm_prev_link", "algorithm_previous_card", current_card_id),
            ("algorithm_next_link", current_card_id, "algorithm_next_card"),
        ),
        {
            "type": "group",
            "id": "algorithm_panel",
            "layout": {
                "type": "stack",
                "gap": "large",
                "align": "center",
            },
            "children": panel_children,
        },
    ]
    caption = _caption_group(
        scene_id=scene_id, audience=audience, include_narration=include_narration
    )
    if caption is not None:
        objects.append(caption)

    extra_animations = _connector_draw_animations(
        connector_ids, pacing_profile=pacing_profile, start=0.15
    )
    extra_animations.append(
        {
            "action": "pulse",
            "target": "algorithm_next_card",
            "at": format_duration(0.6 + pacing_profile.continuity_seconds),
            "duration": pacing_profile.highlight_duration,
            "color": "accent",
        }
    )

    return {
        "id": scene_id,
        "duration": duration,
        "template": "one-column",
        "layout": {"type": "stack", "gap": "large", "align": "center"},
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": current_card_id,
        "focus_style": {
            "at": "0.45s",
            "duration": pacing_profile.focus_duration,
            "scale": 1.1,
            "color": "accent",
        },
        "objects": objects,
        "animations": _step_animations(
            beat=beat,
            duration=duration,
            target_id=current_card_id,
            pacing_profile=pacing_profile,
            step_target_id=_step_target_id(beats, beat),
            reveal_target_ids=_reveal_object_ids(objects) if include_narration else None,
            extra_animations=extra_animations,
        ),
        "auto_visible": not include_narration,
    }


def _build_architecture_scene(
    *,
    animation_title: str,
    beat: Beat,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> dict[str, Any]:
    scene_id = beat.slug
    focus_id = "architecture_system_card"
    connector_ids = ["architecture_source_link", "architecture_sink_link"]
    duration = _scene_duration(beat, pacing_profile)

    sidebar_children: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "architecture_sidebar_heading",
            "content": "Signal Flow",
            "style": "section-heading",
        },
        {
            "type": "token",
            "id": "architecture_stage_badge",
            "content": beat.label,
        },
        {
            "type": "token",
            "id": "architecture_input_token",
            "content": _neighbor_title(beats, beat.index, -1, fallback="Incoming"),
        },
        {
            "type": "token",
            "id": "architecture_output_token",
            "content": _neighbor_title(beats, beat.index, 1, fallback="Downstream"),
        },
    ]
    if not include_narration:
        sidebar_children.append(
            _text_stack(
                group_id=f"{scene_id}_detail",
                lines=_wrap_lines(beat.detail, width=18, max_lines=4),
                style="body",
                align="left",
            )
        )

    objects: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "architecture_heading",
            "content": _truncate(beat.title, 24),
            "style": "heading",
        },
        *_connectors(
            ("architecture_source_link", "architecture_source_card", focus_id),
            ("architecture_sink_link", focus_id, "architecture_sink_card"),
        ),
        {
            "type": "group",
            "id": "architecture_sidebar",
            "grid": {"region": "sidebar"},
            "layout": {
                "type": "stack",
                "gap": "medium",
                "align": "top",
            },
            "children": sidebar_children,
        },
        {
            "type": "group",
            "id": "architecture_main",
            "grid": {"region": "main"},
            "layout": {
                "type": "stack",
                "gap": "large",
                "align": "top",
            },
            "children": [
                {
                    "type": "group",
                    "id": "architecture_lane",
                    "layout": {
                        "type": "flow",
                        "direction": "horizontal",
                        "gap": "large",
                        "align": "center",
                    },
                    "children": [
                        {
                            "type": "box",
                            "id": "architecture_source_card",
                            "content": _neighbor_title(beats, beat.index, -1, fallback="Input"),
                            "style": "muted",
                        },
                        {
                            "type": "box",
                            "id": focus_id,
                            "content": _truncate(beat.title, 24),
                            "style": "accent",
                        },
                        {
                            "type": "box",
                            "id": "architecture_sink_card",
                            "content": _neighbor_title(beats, beat.index, 1, fallback="Outcome"),
                            "style": "primary",
                        },
                    ],
                }
            ],
        },
    ]
    caption = _caption_group(
        scene_id=scene_id, audience=audience, include_narration=include_narration
    )
    if caption is not None:
        objects.append(caption)

    extra_animations = _connector_draw_animations(
        connector_ids, pacing_profile=pacing_profile, start=0.2
    )
    extra_animations.append(
        {
            "action": "pulse",
            "target": "architecture_sink_card",
            "at": format_duration(0.75 + pacing_profile.continuity_seconds),
            "duration": pacing_profile.highlight_duration,
            "color": "success",
        }
    )

    return {
        "id": scene_id,
        "duration": duration,
        "template": "two-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": focus_id,
        "focus_style": {
            "at": "0.5s",
            "duration": pacing_profile.focus_duration,
            "scale": 1.08,
            "color": "accent",
        },
        "objects": objects,
        "animations": _step_animations(
            beat=beat,
            duration=duration,
            target_id=focus_id,
            pacing_profile=pacing_profile,
            step_target_id=_step_target_id(beats, beat),
            reveal_target_ids=_reveal_object_ids(objects) if include_narration else None,
            extra_animations=extra_animations,
        ),
        "auto_visible": not include_narration,
    }


def _build_comparison_scenes(
    *,
    animation_title: str,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
) -> list[dict[str, Any]]:
    if len(beats) == 1:
        return [
            _build_comparison_scene(
                animation_title=animation_title,
                beat=beats[0],
                previous=beats[0],
                audience=audience,
                include_narration=include_narration,
                pacing_profile=pacing_profile,
                step_target_id=None,
            )
        ]

    scenes: list[dict[str, Any]] = []
    for index in range(1, len(beats)):
        scenes.append(
            _build_comparison_scene(
                animation_title=animation_title,
                beat=beats[index],
                previous=beats[index - 1],
                audience=audience,
                include_narration=include_narration,
                pacing_profile=pacing_profile,
                step_target_id=_step_target_id(beats, beats[index]),
            )
        )
    return scenes


def _build_comparison_scene(
    *,
    animation_title: str,
    beat: Beat,
    previous: Beat,
    audience: str | None,
    include_narration: bool,
    pacing_profile: PacingProfile,
    step_target_id: str | None,
) -> dict[str, Any]:
    scene_id = beat.slug
    after_card_id = "comparison_after_card"
    duration = _scene_duration(beat, pacing_profile)

    before_children: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "comparison_before_label",
            "content": "Before",
            "style": "section-heading",
        },
        {
            "type": "token",
            "id": "comparison_before_status",
            "content": previous.label,
        },
        {
            "type": "box",
            "id": "comparison_before_card",
            "content": _truncate(previous.title, 22),
            "style": "muted",
        },
    ]
    after_children: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "comparison_after_label",
            "content": "After",
            "style": "section-heading",
        },
        {
            "type": "token",
            "id": "comparison_after_status",
            "content": beat.label,
        },
        {
            "type": "box",
            "id": after_card_id,
            "content": _truncate(beat.title, 24),
            "style": "primary",
        },
    ]
    if not include_narration:
        before_children.append(
            _text_stack(
                group_id=f"{scene_id}_before_detail",
                lines=_wrap_lines(previous.detail, width=18, max_lines=3),
                style="caption",
                align="left",
            )
        )
        after_children.append(
            _text_stack(
                group_id=f"{scene_id}_after_detail",
                lines=_wrap_lines(beat.detail, width=30, max_lines=4),
                style="body",
                align="left",
            )
        )

    objects: list[dict[str, Any]] = [
        {
            "type": "text",
            "id": "comparison_heading",
            "content": f"From {_truncate(previous.title, 12)} to {_truncate(beat.title, 12)}",
            "style": "heading",
        },
        *_connectors(("comparison_shift_link", "comparison_before_card", after_card_id)),
        {
            "type": "group",
            "id": "comparison_before_panel",
            "grid": {"region": "sidebar"},
            "layout": {
                "type": "stack",
                "gap": "medium",
                "align": "top",
            },
            "children": before_children,
        },
        {
            "type": "group",
            "id": "comparison_after_panel",
            "grid": {"region": "main"},
            "layout": {
                "type": "stack",
                "gap": "medium",
                "align": "top",
            },
            "children": after_children,
        },
    ]
    caption = _caption_group(
        scene_id=scene_id, audience=audience, include_narration=include_narration
    )
    if caption is not None:
        objects.append(caption)

    extra_animations = _connector_draw_animations(
        ["comparison_shift_link"],
        pacing_profile=pacing_profile,
        start=0.2,
    )
    extra_animations.append(
        {
            "action": "pulse",
            "target": "comparison_after_status",
            "at": format_duration(0.5 + pacing_profile.continuity_seconds),
            "duration": pacing_profile.highlight_duration,
            "color": "success",
        }
    )

    return {
        "id": scene_id,
        "duration": duration,
        "template": "two-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": after_card_id,
        "focus_style": {
            "at": "0.5s",
            "duration": pacing_profile.focus_duration,
            "scale": 1.08,
            "color": "success",
        },
        "objects": objects,
        "animations": _step_animations(
            beat=beat,
            duration=duration,
            target_id=after_card_id,
            pacing_profile=pacing_profile,
            step_target_id=step_target_id,
            highlight_color="success",
            reveal_target_ids=_reveal_object_ids(objects) if include_narration else None,
            extra_animations=extra_animations,
        ),
        "auto_visible": not include_narration,
    }


def _step_animations(
    *,
    beat: Beat,
    duration: str,
    target_id: str,
    pacing_profile: PacingProfile,
    step_target_id: str | None = None,
    highlight_color: str = "accent",
    reveal_target_ids: list[str] | None = None,
    extra_animations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    scene_seconds = max(0.0, float(duration.removesuffix("s")))
    active_duration = max(pacing_profile.highlight_seconds, scene_seconds - 0.4)

    animations: list[dict[str, Any]] = []
    if reveal_target_ids:
        reveal_window = min(max(scene_seconds * 0.35, 0.6), 1.2)
        reveal_gap = reveal_window / max(1, len(reveal_target_ids))
        for index, reveal_target_id in enumerate(reveal_target_ids):
            animations.append(
                {
                    "action": "fade-in",
                    "target": reveal_target_id,
                    "at": format_duration(index * reveal_gap),
                    "duration": pacing_profile.scale_duration,
                }
            )

    animations.append(
        {
            "action": "highlight",
            "target": target_id,
            "at": "0.4s",
            "duration": pacing_profile.highlight_duration,
            "style": "glow",
            "color": highlight_color,
        }
    )
    if step_target_id is not None:
        animations.extend(
            [
                {
                    "action": "highlight",
                    "target": step_target_id,
                    "at": "0s",
                    "duration": format_duration(active_duration),
                    "style": "glow",
                    "color": "accent",
                },
                {
                    "action": "scale",
                    "target": step_target_id,
                    "at": "0.1s",
                    "duration": pacing_profile.scale_duration,
                    "scale_factor": 1.14,
                },
            ]
        )
    if extra_animations:
        animations.extend(extra_animations)
    return animations


def _step_target_id(beats: list[Beat], beat: Beat) -> str | None:
    if len(beats) <= 1:
        return None
    return f"step_{beat.index + 1}"


def _caption_group(
    *,
    scene_id: str,
    audience: str | None,
    include_narration: bool,
) -> dict[str, Any] | None:
    if include_narration:
        return None
    return {
        "type": "group",
        "id": f"{scene_id}_caption",
        "position": "bottom",
        "layout": {
            "type": "stack",
            "gap": "small",
            "align": "center",
        },
        "children": [
            {
                "type": "text",
                "id": f"{scene_id}_caption_1",
                "content": _audience_caption(audience),
                "style": "caption",
            }
        ],
    }


def _connector_draw_animations(
    connector_ids: list[str],
    *,
    pacing_profile: PacingProfile,
    start: float,
    gap: float = 0.45,
) -> list[dict[str, Any]]:
    animations: list[dict[str, Any]] = []
    for index, connector_id in enumerate(connector_ids):
        animations.append(
            {
                "action": "draw",
                "target": connector_id,
                "at": format_duration(start + index * gap),
                "duration": pacing_profile.continuity_duration,
            }
        )
    return animations


def _connectors(*pairs: tuple[str, str, str]) -> list[dict[str, Any]]:
    return [
        {
            "type": "connector",
            "id": connector_id,
            "from": from_id,
            "to": to_id,
        }
        for connector_id, from_id, to_id in pairs
    ]


def _labelled_group(group_id: str, label: str, child: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "group",
        "id": group_id,
        "label": label,
        "layout": {
            "type": "stack",
            "gap": "small",
            "align": "center",
        },
        "children": [child],
    }


def _text_stack(
    *,
    group_id: str,
    lines: list[str],
    style: str,
    align: str = "center",
) -> dict[str, Any]:
    return {
        "type": "group",
        "id": group_id,
        "layout": {
            "type": "stack",
            "gap": "small",
            "align": align,
        },
        "children": [
            {
                "type": "text",
                "id": f"{group_id}_{index + 1}",
                "content": line,
                "style": style,
            }
            for index, line in enumerate(lines)
        ],
    }


def _reveal_object_ids(objects: list[dict[str, Any]]) -> list[str]:
    ordered_ids: list[str] = []
    seen: set[str] = set()

    def visit(items: list[dict[str, Any]]) -> None:
        for item in items:
            object_id = item.get("id")
            if object_id and item.get("type") != "connector" and object_id not in seen:
                seen.add(object_id)
                ordered_ids.append(object_id)
            children = item.get("children") or []
            if children:
                visit(children)

    visit(objects)
    return ordered_ids


def _wrap_lines(text: str, *, width: int, max_lines: int) -> list[str]:
    cleaned = _clean_text(text)
    lines = textwrap.wrap(
        cleaned,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [cleaned]
    if len(lines) <= max_lines:
        return lines

    kept = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    kept.append(_truncate(tail, width))
    return kept


def _algorithm_neighbors(beats: list[Beat], index: int) -> list[tuple[str, Beat, str, str]]:
    previous = beats[max(0, index - 1)]
    current = beats[index]
    following = beats[min(len(beats) - 1, index + 1)]
    return [
        ("Previous", previous, "previous", "muted"),
        ("Current", current, "current", "primary"),
        ("Next", following, "next", "accent"),
    ]


def _neighbor_title(beats: list[Beat], index: int, offset: int, *, fallback: str) -> str:
    neighbor_index = index + offset
    if 0 <= neighbor_index < len(beats):
        return _truncate(beats[neighbor_index].title, 18)
    return fallback


def _scene_duration(beat: Beat, pacing_profile: PacingProfile) -> str:
    word_count = len(f"{beat.title} {beat.detail}".split())
    return pacing_profile.scene_duration(word_count)


def _scene_narration(
    animation_title: str,
    beat: Beat,
    audience: str | None,
    include_narration: bool,
) -> str | None:
    if not include_narration:
        return None
    detail = _clean_text(beat.detail) or _clean_text(beat.title) or _clean_text(animation_title)
    if detail and detail[-1] not in ".!?":
        detail += "."
    return detail


def _audience_caption(audience: str | None) -> str:
    if audience:
        return f"Built for {audience}."
    return "Visual starter with safe defaults."


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, length: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= length:
        return cleaned
    return cleaned[: max(1, length - 1)].rstrip() + "..."
