# Kaivra Visual-First Blueprints Plan

## Summary

Starter explainers should look like animations, not slide decks with narration pasted on top. This plan makes narrated starters visual-first by suppressing redundant text, adding a dedicated `visual_explainer` pattern, and teaching existing patterns to use connectors and `draw` so data flow and structure are visible on screen.

## Implementation Changes

### 1. Public surface

- Add `visual_explainer` to the supported starter patterns.
- Keep the existing patterns, but change their narrated output rules so they suppress body text and audience captions by default when `include_narration=True`.
- Continue to allow short headings or step labels so scenes retain orientation.

### 2. Narration-aware scene generation

- In all starter patterns, remove body-text stacks and caption groups when narration is enabled.
- Reserve captions for non-narrated documents or a future explicit subtitle/caption override.
- Keep one primary visual focal object and one short heading, but avoid on-screen text that merely repeats the narration.

### 3. New visual-explainer pattern

- Build `visual_explainer` around boxes, groups, tokens, and connectors rather than body-copy panels.
- Use persistent IDs aggressively so scenes feel like one evolving diagram instead of a fresh slide each time.
- Prefer one diagram progression per beat: reveal node -> draw connector -> highlight active node -> move to next relationship.

### 4. Upgrade existing patterns

- `algorithm_walkthrough`: add connectors between previous/current/next cards and use `draw` plus highlight to show progression.
- `architecture_explainer`: use diagram lanes and inter-component connectors rather than text-heavy two-column copy blocks.
- `process_explainer`: replace the current box-plus-body-text template with a short title and a compact flow or grouped diagram when narration is enabled.
- `before_after_comparison`: keep the side-by-side comparison, but replace redundant detail text with labels, status markers, and animated emphasis.

### 5. Layout semantics and captions

- Replace any semantically incorrect layout declarations so flow content uses `flow` and stacked content uses `stack`.
- If captions are still present in non-narrated scenes, render them above the carousel rail so they do not overlap or sit below navigation content.
- Keep the current carousel, but ensure main-content composition leaves space for it intentionally.

## Acceptance Criteria

- Narrated starter documents no longer include body text or audience-caption groups by default.
- At least `visual_explainer`, `algorithm_walkthrough`, and `architecture_explainer` produce connector-based scenes that visibly use `draw`.
- Generated starter documents keep the carousel readable without caption overlap.
- Layout audits remain clean for the default generated samples.

## Test Plan

### Automated

- Add blueprint tests proving narrated starters omit body text and captions.
- Add pattern tests proving the new `visual_explainer` output contains connectors and `draw` animations.
- Add regression tests for algorithm and architecture starters to confirm connector IDs and targets are valid.
- Add audit-based tests for caption placement and carousel composition.

### Manual

- Generate narrated starters for all patterns and compare them to the current text-heavy output.
- Preview one `visual_explainer` sample and confirm the flow reads without narration echo on screen.
- Render an algorithm walkthrough and verify connectors draw in an order that matches the step progression.

## Dependencies And Sequence

- Coordinate with the pacing plan so visual scenes have enough time to breathe.
- Coordinate with the MCP guidance plan so agent instructions describe the new visual-first default correctly.

## Assumptions And Defaults

- Narrated starters keep short headings but omit explanatory body text and audience captions.
- `visual_explainer` becomes the recommended default for narrated concept explainers, while existing patterns remain available for specific use cases.
- This plan does not add camera choreography; it focuses on object composition and animation primitives already supported by the engine.
