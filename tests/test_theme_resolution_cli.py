from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from kaivra.cli import main
from kaivra.themes.modern import MODERN


def test_cli_render_sample_and_audit_find_workspace_theme_from_input_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    doc_path = workspace / "animations" / "nested" / "demo.json"
    doc_path.parent.mkdir(parents=True)
    theme_path = workspace / "themes" / "workspace.json"
    theme_path.parent.mkdir(parents=True)
    theme_path.write_text(
        json.dumps({**MODERN.to_dict(), "name": "workspace"}),
        encoding="utf-8",
    )

    doc_path.write_text(
        json.dumps(
            {
                "version": "1.1",
                "meta": {"title": "Workspace Theme", "theme": "workspace"},
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

    runner = CliRunner()

    render_result = runner.invoke(
        main,
        ["render", str(doc_path), "-o", str(tmp_path / "frame.png")],
    )
    assert render_result.exit_code == 0, render_result.output

    sample_result = runner.invoke(
        main,
        [
            "sample",
            str(doc_path),
            "--count",
            "1",
            "--outdir",
            str(tmp_path / "frames"),
        ],
    )
    assert sample_result.exit_code == 0, sample_result.output

    audit_result = runner.invoke(main, ["audit", str(doc_path)])
    assert audit_result.exit_code == 0, audit_result.output
