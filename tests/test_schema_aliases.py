from __future__ import annotations

import json

import pytest

from kaivra.dsl.parser import parse_string


def test_show_subtitles_is_the_preferred_serialized_field_name() -> None:
    doc = parse_string(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"theme": "modern", "show_subtitles": False},
                "scenes": [],
            }
        ),
        format="json",
    )

    assert doc.meta.show_subtitles is False
    assert doc.meta.show_narration is False
    assert doc.meta.subtitles_were_explicitly_set() is True

    serialized = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert serialized["meta"]["show_subtitles"] is False
    assert "show_narration" not in serialized["meta"]


def test_show_narration_remains_a_backward_compatible_input_alias() -> None:
    doc = parse_string(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"theme": "modern", "show_narration": False},
                "scenes": [],
            }
        ),
        format="json",
    )

    assert doc.meta.show_subtitles is False
    assert doc.meta.show_narration is False
    assert doc.meta.subtitles_were_explicitly_set() is True


def test_animation_style_is_rejected_for_non_emphasis_actions() -> None:
    with pytest.raises(ValueError, match="`style` is only supported"):
        parse_string(
            json.dumps(
                {
                    "version": "1.2",
                    "meta": {"theme": "modern"},
                    "scenes": [
                        {
                            "objects": [{"id": "box", "type": "box", "content": "A"}],
                            "animations": [
                                {
                                    "action": "move",
                                    "target": "box",
                                    "style": "glow",
                                }
                            ],
                        }
                    ],
                }
            ),
            format="json",
        )


def test_animation_rejects_multiple_semantic_timing_anchors() -> None:
    with pytest.raises(ValueError, match="multiple timing anchors"):
        parse_string(
            json.dumps(
                {
                    "version": "1.2",
                    "meta": {"theme": "modern"},
                    "scenes": [
                        {
                            "objects": [{"id": "box", "type": "box", "content": "A"}],
                            "animations": [
                                {
                                    "action": "reveal",
                                    "target": "box",
                                    "at": "0s",
                                    "after": "intro",
                                }
                            ],
                        }
                    ],
                }
            ),
            format="json",
        )
