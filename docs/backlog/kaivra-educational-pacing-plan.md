# Kaivra Educational Pacing Plan

## Summary

Make narrated explainers slower, clearer, and more teachable by default. The current starter blueprints are tuned for short slide beats, which makes narrated explainers feel rushed. This plan adds an explicit pacing preset, retunes narrated scene heuristics, and applies longer default timing envelopes for continuity, focus, highlight, and scale motion.

## Implementation Changes

### 1. Public surface

- Add `meta.pacing` to the DSL with enum values `quick-demo`, `balanced`, and `educational`.
- Default `meta.pacing` to `balanced` for existing documents that omit it.
- Add `pacing` to `start_animation`; if omitted, use `educational` when `include_narration=True` and `balanced` otherwise.
- Keep existing explicit duration strings valid and do not rewrite them unless the document opts into pacing-aware starter generation or runtime scaling.

### 2. Canonical pacing profiles

- `quick-demo`: preserve the current short-form feel for fast demos.
- `balanced`: modestly slower than today and appropriate for silent previews or mixed use.
- `educational`: optimize for narrated explainers and teaching-oriented output.

Use these profile defaults:

- `quick-demo`: scene heuristic `min(8, max(5, 4 + round(word_count / 5)))`, continuity `0.6s`, focus `1.0s`, highlight `1.6s`, scale `0.8s`.
- `balanced`: scene heuristic `min(10, max(6, 5 + round(word_count / 4)))`, continuity `0.9s`, focus `1.2s`, highlight `2.0s`, scale `1.0s`.
- `educational`: scene heuristic `min(16, max(8, 6 + round(word_count / 3)))`, continuity `1.3s`, focus `1.4s`, highlight `2.8s`, scale `1.2s`.

### 3. Starter blueprint behavior

- Replace the current `_scene_duration` logic with a pacing-aware helper that accepts both `Beat` and selected pacing.
- Update `_step_animations` so highlight and scale durations come from the active pacing profile instead of fixed literals.
- Update `focus_style.duration`, `continuity_duration`, and `glow_release_padding` in generated starter documents from the selected pacing profile.
- Preserve the current chapter-carousel highlight behavior, but lengthen the active-step emphasis in `educational` mode so the viewer can follow it comfortably.

### 4. Runtime behavior

- Add a small pacing resolver utility that both starter generation and runtime document handling can share.
- Apply pacing-derived defaults only when the document omits an explicit value; authored explicit values always win.
- Ensure the audio retimer preserves the selected pacing profile by scaling from the new baseline rather than snapping back to old defaults.

## Acceptance Criteria

- Narrated starter documents generated with default inputs produce scene durations in the 8-16 second range unless the beat text is unusually short or long.
- Silent starter documents without an explicit pacing value continue to feel closer to today's output and remain backward-compatible.
- The active chapter highlight, focus pulse, and continuity move are visibly slower in `educational` mode.
- Existing documents without `meta.pacing` still parse and render successfully.

## Test Plan

### Automated

- Add unit tests for the pacing resolver and the per-profile duration heuristics.
- Add starter blueprint tests covering `quick-demo`, `balanced`, and `educational`.
- Add retime tests confirming continuity and glow-release timing scale from the selected pacing profile.
- Add compatibility tests proving existing documents without `meta.pacing` still build the same or intentionally equivalent scene graph.

### Manual

- Generate one narrated explainer starter and confirm scenes land near the 8-16 second target without hand tuning.
- Generate one silent quick demo and confirm it still feels concise.
- Render a before/after sample to verify the new focus and highlight timing reads as intentional rather than sluggish.

## Dependencies And Sequence

- Land this after the first-run and voice orchestration plans so the improved pacing can be exercised in the default narrated workflow.
- Coordinate with the MCP authoring-guidance plan so the agent-facing guidance matches the actual starter behavior.

## Assumptions And Defaults

- `balanced` is the DSL default for backward compatibility.
- Narrated starter generation opts into `educational` unless the caller explicitly requests a different pacing profile.
- This plan does not introduce new animation types; it retunes existing timing defaults.
