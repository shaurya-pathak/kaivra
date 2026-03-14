from dsa_anim.dsl.schema import ObjectType
from dsa_anim.qa.audit import _audit_overlaps, audit_scene_graph
from dsa_anim.scene_graph.models import ResolvedScene, SceneGraph, SceneNode
from dsa_anim.utils.geometry import Rect


def test_audit_reports_overlapping_visible_nodes():
    left = SceneNode(
        id="left",
        obj_type=ObjectType.BOX,
        rect=Rect(40, 40, 140, 80),
        default_visible=True,
    )
    right = SceneNode(
        id="right",
        obj_type=ObjectType.BOX,
        rect=Rect(120, 55, 140, 80),
        default_visible=True,
    )
    scene = ResolvedScene(
        id="overlap_scene",
        duration=1.0,
        nodes=[left, right],
        node_map={"left": left, "right": right},
        timeline=[],
    )
    graph = SceneGraph(
        width=400,
        height=200,
        fps=30,
        theme_name="modern",
        scenes=[scene],
    )

    findings = audit_scene_graph(graph, samples_per_scene=3)

    assert any(
        finding.kind == "overlap" and finding.node_ids == ("left", "right")
        for finding in findings
    )


def test_audit_ignores_transitional_overlap_during_motion():
    moving = SceneNode(
        id="moving",
        obj_type=ObjectType.BOX,
        rect=Rect(40, 40, 140, 80),
        default_visible=True,
        translate_x=40,
    )
    steady = SceneNode(
        id="steady",
        obj_type=ObjectType.BOX,
        rect=Rect(120, 55, 140, 80),
        default_visible=True,
    )
    findings = _audit_overlaps(
        "transition_scene",
        0.5,
        [moving, steady],
        {
            "moving": Rect(80, 40, 140, 80),
            "steady": Rect(120, 55, 140, 80),
        },
    )

    assert not any(finding.kind == "overlap" for finding in findings)
