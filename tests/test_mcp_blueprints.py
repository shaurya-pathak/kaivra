from __future__ import annotations

import pytest

from kaivra.dsl.schema import AnimAction, ObjectType, parse_duration
from kaivra.mcp.blueprints import SUPPORTED_PATTERNS, build_starter_document
from kaivra.qa.audit import audit_scene_graph
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.themes.registry import get_theme


def _walk_objects(objects):
    for obj in objects:
        yield obj
        if obj.children:
            yield from _walk_objects(obj.children)


@pytest.mark.parametrize("pattern", SUPPORTED_PATTERNS)
def test_starter_blueprints_build_without_audit_errors(pattern: str) -> None:
    doc = build_starter_document(
        title="MCP Starter",
        pattern=pattern,
        beats=[
            {"title": "Input", "detail": "Set the context for the animation."},
            {"title": "Change", "detail": "Show the key transition or behavior."},
            {"title": "Result", "detail": "Land on the final takeaway."},
        ],
        theme="modern",
        audience="new learners",
        include_narration=False,
    )

    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)
    findings = audit_scene_graph(graph, samples_per_scene=4)

    assert all(finding.severity != "error" for finding in findings)
    assert doc.scenes


@pytest.mark.parametrize("pattern", SUPPORTED_PATTERNS)
def test_narrated_starters_omit_body_copy_and_captions(pattern: str) -> None:
    beats = [
        {"title": "Input", "detail": "Set the context for the animation."},
        {"title": "Change", "detail": "Show the key transition or behavior."},
    ]
    doc = build_starter_document(
        title="Narrated Starter",
        pattern=pattern,
        beats=beats,
        theme="modern",
        audience="new learners",
        include_narration=True,
    )

    objects = list(_walk_objects(doc.scenes[0].objects))
    styles = {obj.style for obj in objects if obj.style}
    contents = {obj.content for obj in objects if obj.content}
    ids = {obj.id for obj in objects if obj.id}

    assert "body" not in styles
    assert "caption" not in styles
    assert "Built for new learners." not in contents
    assert beats[0]["detail"] not in contents
    assert not any("caption" in object_id for object_id in ids)
    assert doc.meta.show_subtitles is False


def test_narrated_starters_can_opt_into_subtitles_explicitly() -> None:
    doc = build_starter_document(
        title="Narrated Starter",
        pattern="visual_explainer",
        beats=[
            {"title": "Input", "detail": "Set the context for the animation."},
        ],
        theme="modern",
        audience=None,
        include_narration=True,
        show_subtitles=True,
    )

    assert doc.meta.show_subtitles is True


def test_visual_explainer_uses_connectors_and_draw_animations() -> None:
    doc = build_starter_document(
        title="Visual Starter",
        pattern="visual_explainer",
        beats=[
            {"title": "Observe", "detail": "Notice the signal entering the system."},
            {"title": "Route", "detail": "Show how the key relationship moves forward."},
        ],
        theme="modern",
        audience=None,
        include_narration=True,
    )

    scene = doc.scenes[0]
    objects = list(_walk_objects(scene.objects))
    connector_ids = {obj.id for obj in objects if obj.type == ObjectType.CONNECTOR and obj.id}
    draw_targets = {
        anim.target
        for anim in scene.animations
        if anim.action == AnimAction.DRAW and isinstance(anim.target, str)
    }

    assert connector_ids
    assert draw_targets
    assert draw_targets <= connector_ids


def test_narrated_starters_use_progressive_reveal_and_conversational_narration() -> None:
    detail = "Now we zoom in on one weighted sum before we generalize the same pattern."
    doc = build_starter_document(
        title="Forward Propagation",
        pattern="visual_explainer",
        beats=[
            {"title": "Weighted Sum", "detail": detail},
        ],
        theme="modern",
        audience="engineers learning deep learning",
        include_narration=True,
    )

    scene = doc.scenes[0]
    fade_targets = {
        anim.target
        for anim in scene.animations
        if anim.action == AnimAction.FADE_IN and isinstance(anim.target, str)
    }

    assert scene.auto_visible is False
    assert fade_targets
    assert scene.narration == detail
    assert "engineers learning deep learning" not in scene.narration
    assert not scene.narration.startswith("Weighted Sum.")


def test_default_pattern_follows_narration_even_when_pacing_changes() -> None:
    narrated = build_starter_document(
        title="Default Narrated Starter",
        pattern=None,
        beats=[
            {"title": "Observe", "detail": "Notice the signal entering the system."},
        ],
        theme="modern",
        audience=None,
        include_narration=True,
        pacing="quick-demo",
    )
    silent = build_starter_document(
        title="Default Silent Starter",
        pattern=None,
        beats=[
            {"title": "Observe", "detail": "Notice the signal entering the system."},
        ],
        theme="modern",
        audience=None,
        include_narration=False,
        pacing="educational",
    )

    narrated_ids = {obj.id for obj in _walk_objects(narrated.scenes[0].objects) if obj.id}
    silent_ids = {obj.id for obj in _walk_objects(silent.scenes[0].objects) if obj.id}
    silent_styles = {obj.style for obj in _walk_objects(silent.scenes[0].objects) if obj.style}

    assert "visual_focus_card" in narrated_ids
    assert "visual_source_link" in narrated_ids
    assert "algorithm_current_card" in silent_ids
    assert "algorithm_prev_link" in silent_ids
    assert "body" in silent_styles


def test_pacing_changes_timing_without_overriding_visual_pattern_shape() -> None:
    kwargs = {
        "title": "Routing Signals",
        "pattern": "visual_explainer",
        "beats": [
            {"title": "Observe", "detail": "Notice the signal entering the system."},
        ],
        "theme": "modern",
        "audience": None,
        "include_narration": True,
    }
    educational = build_starter_document(**kwargs, pacing="educational")
    quick_demo = build_starter_document(**kwargs, pacing="quick-demo")

    educational_ids = {obj.id for obj in _walk_objects(educational.scenes[0].objects) if obj.id}
    quick_demo_ids = {obj.id for obj in _walk_objects(quick_demo.scenes[0].objects) if obj.id}
    educational_draw_targets = {
        anim.target
        for anim in educational.scenes[0].animations
        if anim.action == AnimAction.DRAW and isinstance(anim.target, str)
    }
    quick_demo_draw_targets = {
        anim.target
        for anim in quick_demo.scenes[0].animations
        if anim.action == AnimAction.DRAW and isinstance(anim.target, str)
    }

    assert educational_ids == quick_demo_ids
    assert educational_draw_targets == quick_demo_draw_targets
    assert parse_duration(educational.scenes[0].duration) > parse_duration(
        quick_demo.scenes[0].duration
    )
    assert educational.meta.continuity_duration != quick_demo.meta.continuity_duration
    assert educational.scenes[0].focus_style is not None
    assert quick_demo.scenes[0].focus_style is not None
    assert educational.scenes[0].focus_style.duration != quick_demo.scenes[0].focus_style.duration


@pytest.mark.parametrize("pattern", ["algorithm_walkthrough", "architecture_explainer"])
def test_connector_targets_stay_valid_for_visual_patterns(pattern: str) -> None:
    doc = build_starter_document(
        title="Connected Starter",
        pattern=pattern,
        beats=[
            {"title": "Input", "detail": "Set the context for the animation."},
            {"title": "Change", "detail": "Show the key transition or behavior."},
            {"title": "Result", "detail": "Land on the final takeaway."},
        ],
        theme="modern",
        audience="new learners",
        include_narration=True,
    )

    for scene in doc.scenes:
        objects = list(_walk_objects(scene.objects))
        ids = {obj.id for obj in objects if obj.id}
        connector_ids = set()
        for obj in objects:
            if obj.type != ObjectType.CONNECTOR:
                continue
            assert obj.from_id in ids
            assert obj.to_id in ids
            if obj.id:
                connector_ids.add(obj.id)

        draw_targets = {
            anim.target
            for anim in scene.animations
            if anim.action == AnimAction.DRAW and isinstance(anim.target, str)
        }
        assert draw_targets <= connector_ids


def test_legacy_process_explainer_alias_maps_to_non_narrated_default() -> None:
    doc = build_starter_document(
        title="Captioned Starter",
        pattern="process_explainer",
        beats=[
            {"title": "Input", "detail": "Set the context for the animation."},
            {"title": "Change", "detail": "Show the key transition or behavior."},
            {"title": "Result", "detail": "Land on the final takeaway."},
        ],
        theme="modern",
        audience="new learners",
        include_narration=False,
    )

    object_ids = {obj.id for obj in _walk_objects(doc.scenes[0].objects) if obj.id}
    graph = build_scene_graph(doc, get_theme(doc.meta.theme))
    findings = audit_scene_graph(graph, samples_per_scene=4)

    assert "algorithm_panel" in object_ids
    assert "process_panel" not in object_ids
    assert all(finding.severity != "error" for finding in findings)
    first_scene = graph.scenes[0]
    caption = first_scene.node_map["beat_01_caption"]
    steps = first_scene.node_map["steps"]
    assert caption.rect.bottom <= steps.rect.y
