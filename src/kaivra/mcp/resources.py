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

## Defaults

- `visual_explainer` for narrated explainers, `algorithm_walkthrough` for silent demos.
- `pacing: educational` for narrated, `balanced` for silent.
- `modern` theme by default, `whiteboard` for sketch-style teaching.

## Scene Construction

- Set `template: "one-column"` (or `"two-column"`) on every scene.
- Build scenes from `box`, `group`, `connector`, `token`, and short `text` headings.
- Use `draw` on connectors to animate flow and causality.
- Each scene should have enough objects to fully illustrate the concept.

## Layout Essentials

**This is critical.** Flat object lists with the default `center` layout stack everything on the same point, producing massive overlaps.

- Set scene-level `layout.type` to `"stack"` so top-level objects flow vertically.
- Wrap related objects in `group` containers with `layout.type: "flow"` (horizontal rows) or `"stack"` (vertical columns).
- Available layout types: `center`, `grid`, `flow`, `stack`, `split`, `absolute`, `carousel`.
- Use `gap: "small" | "medium" | "large"` on groups to control spacing.
- Use `direction: "horizontal" | "vertical"` on flow/stack layouts.

**Connector overlap:** The engine does not auto-route connectors. If `check_animation` flags crossover warnings, reorder objects within their group so connected nodes are adjacent, or split objects into smaller groups to keep connector paths clear.

## Document-Level Objects

- Persistent objects in the top-level `objects` array appear in every scene (when `include_persistent_objects: true`).
- For multi-scene explainers, add a carousel chapter tracker: a group of tokens with `layout.type: "carousel"` and `position: "bottom"`. In each scene, `highlight` + `scale` the active step token so the viewer knows where they are.

## Animation and Reveals

- Use `fade-in` for reveals — it animates opacity smoothly. `appear` is an instant pop; only use it when you want a hard cut.
- Start scene objects hidden (`auto_visible: false`) and reveal them with staggered `fade-in` timings that track the narration.
- Use `draw` on connectors to animate them in. Connectors without `draw` appear instantly.
- `fade-in` on a group ID reveals the group and all its children. You don't need separate animations for children unless you want them staggered.

## Narration

- Write narration as conversational spoken English with contractions and direct address. Not "Title. Definition."
- Mention labels and values in the order you want reveals to land.
- Let the explanation determine scene length.

## Continuity

- Reuse the same `id` and `content` across consecutive scenes when a value carries forward. The engine morphs it into its new position automatically.
- When a data structure spans scenes (array, graph, pipeline), keep the same object IDs. Recreating with new IDs each scene kills the smooth morph.
- When a concept repeats the same operation, show one concrete worked example, then generalize.

## Workflow

1. `start_animation` → scaffold.
2. Rewrite each scene's objects and animations to be topic-specific.
3. `check_animation` → `preview_animation` → `render_animation`.
"""


def _pattern_catalog() -> str:
    return """# Starter Pattern Catalog

## `visual_explainer`

Default for narrated concept explainers. Rewrite the scaffold scenes with topic-specific diagrams.

## `algorithm_walkthrough`

Sequence with a clear active step and surrounding context (compare/swap/progress beats).

## `architecture_explainer`

Systems or pipeline explanation with sidebar/main-content structure and visible connections between stages.

## `before_after_comparison`

Contrasting states, revisions, or outcomes.

All patterns produce starter scaffolds. Rewrite scene objects before shipping. Keep beats short — one idea per beat.
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

Use these as shape references, not templates. Borrow the composition, then rewrite content, IDs, and relationships for the user's concept.

## Full Reference Examples

Read these complete, polished animations before rewriting scaffolds. They demonstrate every v1.1 pattern working together:

- **`examples/reference/api_how_it_works.json`** — 4-scene narrated explainer (How an API Works). Shows carousel chapter tracker, horizontal flow layouts, connector draws, continuity morphs across scenes, and conversational narration. Material theme, educational pacing.
- **`examples/reference/forward_propagation.json`** — 6-scene narrated explainer (Forward Propagation in a Neural Network). Shows worked-example arithmetic, stacked layouts, highlight colors (accent/success/warning), and deep continuity where computed values carry across scenes. Material theme, educational pacing.

Read one of these files before rewriting your scaffold — they are the quality bar.

## BAD: Scaffold scene (do NOT ship this)

Every scene looks the same — generic "Signal In → Active Idea → Result" lane with only labels changed. This is the raw starter output and must be rewritten.

```json
{
  "template": "one-column",
  "objects": [
    { "type": "text", "id": "visual_heading", "content": "Plants add water vapor", "style": "heading" },
    { "type": "group", "id": "visual_panel", "children": [
      { "type": "token", "id": "visual_stage_badge", "content": "Beat 2" },
      { "type": "group", "id": "visual_lane", "layout": { "type": "flow" }, "children": [
        { "type": "token", "id": "visual_source_token", "content": "Evaporation" },
        { "type": "box", "id": "visual_focus_card", "content": "Transpiration" },
        { "type": "token", "id": "visual_result_token", "content": "Condensation" }
      ]}
    ]},
    { "type": "connector", "from": "visual_source_token", "to": "visual_focus_card" },
    { "type": "connector", "from": "visual_focus_card", "to": "visual_result_token" }
  ]
}
```

Problem: generic lane, no real content, same structure as every other scene.

## GOOD: Rewritten scene with topic-specific content

Each scene has its own unique diagram built from the actual content being explained.

```json
{
  "template": "one-column",
  "auto_visible": false,
  "narration": "Now let's slow down and look at why this weighted sum exists. Each weight tells the neuron how strongly to listen to one input.",
  "objects": [
    { "type": "text", "id": "hidden_sum_title", "content": "1. Compute One Hidden Weighted Sum", "style": "heading" },
    {
      "type": "group", "id": "term_row",
      "layout": { "type": "flow", "gap": "large", "direction": "horizontal" },
      "children": [
        { "type": "box", "id": "term_1", "content": "0.70 × 0.50 = 0.35" },
        { "type": "box", "id": "term_2", "content": "−0.40 × −0.30 = 0.12" }
      ]
    },
    { "type": "box", "id": "partial_sum", "content": "0.35 + 0.12 = 0.47" },
    {
      "type": "group", "id": "weight_note_row",
      "layout": { "type": "flow", "gap": "medium" },
      "children": [
        { "type": "token", "id": "term_1_label", "content": "x1 contributes evidence to h1" },
        { "type": "token", "id": "term_2_label", "content": "x2 contributes evidence to h1" }
      ]
    },
    { "type": "connector", "id": "term_1_to_sum", "from": "term_1", "to": "partial_sum" },
    { "type": "connector", "id": "term_2_to_sum", "from": "term_2", "to": "partial_sum" }
  ],
  "animations": [
    { "action": "fade-in", "target": "hidden_sum_title", "at": "0s", "duration": "0.8s" },
    { "action": "fade-in", "target": "term_1", "at": "0.8s", "duration": "0.9s" },
    { "action": "fade-in", "target": "term_2", "at": "1.5s", "duration": "0.9s" },
    { "action": "draw", "target": "term_1_to_sum", "at": "2.5s", "duration": "1.0s" },
    { "action": "draw", "target": "term_2_to_sum", "at": "3.0s", "duration": "1.0s" },
    { "action": "fade-in", "target": "partial_sum", "at": "3.2s", "duration": "0.8s" },
    { "action": "highlight", "target": "partial_sum", "at": "4.0s", "duration": "2.0s", "color": "accent" },
    { "action": "fade-in", "target": "weight_note_row", "at": "5.5s", "duration": "0.8s" }
  ]
}
```

Notice: unique objects showing actual computations, connectors between real elements, staggered reveals matching narration, no generic lane template.

## GOOD: Non-technical scene (Water Cycle example)

Even non-math topics should have unique per-scene diagrams, not repeated lanes.

```json
{
  "template": "one-column",
  "auto_visible": false,
  "narration": "Higher up, the air is cooler, so the vapor loses heat and condenses into tiny droplets that gather into clouds.",
  "objects": [
    { "type": "text", "id": "condensation_title", "content": "3. Condensation", "style": "heading" },
    {
      "type": "group", "id": "altitude_stack",
      "layout": { "type": "stack", "gap": "large" },
      "children": [
        { "type": "box", "id": "warm_vapor", "content": "Warm vapor rises", "style": "muted" },
        { "type": "box", "id": "cooling_zone", "content": "Air cools at altitude", "style": "accent" },
        { "type": "box", "id": "droplets", "content": "Tiny water droplets form", "style": "primary" }
      ]
    },
    { "type": "token", "id": "temp_label", "content": "Temperature drops → vapor condenses" },
    { "type": "box", "id": "cloud_result", "content": "Clouds form" },
    { "type": "connector", "id": "vapor_to_cool", "from": "warm_vapor", "to": "cooling_zone" },
    { "type": "connector", "id": "cool_to_drops", "from": "cooling_zone", "to": "droplets" },
    { "type": "connector", "id": "drops_to_cloud", "from": "droplets", "to": "cloud_result" }
  ],
  "animations": [
    { "action": "fade-in", "target": "condensation_title", "at": "0s", "duration": "0.8s" },
    { "action": "fade-in", "target": "warm_vapor", "at": "0.5s", "duration": "0.8s" },
    { "action": "draw", "target": "vapor_to_cool", "at": "1.2s", "duration": "1.0s" },
    { "action": "fade-in", "target": "cooling_zone", "at": "1.5s", "duration": "0.8s" },
    { "action": "highlight", "target": "cooling_zone", "at": "2.5s", "duration": "1.5s", "color": "accent" },
    { "action": "draw", "target": "cool_to_drops", "at": "3.5s", "duration": "1.0s" },
    { "action": "fade-in", "target": "droplets", "at": "4.0s", "duration": "0.8s" },
    { "action": "fade-in", "target": "temp_label", "at": "5.0s", "duration": "0.8s" },
    { "action": "draw", "target": "drops_to_cloud", "at": "6.0s", "duration": "1.0s" },
    { "action": "fade-in", "target": "cloud_result", "at": "6.5s", "duration": "0.8s" },
    { "action": "highlight", "target": "cloud_result", "at": "7.5s", "duration": "2.0s", "color": "success" }
  ]
}
```

## Continuity Carry-Over

Reuse the same `id` and `content` in consecutive scenes — the engine glides the object to its new position.

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

## Complete Multi-Scene Explainer Structure

Shows document-level carousel, continuity carry-over, fade-in reveals, and connector draws composed together.

```json
{
  "version": "1.1",
  "meta": {
    "title": "Example Explainer",
    "resolution": [1920, 1080], "fps": 30, "theme": "modern",
    "pacing": "educational", "continuity": true, "continuity_duration": "1.2s"
  },
  "objects": [
    {
      "type": "group", "id": "chapters", "position": "bottom",
      "children": [
        { "type": "token", "id": "step_compute", "content": "1  Compute" },
        { "type": "token", "id": "step_activate", "content": "2  Activate" }
      ],
      "layout": { "type": "carousel", "gap": "medium", "direction": "horizontal",
                   "align": "center", "curve": 16.0, "active_scale": 1.16, "inactive_scale": 0.92 }
    }
  ],
  "scenes": [
    {
      "id": "compute", "duration": "18s", "template": "one-column", "auto_visible": false,
      "include_persistent_objects": true,
      "narration": "Each weight scales one input. We multiply, then add everything together.",
      "objects": [
        { "type": "text", "id": "compute_title", "content": "1. Weighted Sum", "style": "heading" },
        { "type": "box", "id": "term_a", "content": "0.70 × 0.50 = 0.35" },
        { "type": "box", "id": "result_val", "content": "sum = 0.47" },
        { "type": "connector", "id": "a_to_sum", "from": "term_a", "to": "result_val" }
      ],
      "animations": [
        { "action": "fade-in", "target": "compute_title", "at": "0s", "duration": "0.8s" },
        { "action": "fade-in", "target": "term_a", "at": "0.8s", "duration": "0.8s" },
        { "action": "draw", "target": "a_to_sum", "at": "2s", "duration": "1s" },
        { "action": "fade-in", "target": "result_val", "at": "2.5s", "duration": "0.8s" },
        { "action": "highlight", "target": "result_val", "at": "3.5s", "duration": "2s", "color": "success" },
        { "action": "highlight", "target": "step_compute", "at": "0s", "duration": "16s", "style": "glow", "color": "accent" },
        { "action": "scale", "target": "step_compute", "at": "0.1s", "duration": "0.8s", "scale_factor": 1.12 }
      ]
    },
    {
      "id": "activate", "duration": "18s", "template": "one-column", "auto_visible": false,
      "include_persistent_objects": true,
      "narration": "Now we feed that sum through ReLU. Positive values survive, negatives get clipped to zero.",
      "objects": [
        { "type": "text", "id": "activate_title", "content": "2. Apply ReLU", "style": "heading" },
        { "type": "box", "id": "result_val", "content": "sum = 0.47" },
        { "type": "box", "id": "relu_out", "content": "ReLU(0.47) = 0.47" },
        { "type": "connector", "id": "sum_to_relu", "from": "result_val", "to": "relu_out" }
      ],
      "animations": [
        { "action": "fade-in", "target": "activate_title", "at": "0s", "duration": "0.8s" },
        { "action": "draw", "target": "sum_to_relu", "at": "2s", "duration": "1s" },
        { "action": "fade-in", "target": "relu_out", "at": "2.5s", "duration": "0.8s" },
        { "action": "highlight", "target": "relu_out", "at": "3.5s", "duration": "2s", "color": "success" },
        { "action": "highlight", "target": "step_activate", "at": "0s", "duration": "16s", "style": "glow", "color": "accent" },
        { "action": "scale", "target": "step_activate", "at": "0.1s", "duration": "0.8s", "scale_factor": 1.12 }
      ]
    }
  ]
}
```

Key patterns in this example:
- **Carousel**: document-level group with `layout.type: "carousel"` — each scene highlights its step
- **Continuity**: `result_val` has the same id and content in both scenes — the engine morphs it smoothly
- **fade-in** for all reveals, **draw** for connectors — no bare `appear`
- **template: "one-column"** and **auto_visible: false** on every scene
"""
