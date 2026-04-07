from __future__ import annotations

import pytest

from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming
from kaivra.dsl.schema import AnimAction, DocumentSpec, ObjectType
from kaivra.dsl.timing import TimingConfig
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.scene_graph.models import AnimationKeyframe, SceneNode
from kaivra.scene_graph.timeline import apply_animations_at_time
from kaivra.themes.registry import get_theme
from kaivra.utils.geometry import Rect


def _build_graph(doc_dict: dict) -> object:
    doc = DocumentSpec.model_validate(doc_dict)
    return build_scene_graph(doc, get_theme(doc.meta.theme))


def test_appear_with_duration_behaves_like_a_fade() -> None:
    node = SceneNode(
        id="title",
        obj_type=ObjectType.TEXT,
        rect=Rect(0, 0, 100, 40),
    )
    keyframes = [
        AnimationKeyframe(
            target_id="title",
            action=AnimAction.APPEAR,
            start_time=0.0,
            duration=1.0,
        )
    ]

    apply_animations_at_time({"title": node}, keyframes, 0.5)

    assert node.visible is True
    assert 0.0 < node.opacity < 1.0


def test_group_reveal_propagates_to_unanimated_children_but_not_to_explicit_child_reveals() -> None:
    graph = _build_graph(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "group_reveal",
                    "duration": "4s",
                    "auto_visible": False,
                    "layout": "center",
                    "objects": [
                        {
                            "id": "cluster",
                            "type": "group",
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [
                                {"id": "child_a", "type": "box", "content": "A"},
                                {"id": "child_b", "type": "box", "content": "B"},
                            ],
                        }
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "cluster", "at": "0s", "duration": "1s"},
                        {
                            "action": "fade-in",
                            "target": "child_b",
                            "at": "1.5s",
                            "duration": "0.6s",
                        },
                    ],
                }
            ],
        }
    )
    scene = graph.scenes[0]

    apply_animations_at_time(scene.node_map, scene.timeline, 0.5)

    assert scene.node_map["child_a"].visible is True
    assert scene.node_map["child_a"].opacity > 0.0
    assert scene.node_map["child_b"].visible is False

    apply_animations_at_time(scene.node_map, scene.timeline, 2.0)

    assert scene.node_map["child_b"].visible is True
    assert scene.node_map["child_b"].opacity > 0.0


def test_replace_cross_fades_and_leaves_replacement_visible() -> None:
    old_node = SceneNode(
        id="old_value",
        obj_type=ObjectType.BOX,
        rect=Rect(0, 0, 120, 60),
        default_visible=True,
    )
    new_node = SceneNode(
        id="new_value",
        obj_type=ObjectType.BOX,
        rect=Rect(0, 0, 120, 60),
    )
    keyframes = [
        AnimationKeyframe(
            target_id="old_value",
            action=AnimAction.REPLACE,
            start_time=1.0,
            duration=1.0,
            with_id="new_value",
        )
    ]
    nodes = {"old_value": old_node, "new_value": new_node}

    apply_animations_at_time(nodes, keyframes, 1.5)

    assert old_node.visible is True
    assert new_node.visible is True
    assert 0.0 < old_node.opacity < 1.0
    assert 0.0 < new_node.opacity < 1.0

    apply_animations_at_time(nodes, keyframes, 2.1)

    assert old_node.visible is False
    assert old_node.opacity == 0.0
    assert new_node.visible is True
    assert new_node.opacity == 1.0


def test_callout_auto_placement_chooses_non_overlapping_side_when_available() -> None:
    graph = _build_graph(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "callout",
                    "duration": "4s",
                    "auto_visible": True,
                    "layout": {"type": "grid", "columns": 3},
                    "objects": [
                        {
                            "id": "target_box",
                            "type": "box",
                            "content": "Target",
                            "grid": {"col": 1},
                        },
                        {
                            "id": "neighbor_box",
                            "type": "box",
                            "content": "Neighbor",
                            "grid": {"col": 2},
                        },
                        {
                            "id": "flow_callout",
                            "type": "callout",
                            "target": "target_box",
                            "content": "Notice the data path",
                        },
                    ],
                    "animations": [],
                }
            ],
        }
    )
    scene = graph.scenes[0]

    assert (
        scene.node_map["flow_callout"].rect.intersects(scene.node_map["neighbor_box"].rect) is False
    )


def test_semantic_relative_timing_resolves_from_anchor_and_gap_tokens() -> None:
    doc = DocumentSpec.model_validate(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "semantic_scene",
                    "duration": "auto",
                    "layout": "center",
                    "objects": [
                        {"id": "first", "type": "box", "content": "First"},
                        {"id": "second", "type": "box", "content": "Second"},
                    ],
                    "animations": [
                        {
                            "id": "intro",
                            "action": "fade-in",
                            "target": "first",
                            "at": "0s",
                            "duration": "short",
                        },
                        {
                            "action": "fade-in",
                            "target": "second",
                            "after": "intro",
                            "gap": "long",
                            "duration": "short",
                        },
                    ],
                }
            ],
        }
    )
    timing_config = TimingConfig(
        gap_tokens={"none": "0s", "short": "0.25s", "medium": "0.5s", "long": "1.0s"},
        duration_tokens={"instant": "0s", "short": "0.25s", "medium": "0.5s", "long": "1.0s"},
        action_durations={"fade-in": "0.5s"},
        tail_padding="0.75s",
    )

    graph = build_scene_graph(doc, get_theme(doc.meta.theme), timing_config=timing_config)
    timeline = graph.scenes[0].timeline

    assert timeline[0].start_time == 0.0
    assert timeline[0].duration == 0.25
    assert timeline[1].start_time == 1.25
    assert graph.scenes[0].duration == 2.25


def test_semantic_cue_anchor_requires_external_audio_timing_data() -> None:
    doc = DocumentSpec.model_validate(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "cue_scene",
                    "duration": "auto",
                    "layout": "center",
                    "objects": [{"id": "node", "type": "box", "content": "Cue"}],
                    "animations": [
                        {
                            "action": "highlight",
                            "target": "node",
                            "cue": "keyword",
                            "duration": "short",
                        }
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="requires external audio timings"):
        build_scene_graph(doc, get_theme(doc.meta.theme))


def test_semantic_cue_anchor_uses_external_audio_timing_data() -> None:
    doc = DocumentSpec.model_validate(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "cue_scene",
                    "duration": "auto",
                    "layout": "center",
                    "objects": [{"id": "node", "type": "box", "content": "Cue"}],
                    "animations": [
                        {
                            "action": "highlight",
                            "target": "node",
                            "cue": "keyword",
                            "gap": "short",
                            "duration": "short",
                        }
                    ],
                }
            ],
        }
    )
    timing_data = AudioTimingData(
        scenes={
            "cue_scene": SceneAudioTiming(
                id="cue_scene",
                duration_seconds=3.0,
                cues=(AudioCue(start_seconds=0.9, duration_seconds=0.4, text="keyword"),),
            )
        }
    )

    graph = build_scene_graph(
        doc,
        get_theme(doc.meta.theme),
        audio_timing_data=timing_data,
    )

    assert graph.scenes[0].timeline[0].start_time == 1.3
