"""Static MCP resources for guided Kaivra authoring."""

from __future__ import annotations

import json
from typing import Any

from kaivra.dsl.schema import DocumentSpec


RESOURCE_DEFINITIONS = [
    {
        "uri": "kaivra://authoring-profile",
        "name": "authoring_profile",
        "title": "Kaivra Authoring Profile",
        "description": "The recommended subset of the Kaivra DSL for local MCP-guided authoring.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "kaivra://pattern-catalog",
        "name": "pattern_catalog",
        "title": "Starter Pattern Catalog",
        "description": "When to use each supported starter blueprint.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "kaivra://theme-catalog",
        "name": "theme_catalog",
        "title": "Theme Catalog",
        "description": "Built-in theme guidance for the local MCP workflow.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "kaivra://example-catalog",
        "name": "example_catalog",
        "title": "Example Catalog",
        "description": "Curated examples and snippets that show the supported shape.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "kaivra://document-schema",
        "name": "document_schema",
        "title": "Document Schema",
        "description": "The full JSON Schema for the Kaivra document format.",
        "mimeType": "application/json",
    },
]


def list_resources() -> list[dict[str, Any]]:
    """Return the MCP resource descriptors."""
    return RESOURCE_DEFINITIONS


def read_resource(uri: str) -> dict[str, Any]:
    """Return the contents for a Kaivra MCP resource."""
    content_map = {
        "kaivra://authoring-profile": _authoring_profile(),
        "kaivra://pattern-catalog": _pattern_catalog(),
        "kaivra://theme-catalog": _theme_catalog(),
        "kaivra://example-catalog": _example_catalog(),
        "kaivra://document-schema": json.dumps(DocumentSpec.model_json_schema(), indent=2),
    }
    if uri not in content_map:
        raise ValueError(f"Unknown resource URI: {uri}")

    resource = next(item for item in RESOURCE_DEFINITIONS if item["uri"] == uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": resource["mimeType"],
                "text": content_map[uri],
            }
        ]
    }


def _authoring_profile() -> str:
    return """# Kaivra Authoring Profile

Use these defaults unless the user clearly needs something else:

- Prefer `process_explainer`, `algorithm_walkthrough`, `architecture_explainer`, or `before_after_comparison`.
- Prefer `modern` for polished UI-style explainers and `whiteboard` for sketch-style teaching moments.
- Use `one-column` or `two-column` templates instead of custom grids whenever possible.
- Stick to `text`, `box`, `group`, `token`, and occasional `connector` or `callout`.
- Keep scenes compact: one main idea, one focal object, one supporting text stack.
- Prefer `highlight`, `scale`, `appear`, and light `pulse` over complex motion.

Avoid these in the starter workflow:

- `absolute` layout
- complex camera choreography
- long unwrapped text in a single object
- niche animation combinations that are hard to debug

Suggested loop:

1. Read the pattern catalog if the user is vague.
2. Call `start_animation`.
3. If you edit the JSON, call `check_animation`.
4. Call `preview_animation`.
5. Call `render_animation` only when the preview shape is good.
"""


def _pattern_catalog() -> str:
    return """# Starter Pattern Catalog

## `process_explainer`

Use when the user wants a short step-by-step explanation, product flow, or concept walkthrough.

## `algorithm_walkthrough`

Use when the user wants a sequence with a clear current step and surrounding context, like compare/swap/progress beats.

## `architecture_explainer`

Use when the user wants a systems or pipeline explanation with a stronger sidebar/main-content structure.

## `before_after_comparison`

Use when the user is contrasting states, revisions, or outcomes. The MCP compares each beat to the previous one.

General advice:

- Keep beats short and concrete.
- Put one idea in each beat.
- If the user is vague, choose `process_explainer`.
"""


def _theme_catalog() -> str:
    return """# Theme Catalog

## `modern`

- Best default for polished demos and explainers
- Soft depth, UI-like cards, cleaner presentation

## `whiteboard`

- Best for teaching, sketches, and conceptual walkthroughs
- Hand-drawn feel with stronger borders and lighter background

Recommendation:

- Default to `modern`
- Switch to `whiteboard` only when the user explicitly wants a sketch or classroom feel
- Use `add_theme` when the user wants a reusable custom palette or card treatment
"""


def _example_catalog() -> str:
    return """# Example Catalog

Use these as shape references, not as something to copy verbatim:

## Bubble Sort

- Title + compact scene narration
- Repeated step scenes
- Step highlighting on tokens

```json
{
  "meta": { "theme": "whiteboard" },
  "scenes": [
    {
      "template": "one-column",
      "objects": [
        { "type": "text", "content": "Bubble Sort", "style": "heading" },
        { "type": "group", "layout": { "type": "flow" } }
      ]
    }
  ]
}
```

## Agentic Demo

- Persistent bottom carousel for progress
- `modern` theme
- Focused highlight on the active step

## Architecture Explainer

- `two-column` scenes
- Sidebar context + main explanation card
- Compact text stacks instead of long paragraphs
"""
