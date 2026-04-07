from __future__ import annotations

from kaivra.dsl.schema import AnimAction, DocumentSpec, ObjectType
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


def test_one_column_semantic_regions_place_blocks_in_vertical_order() -> None:
    graph = _build_graph(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "semantic_layout",
                    "duration": "6s",
                    "template": "one-column",
                    "auto_visible": True,
                    "objects": [
                        {"id": "title", "type": "text", "content": "Semantic", "style": "heading"},
                        {
                            "id": "problem_lane",
                            "type": "group",
                            "grid": {"region": "problem_solution"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [{"id": "problem", "type": "box", "content": "Problem"}],
                        },
                        {
                            "id": "pipeline_lane",
                            "type": "group",
                            "grid": {"region": "request_pipeline"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [{"id": "pipeline", "type": "box", "content": "Pipeline"}],
                        },
                        {
                            "id": "fanout_lane",
                            "type": "group",
                            "grid": {"region": "fan_out"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [{"id": "fanout", "type": "box", "content": "Fan Out"}],
                        },
                        {
                            "id": "architecture_lane",
                            "type": "group",
                            "grid": {"region": "system_architecture"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [
                                {"id": "architecture", "type": "box", "content": "Architecture"}
                            ],
                        },
                        {
                            "id": "timeline_lane",
                            "type": "group",
                            "grid": {"region": "timeline_steps"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [{"id": "timeline", "type": "box", "content": "Timeline"}],
                        },
                    ],
                    "animations": [],
                }
            ],
        }
    )
    scene = graph.scenes[0]

    assert scene.node_map["title"].rect.y < scene.node_map["problem_lane"].rect.y
    assert scene.node_map["problem_lane"].rect.y < scene.node_map["pipeline_lane"].rect.y
    assert scene.node_map["pipeline_lane"].rect.y < scene.node_map["fanout_lane"].rect.y
    assert scene.node_map["fanout_lane"].rect.y < scene.node_map["architecture_lane"].rect.y
    assert scene.node_map["architecture_lane"].rect.y < scene.node_map["timeline_lane"].rect.y


def test_one_column_unassigned_objects_still_fall_back_to_main_region() -> None:
    graph = _build_graph(
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "main_fallback",
                    "duration": "6s",
                    "template": "one-column",
                    "auto_visible": True,
                    "objects": [
                        {"id": "title", "type": "text", "content": "Legacy", "style": "heading"},
                        {"id": "summary", "type": "box", "content": "Still uses main"},
                        {
                            "id": "pipeline_lane",
                            "type": "group",
                            "grid": {"region": "request_pipeline"},
                            "layout": {"type": "flow", "gap": "medium"},
                            "children": [{"id": "request", "type": "box", "content": "Request"}],
                        },
                    ],
                    "animations": [],
                }
            ],
        }
    )
    scene = graph.scenes[0]

    assert scene.node_map["title"].rect.y < scene.node_map["summary"].rect.y
    assert scene.node_map["summary"].rect.y > scene.node_map["title"].rect.y
    assert scene.node_map["pipeline_lane"].rect.y > scene.node_map["title"].rect.y
