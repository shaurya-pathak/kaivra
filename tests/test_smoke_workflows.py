from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from kaivra.cli import main
from kaivra.mcp.workspace import KaivraWorkspace


def test_workspace_doctor_runs_real_smoke_render(tmp_path: Path) -> None:
    report = KaivraWorkspace(tmp_path).run_doctor(
        required_checks={"python_package", "pycairo", "workspace_write", "smoke_render"},
        include_smoke=True,
    )

    checks = {check["name"]: check for check in report["checks"]}

    assert report["ok"] is True
    assert checks["smoke_render"]["ok"] is True


def test_quick_render_smoke_renders_real_png(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "quick-render-smoke.png"

    monkeypatch.chdir(repo_root)
    result = runner.invoke(
        main,
        [
            "quick-render",
            "examples/algorithms/bubble_sort.json",
            "--format",
            "png",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    doctor_result = runner.invoke(main, ["doctor", "--json"])
    assert doctor_result.exit_code == 0, doctor_result.output
    parsed = json.loads(doctor_result.output)
    assert "checks" in parsed
