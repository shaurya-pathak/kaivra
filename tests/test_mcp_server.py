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
    assert "SCAFFOLD" in instructions
    assert "rewrite each scene" in instructions
    assert "Use draw on connectors" in instructions
    assert "Reuse the same object id and content" in instructions
    assert "conversational spoken English" in instructions
    assert "same order you want highlights and reveals to land" in instructions

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
    assert "start_animation" in tool_names
    assert "quick_render" in tool_names
    assert "render_animation" in tool_names
    start_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "start_animation"
    )
    assert "visual_explainer" in start_tool["inputSchema"]["properties"]["pattern"]["enum"]
    assert "process_explainer" not in start_tool["inputSchema"]["properties"]["pattern"]["enum"]
    assert start_tool["inputSchema"]["properties"]["pacing"]["enum"] == [
        "quick-demo",
        "balanced",
        "educational",
    ]

    start_response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "start_animation",
                "arguments": {
                    "title": "Stack Operations",
                    "pattern": "algorithm_walkthrough",
                    "beats": [
                        "Push: Add a value to the top of the stack.",
                        "Pop: Remove the top value.",
                    ],
                },
            },
        }
    )[0]

    result = start_response["result"]["structuredContent"]
    assert start_response["result"]["isError"] is False
    assert Path(result["file_path"]).exists()

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


def test_resource_guidance_promotes_visual_explainers_and_examples_as_shape_references() -> None:
    authoring = read_resource("kaivra://authoring-profile")["contents"][0]["text"]
    pattern_catalog = read_resource("kaivra://pattern-catalog")["contents"][0]["text"]
    examples = read_resource("kaivra://example-catalog")["contents"][0]["text"]

    assert "SCAFFOLD" in authoring
    assert "rewrite each scene" in authoring
    assert "Choose `pacing: educational` for narrated explainers" in authoring
    assert "Do not describe MCP setup" in authoring
    assert "same `id` and `content`" in authoring
    assert "Sparse animation is the common failure mode" in authoring
    assert "Use `draw` on connectors" in authoring
    assert "Walls of body text when narration is present" in authoring
    assert "What a bad scene looks like" in authoring
    assert "What a good scene looks like" in authoring
    assert "Default choice for narrated concept explainers" in pattern_catalog
    assert "algorithm_walkthrough" in pattern_catalog
    assert "persistent IDs" in pattern_catalog
    assert "Rewrite scene objects before shipping" in pattern_catalog
    assert "BAD: Scaffold scene" in examples
    assert "GOOD: Rewritten scene" in examples
    assert "Continuity Carry-Over" in examples


def test_check_animation_summary_mentions_warning_count() -> None:
    assert (
        _summarize_tool_result(
            "check_animation",
            {"valid": True, "warnings": ["warning one", "warning two"]},
        )
        == "Animation validated with 2 warnings to review."
    )


def test_start_animation_tool_description_steers_narrated_flows_toward_visual_explainer(
    tmp_path: Path,
) -> None:
    server = KaivraMCPServer(workspace_root=str(tmp_path))
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

    start_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "start_animation"
    )

    assert "visual_explainer" in start_tool["description"]
    assert "algorithm_walkthrough" in start_tool["description"]


def test_quick_render_tool_description_steers_narrated_flows_toward_visual_explainer(
    tmp_path: Path,
) -> None:
    server = KaivraMCPServer(workspace_root=str(tmp_path))
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

    quick_render_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "quick_render"
    )

    assert "visual_explainer" in quick_render_tool["description"]
    assert "algorithm_walkthrough" in quick_render_tool["description"]


def test_quick_render_tool_creates_artifact(tmp_path: Path) -> None:
    server = KaivraMCPServer(workspace_root=str(tmp_path))
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

    response = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "quick_render",
                "arguments": {
                    "title": "Queue Basics",
                    "pattern": "algorithm_walkthrough",
                    "beats": [
                        "Enqueue adds to the back.",
                        "Dequeue removes from the front.",
                    ],
                },
            },
        }
    )[0]

    result = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert result["status"] == "ok"
    assert Path(result["created_file_path"]).exists()
    assert Path(result["artifact_path"]).exists()


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
    quick_render_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "quick_render"
    )
    render_tool = next(
        tool for tool in tools_response["result"]["tools"] if tool["name"] == "render_animation"
    )
    assert "visual_explainer" in quick_render_tool["inputSchema"]["properties"]["pattern"]["enum"]
    assert (
        "process_explainer" not in quick_render_tool["inputSchema"]["properties"]["pattern"]["enum"]
    )
    assert quick_render_tool["inputSchema"]["properties"]["pacing"]["enum"] == [
        "quick-demo",
        "balanced",
        "educational",
    ]
    assert "voice" in render_tool["inputSchema"]["properties"]
    assert "voice_provider" in render_tool["inputSchema"]["properties"]
    assert "voice_id" in render_tool["inputSchema"]["properties"]

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
