from kaivra.dsl.parser import parse_string
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.themes.registry import get_theme


def test_title_opener_hides_document_objects_and_upgrades_heading_style():
    doc = parse_string(
        """
        {
          "version": "1.1",
          "meta": {
            "theme": "modern",
            "show_narration": false
          },
          "objects": [
            {
              "type": "token",
              "id": "chapters",
              "content": "persistent chrome"
            }
          ],
          "scenes": [
            {
              "id": "intro",
              "template": "title-opener",
              "duration": "4s",
              "objects": [
                {
                  "type": "text",
                  "id": "title",
                  "content": "CQA Copilot",
                  "style": "heading"
                },
                {
                  "type": "text",
                  "id": "subtitle",
                  "content": "instant AI triage",
                  "style": "body"
                }
              ],
              "auto_visible": true
            }
          ]
        }
        """,
        format="json",
    )

    graph = build_scene_graph(doc, get_theme(doc.meta.theme))
    scene = graph.scenes[0]

    assert "chapters" not in scene.node_map
    assert scene.show_progress is False
    assert scene.node_map["title"].style == "display"
