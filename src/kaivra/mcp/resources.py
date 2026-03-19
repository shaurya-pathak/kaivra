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

## The Most Important Rule

`start_animation` and `quick_render` produce a SCAFFOLD — a generic skeleton where every scene has the same repeating layout with swapped labels. **You must rewrite each scene's `objects` and `animations` arrays** to create topic-specific diagrams before the animation is presentable.

If every scene in your output has the same structure (heading → panel → lane with source/focus/result), you have shipped the scaffold, not an animation. Each scene must have its own unique visual composition that matches what the beat is explaining.

### What a bad scene looks like (scaffold output, do NOT ship this):
- Heading: "Plants add water vapor"
- Panel with generic lane: Context token → Focus card → Outcome token
- Same structure in every scene, only labels change
- Looks like a slideshow of identical slides

### What a good scene looks like (rewritten with topic-specific content):
- Heading: "1. Compute One Hidden Weighted Sum"
- A row of boxes showing actual computed values: "0.70 × 0.50 = 0.35" and "−0.40 × −0.30 = 0.12"
- A result box: "0.35 + 0.12 = 0.47"
- Connectors drawn from each term to the sum
- Tokens labeling what each term means: "x1 contributes evidence to h1"
- Staggered fade-ins timed to match narration

The good scene uses boxes for real values, connectors for real data flow, tokens for real annotations, and layouts that match the content. It does NOT use a generic "previous → current → next" lane.

## Defaults

- Prefer `visual_explainer` for narrated concept explainers.
- Choose `pacing: educational` for narrated explainers, `balanced` for normal silent demos.
- Prefer `modern` for polished UI-style explainers and `whiteboard` for sketch-style teaching.
- Do not describe MCP setup, workspace paths, or authoring logistics in user-facing output.

## Scene Construction

- Build each scene from `box`, `group`, `connector`, `token`, and short `text` headings. Treat body copy as support, not the main event.
- For technical topics, show actual values, computations, and before/after transformations.
- For non-technical topics, show concrete examples, labeled relationships, and visual hierarchies — not abstract category labels.
- Use `one-column` or `two-column` templates.
- Use `draw` on connectors to reveal flow, dependency, and causality.
- Each scene should have 4–10 meaningful visual objects, not 3 generic placeholders.

## Animation and Reveals

- Start scene objects hidden and reveal them with staggered `fade-in` timings that track the narration.
- Every element that becomes relevant during the scene should have a corresponding reveal or emphasis.
- Prefer `highlight`, `scale`, `fade-in`, light `pulse`, and connector `draw` over busy multi-effect motion.
- Sparse animation is the common failure mode — keep adding reveals until the visuals track the explanation.

## Narration

- Write narration as conversational spoken English with contractions and direct address. Not "Title. Definition."
- For voiced renders, mention labels and values in the same order you want reveals to land.
- Let the explanation determine scene length.

## Continuity

- Reuse the same `id` and `content` across consecutive scenes when a value carries forward. The engine morphs it into its new position.
- When a concept repeats the same operation, show one concrete worked example, then generalize. Do not narrate every repetition.

## Avoid

- The same generic lane/panel structure in every scene
- `absolute` layout
- Walls of body text when narration is present
- One long text stack standing in for the full diagram
- Raw DSL invention before checking the pattern and example resources

## Workflow

1. Call `start_animation` with a `pattern`, `beats`, and `pacing`.
2. **Read the generated JSON and rewrite each scene's objects and animations** to be topic-specific.
3. Call `check_animation` on the rewritten file.
4. Call `preview_animation` to inspect timing and layout.
5. Call `render_animation` when the shape is good.
6. `quick_render` is for fast first drafts only — always rewrite scenes before the final version.
"""


def _pattern_catalog() -> str:
    return """# Starter Pattern Catalog

## `visual_explainer`

Default choice for narrated concept explainers. The starter produces a generic scaffold with the same panel layout in every scene. **You must rewrite each scene's objects** to build topic-specific diagrams — boxes with real values or concrete examples, connectors showing actual relationships, tokens with meaningful labels. The scaffold is a starting point for file structure and pacing, not a finished animation.

## `algorithm_walkthrough`

Use when the user wants a sequence with a clear active step and surrounding context, like compare/swap/progress beats. Still benefits from scene-specific customization but the previous/current/next structure is more natural here.

## `architecture_explainer`

Use when the user wants a systems or pipeline explanation with a stronger sidebar/main-content structure and visible connections between stages.

## `before_after_comparison`

Use when the user is contrasting states, revisions, or outcomes. The MCP compares each beat to the previous one.

## General advice

- All patterns produce starter scaffolds. Rewrite scene objects before shipping.
- Keep beats short and concrete. Put one idea in each beat.
- Prefer connectors, tokens, and persistent IDs when flow or causality matters.
- If several scenes have the same object structure with only labels changed, you are shipping a scaffold. Rewrite them.
- Each scene should have a unique visual composition: different boxes, different connector topology, different grouping — matching what that specific beat explains.
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

## Architecture Explainer

- `two-column` scenes
- Sidebar context + main explanation card
- Connectors and tokens to show the system flow
- Compact text stacks instead of long paragraphs
"""
