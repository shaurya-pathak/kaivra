"""Starter blueprints for guided Kaivra authoring."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from kaivra.dsl.parser import parse_string
from kaivra.dsl.schema import DocumentSpec

DEFAULT_PATTERN = "process_explainer"
SUPPORTED_PATTERNS = (
    "algorithm_walkthrough",
    "process_explainer",
    "architecture_explainer",
    "before_after_comparison",
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
) -> DocumentSpec:
    """Build a valid Kaivra starter document for the requested pattern."""
    chosen_pattern = (pattern or DEFAULT_PATTERN).strip()
    if chosen_pattern not in SUPPORTED_PATTERNS:
        supported = ", ".join(SUPPORTED_PATTERNS)
        raise ValueError(f"Unsupported pattern {chosen_pattern!r}. Choose one of: {supported}.")

    chosen_theme = (theme or DEFAULT_THEME).strip()
    if not chosen_theme:
        raise ValueError("Theme names cannot be empty.")

    parsed_beats = _coerce_beats(beats, title=title)

    raw = {
        "version": "1.1",
        "meta": {
            "title": title,
            "resolution": [1920, 1080],
            "fps": 30,
            "theme": chosen_theme,
            "show_narration": include_narration,
            "continuity": True,
            "continuity_duration": "0.6s",
            "glow_release_padding": "0.8s",
        },
        "objects": _build_step_footer(parsed_beats),
        "scenes": _build_scenes(
            title=title,
            pattern=chosen_pattern,
            beats=parsed_beats,
            audience=audience,
            include_narration=include_narration,
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
) -> list[dict[str, Any]]:
    if pattern == "algorithm_walkthrough":
        return [
            _build_algorithm_scene(
                animation_title=title,
                beat=beat,
                beats=beats,
                audience=audience,
                include_narration=include_narration,
            )
            for beat in beats
        ]
    if pattern == "architecture_explainer":
        return [
            _build_architecture_scene(
                animation_title=title,
                beat=beat,
                audience=audience,
                include_narration=include_narration,
            )
            for beat in beats
        ]
    if pattern == "before_after_comparison":
        return _build_comparison_scenes(
            animation_title=title,
            beats=beats,
            audience=audience,
            include_narration=include_narration,
        )
    return [
        _build_process_scene(
            animation_title=title,
            beat=beat,
            audience=audience,
            include_narration=include_narration,
        )
        for beat in beats
    ]


def _build_process_scene(
    *,
    animation_title: str,
    beat: Beat,
    audience: str | None,
    include_narration: bool,
) -> dict[str, Any]:
    scene_id = beat.slug
    body_group_id = f"{scene_id}_body"
    panel_id = f"{scene_id}_panel"
    main_card_id = f"{scene_id}_main_card"

    return {
        "id": scene_id,
        "duration": _scene_duration(beat),
        "template": "one-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": main_card_id,
        "focus_style": {
            "at": "0.5s",
            "duration": "1.2s",
            "scale": 1.08,
            "color": "accent",
        },
        "objects": [
            {
                "type": "text",
                "id": f"{scene_id}_title",
                "content": _truncate(beat.title, 26),
                "style": "heading",
            },
            {
                "type": "group",
                "id": panel_id,
                "layout": {
                    "type": "stack",
                    "gap": "large",
                    "align": "center",
                },
                "children": [
                    {
                        "type": "box",
                        "id": main_card_id,
                        "content": _truncate(beat.title, 28),
                        "style": "primary",
                    },
                    _text_stack(
                        group_id=body_group_id,
                        lines=_wrap_lines(beat.detail, width=34, max_lines=3),
                        style="body",
                    ),
                    _text_stack(
                        group_id=f"{scene_id}_caption",
                        lines=[_audience_caption(audience)],
                        style="caption",
                    ),
                ],
            },
        ],
        "animations": _step_animations(
            beat=beat,
            duration=_scene_duration(beat),
            target_id=main_card_id,
        ),
        "auto_visible": True,
    }


def _build_algorithm_scene(
    *,
    animation_title: str,
    beat: Beat,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
) -> dict[str, Any]:
    scene_id = beat.slug
    current_card_id = f"{scene_id}_current_card"
    lane_id = f"{scene_id}_lane"
    detail_id = f"{scene_id}_detail"
    neighbors = _algorithm_neighbors(beats, beat.index)

    lane_children = []
    for label, item, suffix, style in neighbors:
        lane_children.append(
            {
                "type": "group",
                "id": f"{scene_id}_{suffix}",
                "layout": {
                    "type": "stack",
                    "gap": "small",
                    "align": "center",
                },
                "children": [
                    {
                        "type": "text",
                        "id": f"{scene_id}_{suffix}_label",
                        "content": label,
                        "style": "caption",
                    },
                    {
                        "type": "box",
                        "id": current_card_id if suffix == "current" else f"{scene_id}_{suffix}_card",
                        "content": _truncate(item.title, 20),
                        "style": style,
                    },
                ],
            }
        )

    return {
        "id": scene_id,
        "duration": _scene_duration(beat),
        "template": "one-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": current_card_id,
        "focus_style": {
            "at": "0.5s",
            "duration": "1.2s",
            "scale": 1.1,
            "color": "accent",
        },
        "objects": [
            {
                "type": "text",
                "id": f"{scene_id}_title",
                "content": f"Step {beat.index + 1}: {_truncate(beat.title, 20)}",
                "style": "heading",
            },
            {
                "type": "group",
                "id": f"{scene_id}_panel",
                "layout": {
                    "type": "stack",
                    "gap": "large",
                    "align": "center",
                },
                "children": [
                    {
                        "type": "group",
                        "id": lane_id,
                        "layout": {
                            "type": "flow",
                            "direction": "horizontal",
                            "gap": "large",
                            "align": "center",
                        },
                        "children": lane_children,
                    },
                    _text_stack(
                        group_id=detail_id,
                        lines=_wrap_lines(beat.detail, width=38, max_lines=3),
                        style="body",
                    ),
                ],
            },
        ],
        "animations": _step_animations(
            beat=beat,
            duration=_scene_duration(beat),
            target_id=current_card_id,
        ),
        "auto_visible": True,
    }


def _build_architecture_scene(
    *,
    animation_title: str,
    beat: Beat,
    audience: str | None,
    include_narration: bool,
) -> dict[str, Any]:
    scene_id = beat.slug
    main_card_id = f"{scene_id}_system_card"
    return {
        "id": scene_id,
        "duration": _scene_duration(beat),
        "template": "two-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": main_card_id,
        "focus_style": {
            "at": "0.6s",
            "duration": "1.3s",
            "scale": 1.08,
            "color": "accent",
        },
        "objects": [
            {
                "type": "text",
                "id": f"{scene_id}_title",
                "content": _truncate(beat.title, 24),
                "style": "heading",
            },
            {
                "type": "group",
                "id": f"{scene_id}_sidebar",
                "grid": {"region": "sidebar"},
                "layout": {
                    "type": "stack",
                    "gap": "medium",
                    "align": "top",
                },
                "children": [
                    {
                        "type": "text",
                        "id": f"{scene_id}_sidebar_heading",
                        "content": "Current layer",
                        "style": "section-heading",
                    },
                    {
                        "type": "token",
                        "id": f"{scene_id}_step_badge",
                        "content": f"Stage {beat.index + 1}",
                    },
                    _text_stack(
                        group_id=f"{scene_id}_sidebar_text",
                        lines=_wrap_lines(_audience_caption(audience), width=18, max_lines=3),
                        style="caption",
                        align="left",
                    ),
                ],
            },
            {
                "type": "group",
                "id": f"{scene_id}_main",
                "grid": {"region": "main"},
                "layout": {
                    "type": "stack",
                    "gap": "large",
                    "align": "top",
                },
                "children": [
                    {
                        "type": "box",
                        "id": main_card_id,
                        "content": _truncate(beat.title, 28),
                        "style": "accent",
                    },
                    _text_stack(
                        group_id=f"{scene_id}_detail",
                        lines=_wrap_lines(beat.detail, width=34, max_lines=4),
                        style="body",
                        align="left",
                    ),
                ],
            },
        ],
        "animations": _step_animations(
            beat=beat,
            duration=_scene_duration(beat),
            target_id=main_card_id,
        ),
        "auto_visible": True,
    }


def _build_comparison_scenes(
    *,
    animation_title: str,
    beats: list[Beat],
    audience: str | None,
    include_narration: bool,
) -> list[dict[str, Any]]:
    if len(beats) == 1:
        return [
            _build_comparison_scene(
                animation_title=animation_title,
                beat=beats[0],
                previous=beats[0],
                audience=audience,
                include_narration=include_narration,
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
) -> dict[str, Any]:
    scene_id = beat.slug
    after_card_id = f"{scene_id}_after_card"
    return {
        "id": scene_id,
        "duration": _scene_duration(beat),
        "template": "two-column",
        "narration": _scene_narration(animation_title, beat, audience, include_narration),
        "focus": after_card_id,
        "focus_style": {
            "at": "0.6s",
            "duration": "1.2s",
            "scale": 1.08,
            "color": "success",
        },
        "objects": [
            {
                "type": "text",
                "id": f"{scene_id}_title",
                "content": f"From {_truncate(previous.title, 12)} to {_truncate(beat.title, 12)}",
                "style": "heading",
            },
            {
                "type": "group",
                "id": f"{scene_id}_before_panel",
                "grid": {"region": "sidebar"},
                "layout": {
                    "type": "stack",
                    "gap": "medium",
                    "align": "top",
                },
                "children": [
                    {
                        "type": "text",
                        "id": f"{scene_id}_before_label",
                        "content": "Before",
                        "style": "section-heading",
                    },
                    {
                        "type": "box",
                        "id": f"{scene_id}_before_card",
                        "content": _truncate(previous.title, 22),
                        "style": "muted",
                    },
                    _text_stack(
                        group_id=f"{scene_id}_before_detail",
                        lines=_wrap_lines(previous.detail, width=18, max_lines=3),
                        style="caption",
                        align="left",
                    ),
                ],
            },
            {
                "type": "group",
                "id": f"{scene_id}_after_panel",
                "grid": {"region": "main"},
                "layout": {
                    "type": "stack",
                    "gap": "medium",
                    "align": "top",
                },
                "children": [
                    {
                        "type": "text",
                        "id": f"{scene_id}_after_label",
                        "content": "After",
                        "style": "section-heading",
                    },
                    {
                        "type": "box",
                        "id": after_card_id,
                        "content": _truncate(beat.title, 24),
                        "style": "primary",
                    },
                    _text_stack(
                        group_id=f"{scene_id}_after_detail",
                        lines=_wrap_lines(beat.detail, width=34, max_lines=4),
                        style="body",
                        align="left",
                    ),
                ],
            },
        ],
        "animations": _step_animations(
            beat=beat,
            duration=_scene_duration(beat),
            target_id=after_card_id,
            highlight_color="success",
        ),
        "auto_visible": True,
    }


def _step_animations(
    *,
    beat: Beat,
    duration: str,
    target_id: str,
    highlight_color: str = "accent",
) -> list[dict[str, Any]]:
    scene_seconds = float(duration.removesuffix("s"))
    active_duration = max(1.0, scene_seconds - 0.4)

    animations = [
        {
            "action": "highlight",
            "target": target_id,
            "at": "0.4s",
            "duration": "1.6s",
            "style": "glow",
            "color": highlight_color,
        }
    ]
    if beat.index >= 0:
        animations.extend(
            [
                {
                    "action": "highlight",
                    "target": f"step_{beat.index + 1}",
                    "at": "0s",
                    "duration": f"{active_duration:.1f}s",
                    "style": "glow",
                    "color": "accent",
                },
                {
                    "action": "scale",
                    "target": f"step_{beat.index + 1}",
                    "at": "0.1s",
                    "duration": "0.8s",
                    "scale_factor": 1.14,
                },
            ]
        )
    return animations


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


def _scene_duration(beat: Beat) -> str:
    word_count = len(beat.detail.split())
    seconds = min(8, max(5, 4 + round(word_count / 5)))
    return f"{seconds}s"


def _scene_narration(
    animation_title: str,
    beat: Beat,
    audience: str | None,
    include_narration: bool,
) -> str | None:
    if not include_narration:
        return None
    if audience:
        return f"{beat.title}. {beat.detail} This version is tuned for {audience}."
    return f"{animation_title}: {beat.title}. {beat.detail}"


def _audience_caption(audience: str | None) -> str:
    if audience:
        return f"Built for {audience}."
    return "Starter layout with safe defaults."


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, length: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= length:
        return cleaned
    return cleaned[: max(1, length - 1)].rstrip() + "..."
