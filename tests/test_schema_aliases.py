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


def test_translate_is_the_supported_motion_field() -> None:
    doc = parse_string(
        json.dumps(
            {
                "version": "1.3",
                "meta": {"theme": "modern"},
                "scenes": [
                    {
                        "objects": [{"id": "box", "type": "box", "content": "A"}],
                        "animations": [
                            {
                                "action": "move",
                                "target": "box",
                                "translate": {"x": 1.0},
                            }
                        ],
                    }
                ],
            }
        ),
        format="json",
    )

    assert doc.scenes[0].animations[0].translate is not None
    assert doc.scenes[0].animations[0].translate.x == 1.0


def test_legacy_pixel_offsets_are_accepted() -> None:
    # offset_x/y are kept for backwards compatibility — they must parse without error.
    doc = parse_string(
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
                                "offset_x": 12,
                                "offset_y": -8,
                                "from_offset_x": 0,
                                "from_offset_y": 0,
                            }
                        ],
                    }
                ],
            }
        ),
        format="json",
    )
    anim = doc.scenes[0].animations[0]
    assert anim.offset_x == 12
    assert anim.offset_y == -8


def test_absolute_layout_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_string(
            json.dumps(
                {
                    "version": "1.3",
                    "meta": {"theme": "modern"},
                    "scenes": [{"layout": "absolute", "objects": []}],
                }
            ),
            format="json",
        )
