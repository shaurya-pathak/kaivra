from __future__ import annotations

import json

from kaivra.dsl.timing import resolve_timing_config


def test_resolve_timing_config_loads_nearest_repo_file(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    animations = workspace / "animations"
    animations.mkdir(parents=True)
    (workspace / "kaivra.config.json").write_text(
        json.dumps(
            {
                "timing": {
                    "gaps": {"short": "0.2s"},
                    "tail_padding": "1.5s",
                }
            }
        ),
        encoding="utf-8",
    )
    document_path = animations / "demo.json"
    document_path.write_text("{}", encoding="utf-8")

    config = resolve_timing_config(document_path)

    assert config.gap_tokens["short"] == "0.2s"
    assert config.tail_padding == "1.5s"
    assert config.duration_tokens["medium"] == "0.8s"
