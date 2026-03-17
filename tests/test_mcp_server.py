from __future__ import annotations

from pathlib import Path

from kaivra.mcp.server import KaivraMCPServer


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

    assert server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
    ) == []

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
    assert "render_animation" in tool_names

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
