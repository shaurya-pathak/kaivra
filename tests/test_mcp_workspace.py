from __future__ import annotations

from pathlib import Path

from kaivra.mcp.workspace import KaivraWorkspace


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

    previewed = workspace.preview_animation(file_path=str(source_path))
    assert Path(previewed["html_path"]).exists()
    assert Path(previewed["preview_image_path"]).exists()

    rendered = workspace.render_animation(file_path=str(source_path), format="png")
    assert rendered["status"] == "ok"
    assert Path(rendered["artifact_path"]).exists()
