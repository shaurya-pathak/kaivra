from __future__ import annotations

import pytest

from kaivra.mcp.blueprints import SUPPORTED_PATTERNS, build_starter_document
from kaivra.qa.audit import audit_scene_graph
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.themes.registry import get_theme


@pytest.mark.parametrize("pattern", SUPPORTED_PATTERNS)
def test_starter_blueprints_build_without_audit_errors(pattern: str) -> None:
    doc = build_starter_document(
        title="MCP Starter",
        pattern=pattern,
        beats=[
            {"title": "Input", "detail": "Set the context for the animation."},
            {"title": "Change", "detail": "Show the key transition or behavior."},
            {"title": "Result", "detail": "Land on the final takeaway."},
        ],
        theme="modern",
        audience="new learners",
        include_narration=False,
    )

    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)
    findings = audit_scene_graph(graph, samples_per_scene=4)

    assert all(finding.severity != "error" for finding in findings)
    assert doc.scenes
