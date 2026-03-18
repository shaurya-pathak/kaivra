from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import kaivra.cli as cli_module
from kaivra.cli import main


def test_doctor_command_prints_report() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "ok" in parsed
    assert "checks" in parsed


def test_download_model_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["download-model", "--help"])
    assert result.exit_code == 0
    assert "--model-name" in result.output


def test_mcp_install_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["mcp-install", "--help"])
    assert result.exit_code == 0
    assert "--client" in result.output


def test_mcp_install_auto_writes_cursor_config(tmp_path: Path, monkeypatch) -> None:
    claude_path = tmp_path / ".claude.json"
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text(
        json.dumps(
            {"mcpServers": {"existing": {"type": "stdio", "command": "keep-me", "args": []}}}
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("kaivra.mcp.workspace._DEFAULT_CLAUDE_CONFIG_PATH", claude_path)
    monkeypatch.setattr("kaivra.mcp.workspace._DEFAULT_CURSOR_CONFIG_PATH", cursor_path)
    monkeypatch.setattr(
        "kaivra.mcp.workspace._resolve_mcp_server_command", lambda: "/tmp/kaivra-mcp"
    )

    runner = CliRunner()
    result = runner.invoke(main, ["mcp-install", "--client", "auto"])

    assert result.exit_code == 0, result.output
    assert "Updated cursor MCP config" in result.output
    config = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["existing"]["command"] == "keep-me"
    assert config["mcpServers"]["kaivra"]["command"] == "/tmp/kaivra-mcp"


def test_mcp_install_prints_doctor_hint_only_once(tmp_path: Path, monkeypatch) -> None:
    hint_file = tmp_path / ".kaivra" / ".doctor_hint_seen"

    monkeypatch.setenv("KAIVRA_DOCTOR_HINT_FILE", str(hint_file))
    monkeypatch.setattr(
        "kaivra.mcp.workspace.KaivraWorkspace.preflight_command", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "kaivra.mcp.workspace.KaivraWorkspace.install_mcp_config",
        lambda *args, **kwargs: {
            "status": "ok",
            "client": "claude-code",
            "config_path": str(tmp_path / ".claude.json"),
            "command": "/tmp/kaivra-mcp",
        },
    )

    runner = CliRunner()
    first = runner.invoke(main, ["mcp-install", "--client", "claude-code"])
    second = runner.invoke(main, ["mcp-install", "--client", "claude-code"])

    assert first.exit_code == 0, first.output
    assert "Tip: run `kaivra doctor`" in first.output
    assert second.exit_code == 0, second.output
    assert "Tip: run `kaivra doctor`" not in second.output


def test_quick_render_uses_png_default(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "demo.json"
    input_file.write_text(
        Path("examples/algorithms/bubble_sort.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_run_preflight_for_render", lambda *args, **kwargs: None)

    captured: dict[str, str] = {}

    def fake_render_to_output(**kwargs) -> None:
        captured["output"] = kwargs["output"]
        output_path = Path(kwargs["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"demo")

    monkeypatch.setattr(cli_module, "_render_to_output", fake_render_to_output)

    runner = CliRunner()
    result = runner.invoke(main, ["quick-render", str(input_file)])

    assert result.exit_code == 0
    assert captured["output"].endswith("artifacts/quick-renders/demo.png")


def test_quick_render_uses_mp4_when_voice_requested(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "demo.json"
    input_file.write_text(
        Path("examples/algorithms/bubble_sort.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_run_preflight_for_render", lambda *args, **kwargs: None)

    captured: dict[str, str] = {}

    def fake_render_to_output(**kwargs) -> None:
        captured["output"] = kwargs["output"]
        output_path = Path(kwargs["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"demo")

    monkeypatch.setattr(cli_module, "_render_to_output", fake_render_to_output)

    runner = CliRunner()
    result = runner.invoke(main, ["quick-render", str(input_file), "--voice"])

    assert result.exit_code == 0
    assert captured["output"].endswith("artifacts/quick-renders/demo.mp4")


def test_quick_render_accepts_repo_relative_input_path(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setattr(cli_module, "_run_preflight_for_render", lambda *args, **kwargs: None)

    captured: dict[str, str] = {}

    def fake_render_to_output(**kwargs) -> None:
        captured["input_file"] = kwargs["input_file"]
        captured["output"] = kwargs["output"]
        output_path = Path(kwargs["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"demo")

    monkeypatch.setattr(cli_module, "_render_to_output", fake_render_to_output)

    result = runner.invoke(main, ["quick-render", "examples/algorithms/bubble_sort.json"])

    assert result.exit_code == 0
    assert Path(captured["input_file"]).is_absolute()
    assert captured["output"].endswith("artifacts/quick-renders/bubble_sort.png")
