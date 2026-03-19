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

- Prefer `visual_explainer` for narrated concept explainers. Use the other patterns when the user clearly wants a walkthrough, comparison, or sidebar-heavy architecture shape.
- Choose `pacing: educational` for narrated explainers, `balanced` for normal silent demos, and `quick-demo` only when the user explicitly wants a faster, denser result.
- Prefer `modern` for polished UI-style explainers and `whiteboard` for sketch-style teaching moments.
- Build scene-specific object graphs from each beat's content. Do not reuse the same abstract lane or slide template across every scene.
- Build scenes from `box`, `group`, `connector`, `token`, and short `text` headings. Treat body copy as support, not the main event.
- For technical topics, show actual values, computations, and before/after transformations. Use `box` and `token` for values, `connector` + `draw` for flow, and staggered highlights for sequential emphasis.
- Use `one-column` or `two-column` templates instead of custom grids whenever possible.
- Use `draw` on connectors to reveal flow, dependency, and causality.
- Prefer `fade-in` for smooth reveals. `appear` is an instant visibility toggle and is best reserved for deliberate snap-ins.
- Write narration as conversational spoken English, not written prose. Use contractions, direct address, and casual transitions. Do not open every scene with `Title. Definition.`
- Let the explanation determine scene length. When voice retiming is active, the pipeline can stretch scene timing automatically to match the narration.
- Sparse animation is the common failure mode. Every element that becomes relevant during the scene should have a corresponding reveal or emphasis so the visual keeps pace with the explanation.
- Start most scene objects hidden and reveal them progressively with `fade-in`, `draw`, `highlight`, `scale`, or light `pulse`. Reserve `auto_visible: true` for persistent document-level context.
- Use `meta.show_subtitles` only when narration text should stay on screen. Subtitle visibility is separate from whether a scene has narration or voice.
- Silent quick demos can use shorter scenes and compact text stacks when that helps the point land faster.
- Reuse the same `id` and the same `content` across consecutive scenes when a value, node, or result carries forward. The engine will morph it into its new position automatically.
- Reuse stable IDs for nodes and connectors that persist across scenes so follow-up animations and audits stay reliable.
- When a concept repeats the same operation, show one concrete worked example with real values and then generalize. Do not narrate every repetition one by one.
- Revealing a group ID will also reveal descendants that do not have their own visibility animation. Give a child its own `fade-in` only when you want custom timing.
- Treat the starter blueprint as a scaffold. Hand-edit it to add scene-specific visual depth before the final render.
- Document-level `flow` groups inside `one-column` scenes have limited horizontal space. Keep persistent bars compact, with short labels and tight spacing.
- Prefer `highlight`, `scale`, `fade-in`, light `pulse`, and connector `draw` over busy multi-effect motion.

Avoid these in the starter workflow:

- `absolute` layout
- complex camera choreography
- one long text stack standing in for the full diagram
- walls of body text when narration is present
- raw DSL invention before you have checked the pattern and example resources
- niche animation combinations that are hard to debug

Suggested loop:

1. Use `quick_render` when the user wants the fastest first-run artifact.
2. Read the pattern catalog if the user is vague or if you need to choose between narrated explainer shapes.
3. Call `start_animation` with a `pattern` and `pacing` when you need a starter file you can steer more deliberately.
4. If you edit the JSON, call `check_animation`.
5. Call `preview_animation` before the final render when you need to inspect timing and layout.
6. Call `render_animation` only when the preview shape is good.
"""


def _pattern_catalog() -> str:
    return """# Starter Pattern Catalog

## `process_explainer`

Use when the user wants a short step-by-step explanation, product flow, or silent quick demo with a compact central lane.

## `visual_explainer`

Default choice for narrated concept explainers. Use when the animation should read like one evolving diagram instead of a slide deck.

## `algorithm_walkthrough`

Use when the user wants a sequence with a clear active step and surrounding context, like compare/swap/progress beats.

## `architecture_explainer`

Use when the user wants a systems or pipeline explanation with a stronger sidebar/main-content structure and visible connections between stages.

## `before_after_comparison`

Use when the user is contrasting states, revisions, or outcomes. The MCP compares each beat to the previous one.

General advice:

- Treat examples as shape references, not templates to copy literally.
- Keep beats short and concrete.
- Put one idea in each beat.
- Prefer connectors, tokens, and persistent IDs when flow, causality, or before/after relationships matter.
- Keep raw DSL invention discouraged unless the supported patterns clearly cannot express the scene.
- If the user is vague, choose `visual_explainer` for narrated concept explainers and `process_explainer` or `algorithm_walkthrough` for silent quick demos.
"""


def _theme_catalog() -> str:
    return """# Theme Catalog

## `material`

- Material UI inspired sample for future custom-theme prompts
- Clean light surfaces, blue accent, generous radius, subtle elevation

## `modern`

- Best default for polished demos and explainers
- Soft depth, UI-like cards, cleaner presentation

## `whiteboard`

- Best for teaching, sketches, and conceptual walkthroughs
- Hand-drawn feel with stronger borders and lighter background

Recommendation:

- Default to `modern`
- Reach for `material` when the user wants a product-UI feel or asks for a theme example to customize
- Switch to `whiteboard` only when the user explicitly wants a sketch or classroom feel
- Use `add_theme` when the user wants a reusable custom palette or card treatment
"""


def _example_catalog() -> str:
    return """# Example Catalog

Use these as shape references for scene structure and pacing, not as templates to copy verbatim. Borrow the composition, then rewrite the content, IDs, and relationships for the user's concept.

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

## Good Narrated Scene

- Persistent top context bar plus a scene-specific computation breakdown
- Real values, staged reveals, and connector draws
- Progression from one worked example to a generalized takeaway

```json
{
  "template": "one-column",
  "auto_visible": false,
  "objects": [
    {
      "type": "group",
      "id": "network_bar",
      "layout": { "type": "flow", "gap": "small" },
      "children": [
        { "type": "token", "id": "stage_in", "content": "Input" },
        { "type": "token", "id": "stage_hidden", "content": "Hidden" },
        { "type": "token", "id": "stage_out", "content": "Output" }
      ]
    },
    {
      "type": "group",
      "id": "worked_example",
      "layout": { "type": "flow", "gap": "medium" },
      "children": [
        { "type": "box", "id": "x1_value", "content": "x1 = 0.72" },
        { "type": "box", "id": "weight_step", "content": "0.5 x 0.72" },
        { "type": "box", "id": "relu_step", "content": "ReLU -> 0.36" }
      ]
    },
    { "type": "connector", "id": "x1_to_weight", "from": "x1_value", "to": "weight_step" },
    { "type": "connector", "id": "weight_to_relu", "from": "weight_step", "to": "relu_step" }
  ],
  "animations": [
    { "action": "fade-in", "target": "network_bar", "at": "0s", "duration": "0.6s" },
    { "action": "fade-in", "target": "x1_value", "at": "0.3s", "duration": "0.6s" },
    { "action": "draw", "target": "x1_to_weight", "at": "0.6s", "duration": "0.9s" },
    { "action": "fade-in", "target": "weight_step", "at": "0.7s", "duration": "0.6s" },
    { "action": "highlight", "target": "weight_step", "at": "1.1s", "duration": "1.4s", "color": "accent" },
    { "action": "draw", "target": "weight_to_relu", "at": "1.8s", "duration": "0.9s" },
    { "action": "fade-in", "target": "relu_step", "at": "1.9s", "duration": "0.6s" }
  ]
}
```

## Continuity Carry-Over

- Reuse the same object `id` and the same `content` in consecutive scenes
- The engine glides the object into its new position instead of hard-cutting it

```json
{
  "scenes": [
    {
      "id": "weighted_sum",
      "objects": [{ "type": "box", "id": "result_val", "content": "0.36" }]
    },
    {
      "id": "activation",
      "objects": [{ "type": "box", "id": "result_val", "content": "0.36" }]
    }
  ]
}
```

## Architecture Explainer

- `two-column` scenes
- Sidebar context + main explanation card
- Connectors and tokens to show the system flow
- Compact text stacks instead of long paragraphs
"""
