# Kaivra Animation Depth Plan

## Summary

Kaivra should get deeper within its current visual style, not broader into a fundamentally different rendering product. Today the engine is strongest as "animated diagrams": boxes, text, tokens, connectors, scene continuity, and a compact set of emphasis animations rendered on a 2D Cairo surface. That is already a legitimate niche.

The strategic goal is not to chase After Effects, Motion Canvas, or Manim. It is to make Kaivra better at the kind of explainer an LLM can reliably author end-to-end without human choreography. The win condition is "good-enough animation that is robust, versionable, and easy to generate," not maximal motion complexity.

## Current Strengths

- The existing primitives already cover a useful visual language: `highlight`, `scale`, `pulse`, `draw`, `appear`, `disappear`, and `move`.
- Scene continuity lets shared objects morph across scenes, which gives explainers a coherent narrative arc without requiring a full retained scene graph.
- The renderer is well-matched to flat explainer visuals: labeled boxes, tokens, arrows, grouped layouts, and data-flow diagrams.
- This keeps the DSL understandable for both humans and LLMs.

## Why Not Broaden Into Complex Animation

### 1. The DSL is the product

- Every new primitive is something the author or LLM has to reason about correctly.
- More choreography means more chances for overlap, clipping, broken timing, and invalid references.
- `check_animation` already has meaningful work to do with the current layout and animation surface area.

### 2. Cairo is the wrong renderer for motion-graphics ambition

- Cairo is a frame-by-frame 2D rasterizer, not a GPU-accelerated retained scene graph.
- Features like skeletal animation, particle systems, physics, 3D transforms, or complex path editing would amount to building a new engine on top of the current one.
- If Kaivra ever needed that class of animation, it would likely require a renderer rewrite rather than an incremental feature pass.

### 3. The competition is already mature

- Tools for high-end motion design already exist and are excellent.
- Kaivra does not need to win on "most expressive animation engine."
- It should win on "most reliable repo-native animation system an LLM can author."

### 4. LLMs are bad at precise choreography

- Complex timing dependencies and freeform motion dramatically increase the failure surface.
- Even current documents benefit from iteration and audit support.
- Deeper compositional expressiveness is more likely to succeed than broader choreography complexity.

## Recommended Additions

These features deepen the current style without changing the product's core abstraction or authoring model.

### 1. Animated value changes

- Allow text or numeric content in a box/token to interpolate over time.
- Examples: count from `0` to `0.7`, change `"input"` into `"0.7"`, or animate a metric readout during a step.
- This fits the renderer well because it only changes what is drawn at time `t`.

### 2. Path-following tokens

- Add a small marker or token that moves along an existing connector path.
- This is a strong fit for data-flow explainers, especially neural-network and systems diagrams.
- The connector geometry already exists, so the path can come from the connector instead of requiring freeform bezier authoring in the DSL.

### 3. Staggered group reveals

- Add a cascade or stagger mode for groups so children reveal one by one in layout order.
- This should support at least top-to-bottom and left-to-right semantics.
- It keeps the model simple while making lists, pipelines, and layered diagrams feel much more alive.

### 4. Color transitions

- Let fills, borders, or text colors interpolate over time.
- This is a simple and powerful way to show inactive -> active -> complete state changes without introducing new object types.
- It fits the current engine naturally and should be LLM-friendly to author.

## What To Avoid

- 3D transforms or camera fly-throughs.
- Physics, particles, or freeform motion systems.
- Generic bezier/path animation authored directly in JSON.
- Asset-heavy image or video embedding as part of the core DSL.
- Rich custom easing choreography that adds authoring burden without major communicative gain.

## Implementation Direction

### 1. Preserve the current visual contract

- Keep Kaivra centered on diagrammatic explainers rather than cinematic animation.
- Avoid new primitives that require authors to think like motion designers.

### 2. Make the new features connector- and layout-aware

- Path-following should derive from existing connector geometry.
- Staggering should derive from group order and layout semantics rather than manual timing micromanagement.

### 3. Keep `check_animation` viable

- Any new animation surface should remain auditable.
- Prefer features whose failure modes are simple: wrong target, invalid connector, or conflicting timing, not open-ended choreography bugs.

### 4. Bias for LLM authorability

- New primitives should be describable in plain language.
- If a feature is hard to prompt for or difficult to validate automatically, it is probably the wrong next addition.

## Acceptance Criteria

- Kaivra can produce richer explainers within its existing flat visual style without changing render architecture.
- The next animation additions are understandable enough for LLM prompting and deterministic enough for audit tooling.
- New capabilities materially improve perceived polish for data flow, state changes, and progressive reveal.
- The product remains clearly differentiated from general-purpose motion graphics tools.

## Suggested Next Steps

1. Prototype animated numeric/text value interpolation on boxes and tokens.
2. Prototype connector-based path-following markers using existing bezier geometry.
3. Add a staggered reveal mode for groups with layout-derived child ordering.
4. Add color interpolation for fills and borders.
5. Extend `check_animation` only as needed to validate the above without expanding into generalized choreography analysis.

## Priority

- Medium.
- This is a good post-polish rendering plan because it improves the perceived quality of explainers without changing the product thesis.
- Do this before any discussion of major renderer rewrites or high-complexity animation ambitions.
