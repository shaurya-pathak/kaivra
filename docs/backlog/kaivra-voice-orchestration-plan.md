# Kaivra Voice Orchestration Plan

## Summary

Unify voice generation, retiming, rendering, and muxing into one shared orchestration path that works in both the CLI and MCP workflow. Today the pieces exist, but the user still has to stitch them together manually. This plan turns voice rendering into a first-class workflow with better defaults, workspace-aware theme resolution, stronger local-provider support, and progress reporting across all stages.

## Implementation Changes

### 1. Public surface

- Extend `render_animation` in MCP with `voice`, `voice_provider`, and `voice_id` instead of creating a second render tool.
- Keep CLI `kaivra render --voice`, but route it through the same shared orchestration code used by MCP.
- Add `KAIVRA_VOICE_PROVIDER` as the default provider selector when the caller omits `voice_provider`.
- Continue to reject `voice=true` when the caller also supplies `audio_path` or `audio_timings_path`.

### 2. Shared voice pipeline

- Extract the current CLI-only `_render_with_voice` flow into a reusable module under the main package, not the CLI layer.
- The shared flow should do exactly this: discover provider -> generate per-scene audio -> normalize generated audio to WAV -> build `AudioTimingData` -> retime document -> render silent video -> concatenate WAVs -> mux final artifact.
- Normalize generated audio to WAV before concat so mixed provider output formats do not create codec or extension mismatches.
- Use a `.wav` concat artifact, not `.mp3`, when combining per-scene narration assets.

### 3. Workspace and theme resolution

- Reuse the same theme-search-root handling in CLI and MCP so custom workspace themes resolve consistently.
- Build CLI theme roots from the input document path by walking upward to the nearest ancestor that contains `themes/`, plus `cwd/themes` as a fallback.
- Remove duplicate render-graph construction logic where possible so the theme-resolution fix only lives in one place.

### 4. Local provider support

- Update `LocalProvider` to accept `model_path`, `tokens_path`, and `data_dir`.
- If only `model_path` is provided, auto-discover `tokens.txt` and `espeak-ng-data/` relative to the model directory.
- If nothing is provided, look for `SHERPA_MODEL_PATH` first and then the default download location under `~/.kaivra/models/`.
- Return a clear actionable error if autodiscovery fails.

### 5. Progress and diagnostics

- Emit progress updates for each voice stage: provider discovery, per-scene TTS generation, audio normalization, concat, silent render, and mux.
- In MCP, map these to the existing progress callback path so users get feedback during long narrated renders.
- In CLI, print one concise line per stage and per generated scene.

## Acceptance Criteria

- A user can render a narrated MP4 from MCP without writing a glue script or precomputing timings.
- The CLI and MCP produce equivalent narrated output for the same input document and provider settings.
- Custom workspace themes resolve in both flows.
- Local Sherpa models work with only the downloaded model directory present, without manual token and espeak path wiring.

## Test Plan

### Automated

- Add unit tests for provider default selection via `KAIVRA_VOICE_PROVIDER`.
- Add tests for local-provider autodiscovery of `tokens.txt` and `espeak-ng-data/`.
- Add integration-style tests for the shared orchestration helper with mocked provider output, retiming, concat, and mux.
- Add MCP tests asserting `render_animation` accepts voice-related fields and emits staged progress messages.
- Add regression coverage for custom theme lookup in CLI render, audit, and sample flows.

### Manual

- Render one narrated explainer with the ElevenLabs provider and one with the local provider.
- Confirm per-stage progress is visible in both CLI and MCP.
- Verify the final muxed artifact duration matches the concatenated narration track closely enough to avoid obvious drift.

## Dependencies And Sequence

- Land early because it unblocks the first-run experience and makes the improved narrated pacing easy to validate.
- Coordinate with the first-run ergonomics plan for model download and install guidance.

## Assumptions And Defaults

- MCP uses `render_animation.voice=true` rather than a separate `render_with_voice` tool.
- WAV is the canonical intermediate format for generated narration assets, even if providers return MP3 or another source format.
- Provider discovery remains plugin-based through the existing entry-point registry.
