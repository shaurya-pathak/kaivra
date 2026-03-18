# Kaivra MCP Authoring Guidance Plan

## Summary

Update the MCP instructions and authoring resources so agent-generated animations are biased toward slow, visual explainers instead of compact text-heavy slides. This plan aligns the words shown to agents with the starter behavior implemented by the pacing and visual-blueprint plans.

## Implementation Changes

### 1. Public surface

- Add `pacing` to `start_animation` with enum values `educational`, `balanced`, and `quick-demo`.
- Keep `pattern` as the primary shape selector; use `pacing` to control scene timing and explainability defaults.
- Do not add a second overlapping field such as `style_hint`; keep the public surface to one pacing control.

### 2. MCP initialization instructions

- Rewrite the server instructions to explicitly say:
  - create animations that explain concepts slowly and visually
  - prefer diagrams built from boxes, connectors, groups, and tokens
  - use `draw` on connectors to show flow and causality
  - keep narrated scenes around 10-15 seconds unless the user requests a faster style
  - avoid walls of body text when narration is present
  - use `start_animation` first, then `check_animation`, then preview or render

### 3. Authoring profile resource

- Replace the current “one supporting text stack” framing with a visual-first rule set.
- Promote `connector` and `draw` from occasional/niche usage to recommended primitives for explainers.
- Distinguish between narrated explainers and silent quick demos so the model knows when compact text is acceptable.
- Update the suggested loop to mention pacing selection and the new quick-render path once that plan lands.

### 4. Pattern resource alignment

- Update the pattern catalog descriptions so `visual_explainer` is the default recommendation for narrated concept explainers.
- Rewrite example guidance to show that examples are shape references, not templates to copy literally.
- Keep raw DSL invention discouraged, but give agents stronger guidance on when connectors, tokens, and persistent IDs matter.

## Acceptance Criteria

- The MCP tool schema exposes `pacing` on `start_animation`.
- Server instructions and resources consistently push agents toward slower visual explainers.
- Generated starter docs differ materially when `pacing=educational` versus `pacing=quick-demo`.
- The guidance text no longer tells agents to default to one text stack per scene in narrated explainers.

## Test Plan

### Automated

- Add server-schema tests asserting `start_animation` includes the new `pacing` field.
- Add resource-content tests for the authoring profile and pattern catalog.
- Add starter-generation tests covering the interaction between `pattern`, `include_narration`, and `pacing`.

### Manual

- Inspect MCP initialization output and confirm the guidance reads as opinionated and coherent.
- Generate one narrated explainer and one quick demo from the same beats and confirm the pacing control changes the output shape.
- Validate that the new resource language does not conflict with actual starter defaults after the visual-blueprint plan lands.

## Dependencies And Sequence

- Land after the pacing and visual-blueprint plans so the documentation matches real behavior.
- Coordinate with the first-run ergonomics plan for references to `quick_render`.

## Assumptions And Defaults

- `pacing` is the only new author-facing control added to `start_animation` in this plan.
- `educational` is the recommended MCP default for narrated starter generation.
- The MCP remains intentionally opinionated; this plan strengthens that opinion instead of making the instructions more generic.
