from __future__ import annotations

from pathlib import Path

from kaivra.mcp.resources import read_resource
from kaivra.mcp.server import KaivraMCPServer, _summarize_tool_result


def test_server_initialization_and_tool_call(tmp_path: Path) -> None:
    server = KaivraMCPServer(workspace_root=str(tmp_path))

    init_response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )[0]
    assert init_response["result"]["serverInfo"]["name"] == "kaivra-local-mcp"
    instructions = init_response["result"]["instructions"]
    assert "write the animation JSON directly" in instructions
    assert "fade-in" in instructions
    assert "draw" in instructions
    assert "continuity" in instructions
    assert "conversational spoken English" in instructions
    assert "Template vs layout" in instructions
    assert "Connector overlap" in instructions
    assert "Narration sync" in instructions
    assert "spoken_forms" in instructions
    assert "scene-level timing" in instructions
    assert "persistent document-level objects" in instructions

    assert (
        server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        == []
    )

    tools_response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
    )[0]
    tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
    assert "add_theme" in tool_names
    assert "render_animation" in tool_names
    assert "start_animation" not in tool_names
    assert "quick_render" not in tool_names

    resources_response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        }
    )[0]
    resource_names = {resource["name"] for resource in resources_response["result"]["resources"]}
    assert "authoring_profile" in resource_names
    assert "example_api_how_it_works" in resource_names
    assert "example_forward_propagation" in resource_names


def test_resource_guidance_promotes_visual_explainers_and_examples_as_shape_references() -> None:
    authoring = read_resource("kaivra://authoring-profile")["contents"][0]["text"]
    pattern_catalog = read_resource("kaivra://pattern-catalog")["contents"][0]["text"]
    examples = read_resource("kaivra://example-catalog")["contents"][0]["text"]
    api_example = read_resource("kaivra://example/api_how_it_works")["contents"][0]["text"]

    assert "visual_explainer" in authoring
    assert "educational" in authoring
    assert "fade-in" in authoring
    assert "same `id` and `content`" in authoring
    assert "draw" in authoring
    assert "carousel" in authoring
    assert "template" in authoring
    assert "visible: true" in authoring
    assert "persistent objects" in authoring
    assert "Voice Sync Checklist" in authoring
    assert "positional matching" in authoring
    assert "algorithm_walkthrough" in pattern_catalog
    assert "authoring patterns, not generated scaffolds" in pattern_catalog
    assert "BAD: Generic repeated scene" in examples
    assert "GOOD: Rewritten scene" in examples
    assert "Continuity Carry-Over" in examples
    assert '"version": "1.2"' in examples
    assert '"title": "How an API Works"' in api_example


def test_check_animation_summary_mentions_warning_count() -> None:
    summary = _summarize_tool_result(
        "check_animation",
        {
            "valid": True,
            "finding_groups": {
                "blocking": [],
                "quality": ["warning one"],
                "voice_sync": ["voice warning"],
                "continuity": ["continuity warning"],
            },
            "recommended_edits": [
                {
                    "action": "enable_layout_group_visibility",
                    "field": "scenes[0].objects",
                    "reason": "Set visible on layout-only group.",
                }
            ],
        },
    )
    assert "Animation validated with 3 warning(s)." in summary
    assert "- warning one" in summary
    assert "**Voice sync:**" in summary
    assert "- voice warning" in summary
    assert "**Continuity:**" in summary
    assert "- continuity warning" in summary
    assert "enable_layout_group_visibility on scenes[0].objects" in summary


def test_plan_animation_summary_mentions_voice_sync_guidance() -> None:
    summary = _summarize_tool_result(
        "plan_animation",
        {
            "status": "ok",
            "suggested_meta": {
                "title": "Queues",
                "theme": "modern",
                "pacing": "balanced",
                "continuity": True,
                "show_subtitles": False,
            },
            "draft_defaults": {
                "audience": "general audience",
                "detail_level": "balanced",
                "voice_mode": "captions",
                "pattern": "visual_explainer",
                "theme": "modern",
                "num_beats": "auto",
            },
            "questions": [
                {"id": "audience"},
                {"id": "detail_level"},
                {"id": "voice_mode"},
            ],
        },
    )

    assert "mirror on-screen keywords" in summary
    assert "spoken_forms" in summary
    assert "Questions to collect:" in summary
    assert "- audience:" in summary
    assert "- detail_level:" in summary
    assert "- voice_mode:" in summary
    assert "Draft defaults:" in summary
    assert "Prefer persistent document-level state" in summary


def test_render_tool_exposes_voice_fields_and_emits_progress(tmp_path: Path) -> None:
    server = KaivraMCPServer(workspace_root=str(tmp_path))
    server._writer = lambda message: emitted.append(message)
    emitted: list[dict] = []

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
    )

    tools_response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
    )[0]
    render_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "render_animation"
    )
    check_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "check_animation"
    )
    plan_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "plan_animation"
    )
    assert "voice" in render_tool["inputSchema"]["properties"]
    assert "voice_provider" in render_tool["inputSchema"]["properties"]
    assert "voice_id" in render_tool["inputSchema"]["properties"]
    assert "voice_provider" in check_tool["inputSchema"]["properties"]
    assert "mirror on-screen keywords" in plan_tool["description"]
    assert "spoken_forms" in plan_tool["description"]

    captured: dict[str, object] = {}

    def fake_render_animation(**kwargs):
        captured.update(kwargs)
        progress = kwargs["progress"]
        progress(0.1, "Discovering voice provider: local.")
        progress(1.0, "Narrated render complete.")
        return {
            "status": "ok",
            "artifact_path": str(tmp_path / "out.mp4"),
            "duration_seconds": 1.2,
            "warnings": [],
            "source_file_path": str(tmp_path / "demo.json"),
        }

    server.workspace.render_animation = fake_render_animation
    response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "render_animation",
                "arguments": {
                    "file_path": "animations/demo.json",
                    "format": "mp4",
                    "voice": True,
                    "voice_provider": "local",
                    "voice_id": "amy",
                },
                "_meta": {"progressToken": "voice-render"},
            },
        }
    )[0]

    assert response["result"]["isError"] is False
    assert captured["voice"] is True
    assert captured["voice_provider"] == "local"
    assert captured["voice_id"] == "amy"
    progress_messages = [
        message["params"]["message"]
        for message in emitted
        if message.get("method") == "notifications/progress"
    ]
    assert "Discovering voice provider: local." in progress_messages
    assert "Narrated render complete." in progress_messages
