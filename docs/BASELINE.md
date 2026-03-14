# Frozen Baseline

This document describes the quality bar and supported feature set we are intentionally freezing around.

## Product Boundary

`dsa-anim` owns:

- the DSL
- validation
- scene graph construction
- rendering
- continuity behavior
- overlap and clipping audits
- generic audio muxing
- generic audio-timing-aware retiming

`dsa-anim` does not own:

- a specific TTS provider
- prompt-engineering instructions such as `SKILL.md`
- demo-specific orchestration outside the DSL

## Stable Commands

- `dsa-anim validate`
- `dsa-anim render`
- `dsa-anim preview`
- `dsa-anim audit`
- `dsa-anim schema`

## Stable Render Flags

- `--fps`
- `--audio`
- `--audio-timings`

## Stable Timing Behavior

When `--audio-timings` is present:

- scene durations retime to the supplied scene duration metadata
- continuity and glow-release padding scale with the retime
- scene-local `highlight`, `pulse`, and `focus_style` beats align to cue windows when cues are present
- if only durations are present, DSA infers approximate beat windows from scene narration

Intentional exceptions:

- long-lived persistent glows such as chapter or carousel emphasis are left broad instead of being snapped to narrow voice cues

## Quality Bar

Every stabilization pass should preserve these expectations:

- no layout overlap regressions in audited scenes
- no hard scene cuts for shared content when continuity is enabled
- no text-scaling artifacts on shell-only scale by default
- no provider-specific assumptions in the core CLI audio path
- no undocumented JSON sidecar formats

## Required Local Checks

Minimum checks before calling the base stable:

```bash
source .venv/bin/activate
python -m compileall src tests
dsa-anim validate examples/explainers/agentic_debug_agent_explainer.json
dsa-anim audit examples/explainers/agentic_debug_agent_explainer.json
```

If dev dependencies are installed:

```bash
source .venv/bin/activate
python -m pytest
```

## Cleanup Rules

When cleaning up code, prefer:

- fewer public pathways
- shared helpers over repeated inline logic
- explicit timing heuristics with named constants
- tests that lock down behavior instead of comments that merely promise it

Avoid:

- adding new primitives unless they are necessary for correctness
- provider-specific abstractions inside `dsa-anim`
- demo-only hacks in core rendering code
