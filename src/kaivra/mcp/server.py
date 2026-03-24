"""Minimal stdio MCP server for the guided Kaivra workflow."""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kaivra.mcp.resources import list_resources, read_resource
from kaivra.mcp.workspace import KaivraWorkspace
from kaivra.version import CURRENT_DSL_VERSION

SERVER_NAME = "kaivra-local-mcp"
SERVER_VERSION = "0.1.0"
SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)

JSONRPC_VERSION = "2.0"


@dataclass(frozen=True)
class ToolDefinition:
    """Static tool metadata exposed through MCP."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    handler: Callable[[dict[str, Any], "ToolContext"], dict[str, Any]]


@dataclass
class ToolContext:
    """Execution context passed to each tool handler."""

    workspace: KaivraWorkspace
    emit_progress: Callable[[float, str], None]


class KaivraMCPServer:
    """Guided local MCP server for Kaivra authoring and rendering."""

    def __init__(self, *, workspace_root: str | None = None) -> None:
        self.workspace = KaivraWorkspace(workspace_root)
        self.initialized = False
        self.protocol_version = SUPPORTED_PROTOCOL_VERSIONS[0]
        self._writer: Callable[[dict[str, Any]], None] | None = None
        self.tools = {tool.name: tool for tool in _build_tools()}

    def serve(self) -> None:
        """Serve newline-delimited JSON-RPC messages over stdio."""
        self._writer = self._write_message
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._write_message(_error_response(None, -32700, f"Invalid JSON: {exc.msg}"))
                continue

            responses = self.handle_message(message)
            for response in responses:
                self._write_message(response)

    def handle_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle a single parsed JSON-RPC message."""
        if not isinstance(message, dict):
            return [_error_response(None, -32600, "Messages must be JSON objects.")]

        method = message.get("method")
        if not isinstance(method, str):
            return [_error_response(message.get("id"), -32600, "Missing method name.")]

        request_id = message.get("id")
        params = message.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return [_error_response(request_id, -32602, "params must be an object.")]

        try:
            result = self._dispatch(method, params)
        except MCPError as exc:
            if request_id is None:
                return []
            return [_error_response(request_id, exc.code, exc.message)]
        except Exception as exc:  # pragma: no cover - defensive fallback
            traceback.print_exc(file=sys.stderr)
            if request_id is None:
                return []
            return [_error_response(request_id, -32603, f"Internal error: {exc}")]

        if request_id is None:
            return []
        return [_success_response(request_id, result)]

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return self._initialize(params)
        if method == "notifications/initialized":
            self.initialized = True
            return {}
        if method == "ping":
            return {}

        if not self.initialized:
            raise MCPError(-32002, "Server not initialized.")

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "title": tool.title,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                        "annotations": tool.annotations,
                    }
                    for tool in self.tools.values()
                ]
            }

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str):
                raise MCPError(-32602, "tools/call requires a string tool name.")
            if not isinstance(arguments, dict):
                raise MCPError(-32602, "tools/call requires arguments to be an object.")
            meta = params.get("_meta")
            if meta is not None and not isinstance(meta, dict):
                raise MCPError(-32602, "tools/call _meta must be an object when provided.")
            return self._call_tool(name, arguments, meta if isinstance(meta, dict) else None)

        if method == "resources/list":
            return {"resources": list_resources()}

        if method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str):
                raise MCPError(-32602, "resources/read requires a string uri.")
            return read_resource(uri)

        raise MCPError(-32601, f"Unknown method: {method}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
            self.protocol_version = requested
        else:
            self.protocol_version = SUPPORTED_PROTOCOL_VERSIONS[0]

        return {
            "protocolVersion": self.protocol_version,
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
            },
            "instructions": (
                f'Kaivra DSL v{CURRENT_DSL_VERSION}. Always set "version": "{CURRENT_DSL_VERSION}". '
                "Workflow: plan_animation → write JSON directly → check_animation → preview_animation → render_animation. "
                "Always start with plan_animation to capture voice mode, detail level, audience, theme, and structure. "
                "After planning, write the animation JSON directly — do NOT use a scaffold. "
                "Read examples/reference/api_how_it_works.json or examples/reference/forward_propagation.json for the quality bar. "
                "Wrap objects in group containers with flow (horizontal) or stack (vertical) layouts — flat lists cause overlaps. "
                "Set scene-level layout.type to 'stack'. "
                "Keep connected nodes adjacent within groups so connectors don't cross unrelated nodes. "
                "Available layout types: center, grid, flow, stack, split, absolute, carousel. "
                "Use fade-in for reveals, draw for connectors. "
                "Reuse the same object id and content across consecutive scenes for smooth continuity morphs. "
                "Add a carousel chapter tracker as a persistent document-level object and highlight the active step each scene. "
                "Set template: one-column on scenes. "
                "Template vs layout: 'template' is a high-level scene preset ('one-column' or 'two-column') that sets default layout and regions. "
                "'layout' on a scene or group is the algorithmic arrangement (center, grid, flow, stack, etc.). "
                "Template sets the layout automatically — do NOT set both template and layout on the same scene; use template for simple column layouts, layout for fine-grained control. "
                "Connector overlap: connectors route as straight lines between anchors. To avoid crossings, "
                "order objects in the group so that connected nodes are adjacent — the engine does not auto-route around obstacles. "
                "If a connector must span non-adjacent nodes, split into a separate group or use an intermediate waypoint node. "
                "Write narration as conversational spoken English."
            ),
        }

    def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            raise MCPError(-32602, f"Unknown tool: {name}")

        progress_token = meta.get("progressToken") if meta else None

        def emit_progress(progress: float, message: str) -> None:
            if progress_token is None or self._writer is None:
                return
            self._writer(
                {
                    "jsonrpc": JSONRPC_VERSION,
                    "method": "notifications/progress",
                    "params": {
                        "progressToken": progress_token,
                        "progress": round(max(0.0, min(progress, 1.0)), 3),
                        "total": 1.0,
                        "message": message,
                    },
                }
            )

        context = ToolContext(workspace=self.workspace, emit_progress=emit_progress)
        try:
            result = tool.handler(arguments, context)
            return _tool_success(tool.name, result)
        except Exception as exc:
            return _tool_error(tool.name, str(exc))

    @staticmethod
    def _write_message(message: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _build_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="doctor_kaivra",
            title="Doctor Kaivra",
            description="Check local Kaivra dependencies, workspace access, the resolved kaivra-mcp command path, and local voice model defaults.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            annotations={
                "title": "Doctor Kaivra",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_doctor_tool,
        ),
        ToolDefinition(
            name="add_theme",
            title="Add Theme",
            description="Create or update a custom Kaivra theme file inside the local workspace. Starts from a base theme and applies overrides.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the custom theme (used as filename and reference).",
                    },
                    "base_theme": {
                        "type": "string",
                        "enum": ["material", "whiteboard", "modern"],
                        "description": "Built-in theme to start from. Defaults to 'modern'.",
                    },
                    "overrides": {
                        "type": "object",
                        "description": (
                            "Theme fields to override. Valid keys include: "
                            "background_color, primary, accent, success, warning, error, muted, "
                            "text_color, text_light, font_family, font_size_heading, font_size_body, "
                            "box_fill, box_border, box_border_width, box_corner_radius, box_padding, "
                            "token_fill, token_border, connector_color, connector_width, "
                            "gap_small, gap_medium, gap_large, margin, "
                            "shadow (bool), sketch_effect (bool)."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            annotations={
                "title": "Add Theme",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_add_theme_tool,
        ),
        ToolDefinition(
            name="plan_animation",
            title="Plan Animation",
            description="Interactive planning step — returns a structured questionnaire for the user to answer before creating an animation. Ask about voice mode (ElevenLabs, local, captions only), detail level, audience, visual theme, and structure. Present the questions conversationally, then use the answers to call start_animation.",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                },
                "additionalProperties": False,
            },
            annotations={
                "title": "Plan Animation",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_plan_tool,
        ),
        ToolDefinition(
            name="check_animation",
            title="Check Animation",
            description="Validate and audit a Kaivra JSON file or raw JSON string, with optional normalization write-back and voice-aware narration pacing notes.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "dsl_json": {"type": "string"},
                    "write_back": {"type": "boolean"},
                    "voice": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            annotations={
                "title": "Check Animation",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_check_tool,
        ),
        ToolDefinition(
            name="preview_animation",
            title="Preview Animation",
            description="Write a self-contained HTML preview and first-frame PNG into artifacts/previews.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "output_name": {"type": "string"},
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
            annotations={
                "title": "Preview Animation",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_preview_tool,
        ),
        ToolDefinition(
            name="render_animation",
            title="Render Animation",
            description="Render a Kaivra animation to PNG, MP4, or WebM inside artifacts/renders.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "format": {
                        "type": "string",
                        "enum": ["png", "mp4", "webm"],
                    },
                    "output_name": {"type": "string"},
                    "audio_path": {"type": "string"},
                    "audio_timings_path": {"type": "string"},
                    "voice": {"type": "boolean"},
                    "voice_provider": {
                        "type": "string",
                        "enum": ["elevenlabs", "local"],
                        "description": "Voice synthesis provider. 'elevenlabs' for high-quality AI voices (requires API key), 'local' for free offline Sherpa TTS.",
                    },
                    "voice_id": {"type": "string"},
                },
                "required": ["file_path", "format"],
                "additionalProperties": False,
            },
            annotations={
                "title": "Render Animation",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            handler=_render_tool,
        ),
    ]


def _doctor_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    del arguments
    return context.workspace.run_doctor()


def _plan_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    return context.workspace.plan_animation(
        topic=arguments.get("topic"),
    )


def _add_theme_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    context.emit_progress(0.2, "Building the custom theme.")
    result = context.workspace.add_theme(
        name=arguments["name"],
        base_theme=arguments.get("base_theme"),
        overrides=arguments.get("overrides"),
    )
    context.emit_progress(1.0, "Theme file written to the workspace.")
    return result


def _check_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    context.emit_progress(0.2, "Validating the Kaivra document.")
    result = context.workspace.check_animation(
        file_path=arguments.get("file_path"),
        dsl_json=arguments.get("dsl_json"),
        write_back=bool(arguments.get("write_back", False)),
        voice=bool(arguments.get("voice", False)),
    )
    context.emit_progress(1.0, "Validation and audit complete.")
    return result


def _preview_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    context.emit_progress(0.2, "Building preview artifacts.")
    result = context.workspace.preview_animation(
        file_path=arguments["file_path"],
        output_name=arguments.get("output_name"),
    )
    context.emit_progress(1.0, "Preview artifacts are ready.")
    return result


def _render_tool(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    return context.workspace.render_animation(
        file_path=arguments["file_path"],
        format=arguments["format"],
        output_name=arguments.get("output_name"),
        audio_path=arguments.get("audio_path"),
        audio_timings_path=arguments.get("audio_timings_path"),
        voice=bool(arguments.get("voice", False)),
        voice_provider=arguments.get("voice_provider"),
        voice_id=arguments.get("voice_id"),
        progress=context.emit_progress,
    )


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result,
    }


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _tool_success(name: str, result: dict[str, Any]) -> dict[str, Any]:
    summary = _summarize_tool_result(name, result)
    return {
        "content": [
            {
                "type": "text",
                "text": summary,
            }
        ],
        "structuredContent": result,
        "isError": False,
    }


def _tool_error(name: str, message: str) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": f"{name} failed: {message}",
            }
        ],
        "structuredContent": {
            "status": "error",
            "error": message,
        },
        "isError": True,
    }


def _summarize_tool_result(name: str, result: dict[str, Any]) -> str:
    if name == "doctor_kaivra":
        return (
            "Kaivra doctor passed."
            if result.get("ok")
            else "Kaivra doctor found local setup issues."
        )
    if name == "plan_animation":
        return (
            "Animation plan ready. Present the questions to the user, "
            "collect their preferences, then write the animation JSON directly. "
            "Read examples/reference/api_how_it_works.json for the quality bar."
        )
    if name == "add_theme":
        return f"Theme saved at {result['file_path']}."
    if name == "check_animation":
        warnings = result.get("warnings") or []
        blocking = result.get("blocking_issues") or []
        recommended = result.get("recommended_edits") or []
        warning_count = len(warnings)
        blocking_count = len(blocking)

        parts: list[str] = []

        # Header
        if result.get("valid") and not warning_count:
            parts.append("Animation validated cleanly.")
        elif result.get("valid"):
            parts.append(f"Animation validated with {warning_count} warning(s).")
        else:
            parts.append(f"Animation check found {blocking_count} blocking issue(s).")

        # Blocking issues
        if blocking:
            parts.append("\n**Blocking issues:**")
            for issue in blocking:
                parts.append(f"- {issue}")

        # Warnings
        if warnings:
            parts.append("\n**Warnings:**")
            for w in warnings:
                parts.append(f"- {w}")

        # Recommended edits
        if recommended:
            parts.append("\n**Recommended edits:**")
            for edit in recommended:
                parts.append(f"- {edit}")

        return "\n".join(parts)
    if name == "preview_animation":
        return f"Preview HTML written to {result['html_path']}."
    if name == "render_animation":
        return f"Render written to {result['artifact_path']}."
    return f"{name} completed."


class MCPError(RuntimeError):
    """Protocol-level JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
