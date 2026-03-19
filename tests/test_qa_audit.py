from __future__ import annotations

from kaivra.dsl.schema import ObjectType
from kaivra.qa.audit import audit_scene_graph
from kaivra.scene_graph.models import ResolvedScene, SceneGraph, SceneNode
from kaivra.utils.geometry import Rect, connector_endpoints


def _graph_for(node: SceneNode) -> SceneGraph:
    return _graph_for_nodes([node])


def _graph_for_nodes(nodes: list[SceneNode]) -> SceneGraph:
    scene = ResolvedScene(
        id="scene_1",
        duration=4.0,
        nodes=nodes,
        node_map={node.id: node for node in nodes},
        timeline=[],
    )
    return SceneGraph(
        width=500,
        height=300,
        fps=30,
        theme_name="modern",
        scenes=[scene],
        show_narration=False,
    )


def test_audit_suppresses_clipping_for_carousel_items() -> None:
    node = SceneNode(
        id="carousel_token",
        obj_type=ObjectType.TOKEN,
        rect=Rect(-80, 100, 180, 60),
        default_visible=True,
        layout_role="carousel-item",
    )

    findings = audit_scene_graph(_graph_for(node), samples_per_scene=2)

    assert findings == []


def test_audit_still_reports_clipping_for_non_carousel_items() -> None:
    node = SceneNode(
        id="regular_token",
        obj_type=ObjectType.TOKEN,
        rect=Rect(-80, 100, 180, 60),
        default_visible=True,
    )

    findings = audit_scene_graph(_graph_for(node), samples_per_scene=2)

    assert any(finding.kind == "clipping" for finding in findings)


def test_audit_warns_when_callout_overlaps_neighboring_content() -> None:
    target = SceneNode(
        id="target_box",
        obj_type=ObjectType.BOX,
        rect=Rect(40, 100, 120, 60),
        default_visible=True,
    )
    neighbor = SceneNode(
        id="neighbor_box",
        obj_type=ObjectType.BOX,
        rect=Rect(210, 100, 120, 60),
        default_visible=True,
    )
    callout = SceneNode(
        id="flow_callout",
        obj_type=ObjectType.CALLOUT,
        rect=Rect(200, 90, 170, 80),
        from_id="target_box",
        default_visible=True,
    )

    findings = audit_scene_graph(_graph_for_nodes([target, neighbor, callout]), samples_per_scene=2)

    assert any(finding.kind == "callout_overlap" for finding in findings)


def test_audit_warns_when_connector_crosses_unrelated_node() -> None:
    top_left = SceneNode(
        id="top_left",
        obj_type=ObjectType.BOX,
        rect=Rect(40, 40, 120, 60),
        default_visible=True,
    )
    middle = SceneNode(
        id="middle",
        obj_type=ObjectType.BOX,
        rect=Rect(190, 140, 120, 60),
        default_visible=True,
    )
    bottom_right = SceneNode(
        id="bottom_right",
        obj_type=ObjectType.BOX,
        rect=Rect(340, 240, 120, 60),
        default_visible=True,
    )
    connector = SceneNode(
        id="flow_arrow",
        obj_type=ObjectType.CONNECTOR,
        rect=Rect(0, 0, 0, 0),
        from_id="top_left",
        to_id="bottom_right",
        default_visible=True,
    )

    findings = audit_scene_graph(
        _graph_for_nodes([top_left, middle, bottom_right, connector]),
        samples_per_scene=2,
    )

    assert any(
        finding.kind == "connector_overlap" and finding.node_ids == ("flow_arrow", "middle")
        for finding in findings
    )


def test_audit_ignores_connector_touching_only_its_endpoints() -> None:
    left = SceneNode(
        id="left",
        obj_type=ObjectType.BOX,
        rect=Rect(30, 100, 120, 60),
        default_visible=True,
    )
    right = SceneNode(
        id="right",
        obj_type=ObjectType.BOX,
        rect=Rect(280, 100, 120, 60),
        default_visible=True,
    )
    connector = SceneNode(
        id="left_to_right",
        obj_type=ObjectType.CONNECTOR,
        rect=Rect(0, 0, 0, 0),
        from_id="left",
        to_id="right",
        default_visible=True,
    )

    findings = audit_scene_graph(_graph_for_nodes([left, right, connector]), samples_per_scene=2)

    assert not any(finding.kind == "connector_overlap" for finding in findings)


def test_connector_endpoints_prefer_top_to_bottom_when_nodes_share_a_column() -> None:
    start, end = connector_endpoints(
        Rect(240, 120, 380, 120),
        Rect(540, 360, 500, 120),
    )

    assert start == Rect(240, 120, 380, 120).bottom_center
    assert end == Rect(540, 360, 500, 120).top_center
