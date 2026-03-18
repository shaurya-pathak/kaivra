from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from kaivra.mcp import workspace as workspace_module
from kaivra.mcp.workspace import KaivraWorkspace
from kaivra.themes.modern import MODERN


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

    started = workspace.start_animation(
        title="Queue Basics",
        pattern="process_explainer",
        beats=[
            {"title": "Enqueue", "detail": "Add a new item to the back of the queue."},
            {"title": "Dequeue", "detail": "Remove the oldest item from the front."},
            {"title": "Result", "detail": "The queue preserves first-in, first-out order."},
        ],
        theme=added_theme["theme_name"],
        audience="beginners",
        include_narration=False,
        slug="queue-basics",
    )

    source_path = Path(started["file_path"])
    assert source_path.exists()

    checked = workspace.check_animation(file_path=str(source_path))
    assert checked["valid"] is True
    assert checked["warnings"] == []
    assert isinstance(checked["recommended_edits"], list)
    assert started["defaults"]["pacing"] == "balanced"

    previewed = workspace.preview_animation(file_path=str(source_path))
    assert Path(previewed["html_path"]).exists()
    assert Path(previewed["preview_image_path"]).exists()

    rendered = workspace.render_animation(file_path=str(source_path), format="png")
    assert rendered["status"] == "ok"
    assert Path(rendered["artifact_path"]).exists()


def test_check_animation_warns_on_scene_pacing_and_narration_mismatch(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(workspace, {
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
    })

    assert checked["valid"] is True
    assert any("too_short pacing" in warning and "shorter" in warning for warning in checked["warnings"])
    assert any("too_long pacing" in warning and "longer" in warning for warning in checked["warnings"])
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
    checked = _check_animation(workspace, {
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
    })

    assert checked["valid"] is True
    assert any("redundant_copy redundant_copy" in warning for warning in checked["warnings"])
    _assert_structured_edits(checked["recommended_edits"])
    assert any(
        edit["scene_id"] == "redundant_copy"
        and edit["object_id"] == "body_copy"
        and edit["field"] == "content"
        for edit in checked["recommended_edits"]
    )


def test_check_animation_blocks_invalid_connectors_and_animation_targets(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)
    checked = _check_animation(workspace, {
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
                    {"id": "edge_1", "type": "connector", "from": "node_a", "to": "node_missing"},
                ],
                "animations": [
                    {"action": "appear", "target": "node_missing", "at": "0s"},
                    {"action": "move-to", "target": "node_a", "to_id": "shared_nod", "at": "1s"},
                ],
            },
        ],
    })

    assert checked["valid"] is False
    assert any("Connector `edge_1`" in issue for issue in checked["blocking_issues"])
    assert any("targets missing object `node_missing`" in issue for issue in checked["blocking_issues"])
    assert any("moves toward missing object `shared_nod`" in issue for issue in checked["blocking_issues"])
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


def test_workspace_quick_render_creates_artifact(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)

    result = workspace.quick_render(
        title="Stack Basics",
        pattern="process_explainer",
        beats=[
            "Push adds a value to the top.",
            "Pop removes the top value.",
        ],
    )

    assert result["status"] == "ok"
    assert Path(result["created_file_path"]).exists()
    assert Path(result["artifact_path"]).exists()
    assert result["format"] == "png"


def test_workspace_quick_render_passes_pacing_to_start_animation(tmp_path: Path) -> None:
    workspace = KaivraWorkspace(tmp_path)

    result = workspace.quick_render(
        title="Narrated Basics",
        pattern="visual_explainer",
        beats=["Show how the signal moves through the system."],
        include_narration=True,
        pacing="educational",
    )

    assert result["status"] == "ok"
    created = Path(result["created_file_path"])
    assert created.exists()
    parsed = json.loads(created.read_text(encoding="utf-8"))
    assert parsed["meta"]["pacing"] == "educational"


def test_workspace_render_and_preview_find_nearest_workspace_theme_for_nested_docs(tmp_path: Path) -> None:
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
                "version": "1.1",
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


def test_start_animation_resolves_theme_from_nearest_ancestor_workspace(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_root = project_root / "apps" / "demo"
    nested_root.mkdir(parents=True)
    workspace_theme = project_root / "themes" / "ancestor.json"
    workspace_theme.parent.mkdir(parents=True)
    workspace_theme.write_text(
        json.dumps({**MODERN.to_dict(), "name": "ancestor"}),
        encoding="utf-8",
    )

    workspace = KaivraWorkspace(nested_root)
    started = workspace.start_animation(
        title="Ancestor Theme",
        pattern="process_explainer",
        beats=["Show the inherited workspace theme."],
        theme="ancestor",
        audience=None,
        include_narration=False,
    )

    assert Path(started["file_path"]).exists()


def test_preflight_reports_missing_cairo_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = KaivraWorkspace(tmp_path)
    real_import_module = workspace_module.importlib.import_module

    def fake_import_module(name: str):
        if name == "cairo":
            raise ImportError("No module named cairo")
        return real_import_module(name)

    monkeypatch.setattr(workspace_module.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("preview", needs_cairo=True)

    assert "preview" in str(excinfo.value)
    assert "brew install cairo pkg-config" in str(excinfo.value)


def test_preflight_reports_missing_ffmpeg_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = KaivraWorkspace(tmp_path)

    def fake_command_available(command: str) -> tuple[bool, str]:
        if command == "ffmpeg":
            return False, "ffmpeg was not found on PATH."
        return True, f"{command} is available."

    monkeypatch.setattr(workspace_module, "_command_available", fake_command_available)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("render", needs_cairo=False, needs_ffmpeg=True)

    assert "ffmpeg was not found on PATH" in str(excinfo.value)
    assert "brew install ffmpeg" in str(excinfo.value)


def test_preflight_reports_missing_ffprobe_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = KaivraWorkspace(tmp_path)

    def fake_command_available(command: str) -> tuple[bool, str]:
        if command == "ffprobe":
            return False, "ffprobe was not found on PATH."
        return True, f"{command} is available."

    monkeypatch.setattr(workspace_module, "_command_available", fake_command_available)

    with pytest.raises(RuntimeError) as excinfo:
        workspace.preflight_command("quick-render", needs_cairo=False, needs_ffprobe=True)

    assert "ffprobe was not found on PATH" in str(excinfo.value)
    assert "brew install ffmpeg" in str(excinfo.value)


def test_install_mcp_config_updates_claude_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
