from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from kaivra.mcp import workspace as workspace_module
from kaivra.mcp.workspace import KaivraWorkspace


def _check_animation(workspace: KaivraWorkspace, doc: dict) -> dict:
    return workspace.check_animation(dsl_json=json.dumps(doc))


def _assert_structured_edits(edits: list[dict]) -> None:
    required_keys = {"scene_id", "action", "object_id", "field", "suggested_value", "reason"}
    assert edits
    assert all(isinstance(edit, dict) for edit in edits)
    assert all(required_keys <= set(edit) for edit in edits)


def test_workspace_guided_flow_writes_files(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    added_theme = workspace.add_theme(
        name="Mint Breeze",
        base_theme="modern",
        overrides={
            "accent": "#14b8a6",
            "background_color": "#f4fffd",
            "box_border": "#0f766e",
        },
    )

    assert Path(added_theme["file_path"]).exists()

    # Write animation JSON directly (no scaffold)
    source_path = tmp_path / "animations" / "queue-basics.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"title": "Queue Basics", "theme": added_theme["theme_name"]},
                "scenes": [
                    {
                        "id": "enqueue",
                        "duration": "5s",
                        "objects": [
                            {"type": "box", "id": "q", "content": "Enqueue"},
                        ],
                        "animations": [{"action": "fade-in", "target": "q"}],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    checked = workspace.check_animation(file_path=str(source_path))
    assert checked["valid"] is True
    assert isinstance(checked["recommended_edits"], list)

    previewed = workspace.preview_animation(file_path=str(source_path))
    assert Path(previewed["html_path"]).exists()
    assert Path(previewed["preview_image_path"]).exists()

    rendered = workspace.render_animation(file_path=str(source_path), format="png")
    assert rendered["status"] == "ok"
    assert Path(rendered["artifact_path"]).exists()


def test_check_animation_warns_on_scene_pacing_and_narration_mismatch(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": True},
            "scenes": [
                {
                    "id": "too_short",
                    "duration": "3s",
                    "layout": "center",
                    "narration": (
                        "Queues remove the oldest item first while preserving the order that "
                        "items originally arrived in the line."
                    ),
                    "objects": [
                        {"id": "short_card", "type": "text", "content": "Queue rule"},
                    ],
                    "animations": [
                        {"action": "appear", "target": "short_card", "at": "0s"},
                    ],
                },
                {
                    "id": "too_long",
                    "duration": "21s",
                    "layout": "center",
                    "objects": [
                        {"id": "long_card", "type": "text", "content": "Long beat"},
                    ],
                    "animations": [
                        {"action": "appear", "target": "long_card", "at": "0s"},
                    ],
                },
            ],
        },
    )

    assert checked["valid"] is True
    assert any(
        "too_short pacing" in warning and "shorter" in warning for warning in checked["warnings"]
    )
    assert any(
        "too_long pacing" in warning and "longer" in warning for warning in checked["warnings"]
    )
    assert any("too_short narration" in warning for warning in checked["warnings"])
    _assert_structured_edits(checked["recommended_edits"])
    assert any(
        edit["scene_id"] == "too_short"
        and edit["field"] == "narration"
        and edit["action"] == "shorten_text"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_warns_when_body_text_duplicates_narration(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": True},
            "scenes": [
                {
                    "id": "redundant_copy",
                    "duration": "8s",
                    "layout": "center",
                    "narration": "A queue removes the oldest item first and keeps first in first out order.",
                    "objects": [
                        {
                            "id": "body_copy",
                            "type": "text",
                            "style": "body",
                            "content": "A queue removes the oldest item first and keeps first in first out order.",
                        },
                    ],
                    "animations": [
                        {"action": "appear", "target": "body_copy", "at": "0s"},
                    ],
                },
            ],
        },
    )

    assert checked["valid"] is True
    assert any("redundant_copy redundant_copy" in warning for warning in checked["warnings"])
    _assert_structured_edits(checked["recommended_edits"])
    assert any(
        edit["scene_id"] == "redundant_copy"
        and edit["object_id"] == "body_copy"
        and edit["field"] == "content"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_flags_internal_terms_for_layperson_audience(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "version": "1.2",
            "meta": {"theme": "modern", "audience": "layperson"},
            "scenes": [
                {
                    "id": "plain_english",
                    "duration": "8s",
                    "template": "one-column",
                    "narration": (
                        "The qa_harness reads logs from src/debug_agent.py, then sends the payload "
                        "to the backend service for remediation."
                    ),
                    "objects": [
                        {"id": "card", "type": "box", "content": "Fix flow"},
                    ],
                    "animations": [{"action": "fade-in", "target": "card", "duration": "0.5s"}],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert any("audience_language" in warning for warning in checked["warnings"])
    assert any("src/debug_agent.py" in warning for warning in checked["warnings"])
    assert any(edit["action"] == "simplify_language" for edit in checked["recommended_edits"])


def test_check_animation_annotates_narration_pacing_when_voice_retiming_is_enabled(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = workspace.check_animation(
        dsl_json=json.dumps(
            {
                "meta": {"theme": "modern", "show_narration": True},
                "scenes": [
                    {
                        "id": "voice_scene",
                        "duration": "4s",
                        "layout": "center",
                        "narration": (
                            "Now we walk through one concrete example, and then we generalize the same "
                            "pattern across every other connection in the layer."
                        ),
                        "objects": [
                            {"id": "voice_card", "type": "text", "content": "Worked example"},
                        ],
                        "animations": [
                            {"action": "appear", "target": "voice_card", "at": "0s"},
                        ],
                    }
                ],
            }
        ),
        voice=True,
    )

    assert checked["valid"] is True
    assert checked["summary"] == "Kaivra validation passed with 1 warning to review."
    assert any("Pre-retiming diagnostic:" in warning for warning in checked["warnings"])
    assert any(
        "Voice retiming will stretch the scene automatically" in warning
        for warning in checked["warnings"]
    )
    assert any(
        edit["scene_id"] == "voice_scene"
        and edit["field"] == "narration"
        and "less retiming" in edit["reason"]
        for edit in checked["recommended_edits"]
    )


def test_check_animation_warns_when_technical_narration_never_explains_purpose(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "bias_step",
                    "duration": "8s",
                    "layout": "center",
                    "narration": (
                        "Now add the bias. The weighted total is 0.47, the bias is 0.10, "
                        "and the pre-activation becomes 0.57."
                    ),
                    "objects": [
                        {"id": "sum_box", "type": "box", "content": "0.47 + 0.10 = 0.57"},
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "sum_box", "at": "0s", "duration": "0.5s"},
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert any("explanatory_narration" in warning for warning in checked["warnings"])
    assert any(
        edit["scene_id"] == "bias_step"
        and edit["field"] == "narration"
        and edit["action"] == "expand_text"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_skips_explanatory_warning_when_scene_explains_why(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_subtitles": False},
            "scenes": [
                {
                    "id": "bias_step",
                    "duration": "8s",
                    "layout": "center",
                    "narration": (
                        "Now add the bias because it shifts the neuron's baseline, which means "
                        "the model can control how easily this feature turns on."
                    ),
                    "objects": [
                        {"id": "sum_box", "type": "box", "content": "0.47 + 0.10 = 0.57"},
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "sum_box", "at": "0s", "duration": "0.5s"},
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert not any("explanatory_narration" in warning for warning in checked["warnings"])


def test_check_animation_skips_explanatory_warning_for_outcome_language_with_tracker_tokens(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "version": "1.2",
            "meta": {"theme": "modern", "continuity": True},
            "objects": [
                {
                    "id": "chapters",
                    "type": "group",
                    "layout": {"type": "carousel"},
                    "children": [
                        {"id": "step_one", "type": "token", "token_id": 1, "content": "Intro"},
                        {"id": "step_two", "type": "token", "token_id": 2, "content": "Outcome"},
                    ],
                }
            ],
            "scenes": [
                {
                    "id": "outcome_scene",
                    "duration": "8s",
                    "template": "one-column",
                    "narration": (
                        "The result is faster diagnosis and cleaner handoffs, instead of waiting "
                        "for a manual reset before anyone can move forward."
                    ),
                    "objects": [
                        {"id": "result_box", "type": "box", "content": "Faster diagnosis"},
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "result_box", "duration": "0.5s"},
                        {"action": "highlight", "target": "step_two", "duration": "0.4s"},
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert not any("explanatory_narration" in warning for warning in checked["warnings"])


def test_check_animation_warns_when_hidden_object_has_no_reveal_animation(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "missing_reveal",
                    "duration": "6s",
                    "auto_visible": False,
                    "layout": "center",
                    "objects": [
                        {"id": "title", "type": "text", "content": "Hidden forever"},
                    ],
                    "animations": [],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert any(
        "has no visibility animation and will never appear" in warning
        for warning in checked["warnings"]
    )
    assert any(
        edit["scene_id"] == "missing_reveal"
        and edit["object_id"] == "title"
        and edit["action"] == "add_visibility_animation"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_respects_group_inherited_reveal_for_hidden_children(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "group_reveal",
                    "duration": "6s",
                    "auto_visible": False,
                    "layout": "center",
                    "objects": [
                        {
                            "id": "cluster",
                            "type": "group",
                            "layout": "flow",
                            "children": [
                                {"id": "child_a", "type": "box", "content": "A"},
                                {"id": "child_b", "type": "box", "content": "B"},
                            ],
                        }
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "cluster", "at": "0s", "duration": "0.6s"},
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert not any("child_a" in warning for warning in checked["warnings"])
    assert not any("child_b" in warning for warning in checked["warnings"])


def test_check_animation_write_back_enables_layout_group_visibility(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    source_path = tmp_path / "animations" / "visibility-fix.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"theme": "modern", "show_narration": False},
                "scenes": [
                    {
                        "id": "blocked_child",
                        "duration": "6s",
                        "auto_visible": False,
                        "layout": "center",
                        "objects": [
                            {
                                "id": "cluster",
                                "type": "group",
                                "layout": "flow",
                                "children": [
                                    {"id": "child_box", "type": "box", "content": "Child"},
                                ],
                            }
                        ],
                        "animations": [
                            {
                                "action": "fade-in",
                                "target": "child_box",
                                "at": "0s",
                                "duration": "0.6s",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    checked = workspace.check_animation(file_path=str(source_path), write_back=True)
    rewritten = json.loads(source_path.read_text(encoding="utf-8"))

    assert checked["valid"] is True
    assert checked["applied_fixes"]
    assert any(
        fix["action"] == "enable_layout_group_visibility" and fix["object_id"] == "cluster"
        for fix in checked["applied_fixes"]
    )
    assert rewritten["scenes"][0]["objects"][0]["visible"] is True
    assert not checked["finding_groups"]["blocking"]


def test_check_animation_reports_narration_timing_and_can_stretch_scene(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    source_path = tmp_path / "animations" / "timing-fix.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"theme": "modern", "show_narration": True},
                "scenes": [
                    {
                        "id": "voice_scene",
                        "duration": "4s",
                        "template": "one-column",
                        "narration": (
                            "This is a deliberately long spoken explanation that should take "
                            "longer than four seconds to read comfortably out loud."
                        ),
                        "objects": [
                            {"id": "voice_card", "type": "text", "content": "Worked example"},
                        ],
                        "animations": [{"action": "appear", "target": "voice_card", "at": "0s"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    checked = workspace.check_animation(file_path=str(source_path), write_back=True, voice=True)
    rewritten = json.loads(source_path.read_text(encoding="utf-8"))

    assert checked["narration_timing"]
    assert checked["narration_timing"][0]["scene_id"] == "voice_scene"
    assert checked["narration_timing"][0]["needs_review"] is False
    assert float(checked["narration_timing"][0]["suggested_duration_seconds"]) >= 8.0
    assert any(
        fix["action"] == "stretch_scene_to_narration" and fix["scene_id"] == "voice_scene"
        for fix in checked["applied_fixes"]
    )
    assert rewritten["scenes"][0]["duration"] != "4s"


def test_check_animation_warns_when_scene_crossfade_and_object_reveal_stack(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "setup",
                    "duration": "4s",
                    "layout": "center",
                    "objects": [{"id": "setup_box", "type": "box", "content": "Setup"}],
                    "animations": [{"action": "appear", "target": "setup_box", "at": "0s"}],
                    "transition": {"type": "fade", "duration": "1s"},
                },
                {
                    "id": "reveal_scene",
                    "duration": "4s",
                    "auto_visible": False,
                    "layout": "center",
                    "objects": [{"id": "value_box", "type": "box", "content": "Value"}],
                    "animations": [
                        {
                            "action": "fade-in",
                            "target": "value_box",
                            "at": "0.2s",
                            "duration": "0.6s",
                        }
                    ],
                },
            ],
        },
    )

    assert checked["valid"] is True
    assert any(
        "look like it appears twice" in warning and "value_box" in warning
        for warning in checked["warnings"]
    )


def test_check_animation_warns_when_group_and_child_reveal_overlap(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "nested_reveal",
                    "duration": "5s",
                    "auto_visible": False,
                    "layout": "center",
                    "objects": [
                        {
                            "id": "cluster",
                            "type": "group",
                            "layout": "flow",
                            "children": [
                                {"id": "child_box", "type": "box", "content": "Child"},
                            ],
                        }
                    ],
                    "animations": [
                        {"action": "fade-in", "target": "cluster", "at": "0s", "duration": "0.8s"},
                        {
                            "action": "fade-in",
                            "target": "child_box",
                            "at": "0.1s",
                            "duration": "0.6s",
                        },
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is True
    assert any(
        "Group `cluster` and child `child_box` both reveal during the same window" in warning
        for warning in checked["warnings"]
    )


def test_check_animation_warns_when_narrated_scenes_repeat_same_scaffold(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    shared_objects = [
        {"id": "process_heading", "type": "text", "content": "Heading"},
        {
            "id": "process_panel",
            "type": "group",
            "layout": "stack",
            "children": [
                {"id": "process_stage_badge", "type": "token", "content": "Step"},
                {
                    "id": "process_lane",
                    "type": "group",
                    "layout": "flow",
                    "children": [
                        {"id": "process_context_token", "type": "token", "content": "Context"},
                        {"id": "process_focus_card", "type": "box", "content": "Focus"},
                        {"id": "process_outcome_token", "type": "token", "content": "Outcome"},
                    ],
                },
            ],
        },
    ]
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "beat_1",
                    "duration": "6s",
                    "layout": "center",
                    "narration": "First narrated beat with a scaffold.",
                    "objects": shared_objects,
                },
                {
                    "id": "beat_2",
                    "duration": "6s",
                    "layout": "center",
                    "narration": "Second narrated beat with the same scaffold.",
                    "objects": shared_objects,
                },
                {
                    "id": "beat_3",
                    "duration": "6s",
                    "layout": "center",
                    "narration": "Third narrated beat with the same scaffold.",
                    "objects": shared_objects,
                },
            ],
        },
    )

    assert checked["valid"] is True
    assert any("reuse the same local object scaffold" in warning for warning in checked["warnings"])


def test_check_animation_blocks_replace_when_objects_are_not_aligned(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "scenes": [
                {
                    "id": "replace_misaligned",
                    "duration": "6s",
                    "layout": {
                        "type": "grid",
                        "columns": 2,
                        "rows": 1,
                    },
                    "objects": [
                        {"id": "old_val", "type": "box", "content": "2 + 2", "grid": {"col": 1}},
                        {"id": "new_val", "type": "box", "content": "4", "grid": {"col": 2}},
                    ],
                    "animations": [
                        {
                            "action": "replace",
                            "target": "old_val",
                            "with": "new_val",
                            "at": "1s",
                            "duration": "0.8s",
                        },
                    ],
                }
            ],
        },
    )

    assert checked["valid"] is False
    assert any("Align them first." in issue for issue in checked["blocking_issues"])
    assert any(
        edit["action"] == "align_replacement" and edit["object_id"] == "new_val"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_blocks_invalid_connectors_and_animation_targets(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(
        workspace,
        {
            "meta": {"theme": "modern", "show_narration": False},
            "objects": [
                {"id": "shared_node", "type": "text", "content": "Shared"},
            ],
            "scenes": [
                {
                    "id": "broken_refs",
                    "duration": "6s",
                    "layout": "center",
                    "objects": [
                        {"id": "node_a", "type": "box", "content": "A"},
                        {
                            "id": "edge_1",
                            "type": "connector",
                            "from": "node_a",
                            "to": "node_missing",
                        },
                    ],
                    "animations": [
                        {"action": "appear", "target": "node_missing", "at": "0s"},
                        {
                            "action": "move-to",
                            "target": "node_a",
                            "to_id": "shared_nod",
                            "at": "1s",
                        },
                    ],
                },
            ],
        },
    )

    assert checked["valid"] is False
    assert any("Connector `edge_1`" in issue for issue in checked["blocking_issues"])
    assert any(
        "targets missing object `node_missing`" in issue for issue in checked["blocking_issues"]
    )
    assert any(
        "moves toward missing object `shared_nod`" in issue for issue in checked["blocking_issues"]
    )
    _assert_structured_edits(checked["recommended_edits"])
    assert any(
        edit["action"] == "fix_connector_endpoint"
        and edit["object_id"] == "edge_1"
        and edit["field"] == "scenes[0].objects[1].to"
        for edit in checked["recommended_edits"]
    )
    assert any(
        edit["action"] == "replace_target"
        and edit["field"] == "scenes[0].animations[1].to_id"
        and edit["suggested_value"] == "shared_node"
        for edit in checked["recommended_edits"]
    )


def test_workspace_render_and_preview_find_nearest_workspace_theme_for_nested_docs(
    tmp_path: Path,
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    theme = workspace.add_theme(
        name="Nested Mint",
        base_theme="modern",
        overrides={"accent": "#10b981"},
    )
    source_path = tmp_path / "animations" / "nested" / "demo.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"title": "Nested Theme", "theme": theme["theme_name"]},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "1s",
                        "objects": [{"type": "text", "content": "Hello"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    checked = workspace.check_animation(file_path=str(source_path))
    previewed = workspace.preview_animation(file_path=str(source_path))
    rendered = workspace.render_animation(file_path=str(source_path), format="png")

    assert checked["valid"] is True
    assert Path(previewed["html_path"]).exists()
    assert Path(rendered["artifact_path"]).exists()


def test_preview_and_render_use_document_workspace_when_server_root_is_elsewhere(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (project_root / "animations").mkdir(parents=True)
    source_path = project_root / "animations" / "demo.json"
    source_path.write_text(
        json.dumps(
            {
                "version": "1.2",
                "meta": {"title": "Doc Workspace", "theme": "modern"},
                "scenes": [
                    {
                        "id": "intro",
                        "duration": "1s",
                        "objects": [{"type": "text", "content": "Hello"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    workspace = KaivraWorkspace(tmp_path / "wrong-root")
    previewed = workspace.preview_animation(file_path=str(source_path))
    rendered = workspace.render_animation(file_path=str(source_path), format="png")

    assert Path(previewed["html_path"]).parent == project_root / "artifacts" / "previews"
    assert Path(rendered["artifact_path"]).parent == project_root / "artifacts" / "renders"


def test_download_model_smoke_installs_and_reuses_local_archive(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    archive_root = tmp_path / "archive-root" / "bundle"
    archive_root.mkdir(parents=True)
    (archive_root / "voice.onnx").write_bytes(b"onnx")
    (archive_root / "tokens.txt").write_text("a\n", encoding="utf-8")
    (archive_root / "espeak-ng-data").mkdir()
    (archive_root / "espeak-ng-data" / "placeholder").write_text("ok", encoding="utf-8")

    archive_path = tmp_path / "bundle.tar.bz2"
    with tarfile.open(archive_path, "w:bz2") as archive:
        archive.add(archive_root, arcname=archive_root.name)

    target_dir = tmp_path / "models" / "amy"
    installed = workspace.download_model(
        model_name="vits-piper-en_US-amy-low",
        target_dir=target_dir,
        archive_url=archive_path.as_uri(),
    )
    reused = workspace.download_model(
        model_name="vits-piper-en_US-amy-low",
        target_dir=target_dir,
        archive_url=archive_path.as_uri(),
    )

    assert installed["status"] == "ok"
    assert installed["downloaded"] is True
    assert Path(installed["model_path"]).exists()
    assert Path(installed["tokens_path"]).exists()
    assert Path(installed["data_dir"]).is_dir()
    assert reused["downloaded"] is False


def test_preflight_reports_missing_cairo_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    real_import_module = workspace_module.importlib.import_module
    expected_fix = workspace_module._platform_fix_commands()["pycairo"][0]

    def fake_import_module(name: str):
        if name == "cairo":
            raise ImportError("No module named cairo")
        return real_import_module(name)

    monkeypatch.setattr(workspace_module.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("preview", needs_cairo=True)

    assert "preview" in str(excinfo.value)
    assert expected_fix in str(excinfo.value)


def test_preflight_reports_missing_ffmpeg_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    expected_fix = workspace_module._platform_fix_commands()["ffmpeg"][0]

    def fake_command_available(command: str) -> tuple[bool, str]:
        if command == "ffmpeg":
            return False, "ffmpeg was not found on PATH."
        return True, f"{command} is available."

    monkeypatch.setattr(workspace_module, "_command_available", fake_command_available)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("render", needs_cairo=False, needs_ffmpeg=True)

    assert "ffmpeg was not found on PATH" in str(excinfo.value)
    assert expected_fix in str(excinfo.value)


def test_preflight_reports_missing_ffprobe_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = KaivraWorkspace(tmp_path)
    expected_fix = workspace_module._platform_fix_commands()["ffprobe"][0]

    def fake_command_available(command: str) -> tuple[bool, str]:
        if command == "ffprobe":
            return False, "ffprobe was not found on PATH."
        return True, f"{command} is available."

    monkeypatch.setattr(workspace_module, "_command_available", fake_command_available)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("quick-render", needs_cairo=False, needs_ffprobe=True)

    assert "ffprobe was not found on PATH" in str(excinfo.value)
    assert expected_fix in str(excinfo.value)


def test_install_mcp_config_updates_claude_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / ".claude.json"
    config_path.write_text(json.dumps({"projects": {"demo": {}}}), encoding="utf-8")
    monkeypatch.setattr(workspace_module, "_DEFAULT_CLAUDE_CONFIG_PATH", config_path)
    monkeypatch.setattr(
        workspace_module,
        "_resolve_mcp_server_command",
        lambda: "/tmp/fake-venv/bin/kaivra-mcp",
    )

    result = KaivraWorkspace(tmp_path).install_mcp_config(client="claude-code")

    updated = json.loads(config_path.read_text(encoding="utf-8"))
    assert result["client"] == "claude-code"
    assert updated["projects"] == {"demo": {}}
    assert updated["mcpServers"]["kaivra"]["command"] == "/tmp/fake-venv/bin/kaivra-mcp"


def test_install_mcp_config_auto_prefers_existing_cursor_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude_path = tmp_path / ".claude.json"
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(workspace_module, "_DEFAULT_CLAUDE_CONFIG_PATH", claude_path)
    monkeypatch.setattr(workspace_module, "_DEFAULT_CURSOR_CONFIG_PATH", cursor_path)
    monkeypatch.setattr(
        workspace_module,
        "_resolve_mcp_server_command",
        lambda: "/tmp/fake-venv/bin/kaivra-mcp",
    )

    result = KaivraWorkspace(tmp_path).install_mcp_config(client="auto")

    updated = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert result["client"] == "cursor"
    assert updated["mcpServers"]["kaivra"]["type"] == "stdio"


def test_download_model_extracts_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive_path = tmp_path / "bundle.tar.bz2"
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "en_US-amy-low.onnx").write_bytes(b"onnx")
    (bundle_dir / "tokens.txt").write_text("a b c", encoding="utf-8")
    (bundle_dir / "espeak-ng-data").mkdir()
    (bundle_dir / "espeak-ng-data" / "voice").write_text("demo", encoding="utf-8")

    with tarfile.open(archive_path, "w:bz2") as archive:
        archive.add(bundle_dir, arcname="vits-piper-en_US-amy-low")

    def fake_download(url: str, destination: Path) -> None:
        destination.write_bytes(archive_path.read_bytes())

    monkeypatch.setattr(workspace_module, "_download_file", fake_download)

    result = KaivraWorkspace(tmp_path).download_model(target_dir=tmp_path / "models")

    assert result["downloaded"] is True
    assert Path(result["model_path"]).exists()
    assert Path(result["tokens_path"]).exists()
    assert Path(result["data_dir"]).is_dir()


def test_voice_sync_findings_flag_unmatched_targets(tmp_path: Path) -> None:
    """ElevenLabs sync audit warns when narration misses animation targets."""
    workspace = KaivraWorkspace(tmp_path)
    doc = {
        "version": "1.2",
        "meta": {"title": "Sync Test", "theme": "modern"},
        "scenes": [
            {
                "id": "intro",
                "duration": "8s",
                "template": "one-column",
                "narration": "The backend component handles incoming traffic smoothly.",
                "objects": [
                    {"type": "box", "id": "server", "content": "Server"},
                    {"type": "box", "id": "traffic", "content": "Traffic"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "server", "at": "0s", "duration": "0.5s"},
                    {"action": "fade-in", "target": "traffic", "at": "2s", "duration": "0.5s"},
                ],
            }
        ],
    }
    result = workspace.check_animation(
        dsl_json=json.dumps(doc),
        voice=True,
        voice_provider="elevenlabs",
    )

    voice_findings = [f for f in result["audit_findings"] if "voice_sync" in f]
    # "server" has no keyword overlap with narration ("backend component" ≠ "Server")
    assert any("server" in f for f in voice_findings)
    assert any("Missing target terms: server." in f for f in voice_findings)
    assert any("Narration terms seen:" in f for f in voice_findings)
    # "traffic" DOES overlap with narration
    assert not any("'traffic'" in f for f in voice_findings)
    assert result["finding_groups"]["voice_sync"]


def test_voice_sync_findings_warn_for_local_voice(tmp_path: Path) -> None:
    """Local voice still benefits from keyword-match warnings during authoring."""
    workspace = KaivraWorkspace(tmp_path)
    doc = {
        "version": "1.2",
        "meta": {"title": "Sync Test", "theme": "modern"},
        "scenes": [
            {
                "id": "intro",
                "duration": "8s",
                "template": "one-column",
                "narration": "The backend component handles incoming traffic.",
                "objects": [
                    {"type": "box", "id": "server", "content": "Server"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "server", "at": "0s", "duration": "0.5s"},
                ],
            }
        ],
    }

    result = workspace.check_animation(
        dsl_json=json.dumps(doc),
        voice=True,
        voice_provider="local",
    )

    voice_findings = [f for f in result["audit_findings"] if "voice_sync" in f]
    assert any("'server'" in f for f in voice_findings)
    assert any("scene-level timing" in f for f in voice_findings)


def test_voice_sync_findings_skip_connectors_and_tracker_tokens(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    doc = {
        "version": "1.2",
        "meta": {"title": "Sync Test", "theme": "modern"},
        "objects": [
            {
                "id": "chapters",
                "type": "group",
                "layout": {"type": "carousel"},
                "children": [
                    {"type": "token", "id": "step_intro", "token_id": 1, "content": "Intro"},
                ],
            }
        ],
        "scenes": [
            {
                "id": "intro",
                "duration": "8s",
                "template": "one-column",
                "narration": "The backend component handles incoming traffic.",
                "objects": [
                    {"type": "box", "id": "server", "content": "Server"},
                    {"type": "box", "id": "client", "content": "Client"},
                    {"type": "connector", "id": "server_link", "from": "client", "to": "server"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "server", "duration": "0.5s"},
                    {"action": "draw", "target": "server_link", "duration": "0.4s"},
                    {"action": "highlight", "target": "step_intro", "duration": "0.4s"},
                ],
            }
        ],
    }

    result = workspace.check_animation(
        dsl_json=json.dumps(doc),
        voice=True,
        voice_provider="local",
    )

    voice_findings = [f for f in result["audit_findings"] if "voice_sync" in f]
    assert any("'server'" in f for f in voice_findings)
    assert not any("server_link" in f for f in voice_findings)
    assert not any("step_intro" in f for f in voice_findings)


def test_voice_sync_findings_absent_without_voice_flag(tmp_path: Path) -> None:
    """check_animation without voice=True should not emit voice_sync findings."""
    workspace = KaivraWorkspace(tmp_path)
    doc = {
        "version": "1.2",
        "meta": {"title": "Sync Test", "theme": "modern"},
        "scenes": [
            {
                "id": "intro",
                "duration": "8s",
                "template": "one-column",
                "narration": "The backend component handles incoming traffic.",
                "objects": [
                    {"type": "box", "id": "server", "content": "Server"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "server", "at": "0s", "duration": "0.5s"},
                ],
            }
        ],
    }
    result = workspace.check_animation(dsl_json=json.dumps(doc), voice=False)

    voice_findings = [f for f in result["audit_findings"] if "voice_sync" in f]
    assert voice_findings == []


def test_check_animation_warns_when_continuity_id_changes_content_too_much(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    result = _check_animation(
        workspace,
        {
            "version": "1.2",
            "meta": {"theme": "modern", "continuity": True},
            "scenes": [
                {
                    "id": "scene_a",
                    "duration": "5s",
                    "template": "one-column",
                    "objects": [
                        {"type": "box", "id": "status", "content": "Queued request"},
                    ],
                    "animations": [{"action": "fade-in", "target": "status", "duration": "0.3s"}],
                },
                {
                    "id": "scene_b",
                    "duration": "5s",
                    "template": "one-column",
                    "objects": [
                        {"type": "box", "id": "status", "content": "GPU memory scheduler"},
                    ],
                    "animations": [{"action": "fade-in", "target": "status", "duration": "0.3s"}],
                },
            ],
        },
    )

    assert result["valid"] is True
    assert result["finding_groups"]["continuity"]
    assert any("changes sharply" in finding for finding in result["finding_groups"]["continuity"])
    assert any(
        edit["action"] == "split_continuity_id" and edit["object_id"] == "status"
        for edit in result["recommended_edits"]
    )


def test_check_animation_skips_continuity_warning_for_scene_titles(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    result = _check_animation(
        workspace,
        {
            "version": "1.2",
            "meta": {"theme": "modern", "continuity": True},
            "scenes": [
                {
                    "id": "scene_a",
                    "duration": "5s",
                    "template": "one-column",
                    "objects": [
                        {"type": "text", "id": "title", "content": "Diagnose The Failure"},
                    ],
                    "animations": [{"action": "fade-in", "target": "title", "duration": "0.3s"}],
                },
                {
                    "id": "scene_b",
                    "duration": "5s",
                    "template": "one-column",
                    "objects": [
                        {"type": "text", "id": "title", "content": "Remediate Test Automation"},
                    ],
                    "animations": [{"action": "fade-in", "target": "title", "duration": "0.3s"}],
                },
            ],
        },
    )

    assert result["valid"] is True
    assert not result["finding_groups"]["continuity"]
