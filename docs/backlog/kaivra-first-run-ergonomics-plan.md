# Kaivra First-Run Ergonomics Plan

## Summary

Reduce the number of manual steps required to get from a clean machine to a successful first render. Today install, dependency setup, model acquisition, and MCP registration are all separate pieces. This plan defines a supported bootstrap path, adds helper commands, surfaces doctor checks earlier, and creates a simpler quick-start render flow.

## Implementation Changes

### 1. Supported install path

- Add a top-level `Makefile` with at least `install`, `install-voice-local`, `doctor`, and `smoke` targets.
- Keep the `uv`-based setup, but document it as a two-step install when voice providers are needed: core repo first, then local editable install of `packages/kaivra-voice`.
- Update the README and local MCP docs so the voice package requirement is impossible to miss.

### 2. Doctor integration

- Add `kaivra doctor` to the main CLI as a wrapper around the existing environment checks.
- Run a lightweight doctor preflight the first time the user invokes guided commands that require system deps, specifically `preview`, `render`, `quick-render`, and `mcp-install`.
- When doctor finds missing Cairo, ffmpeg, ffprobe, or package install issues, return actionable fix text before attempting the main operation.

### 3. Model download

- Add `kaivra download-model` with defaults targeting `vits-piper-en_US-amy-low`.
- Download into `~/.kaivra/models/vits-piper-en_US-amy-low/` and ensure the directory contains the model file, `tokens.txt`, and `espeak-ng-data/`.
- Print the resolved local-provider paths at the end so the user can verify the install.

### 4. MCP install helper

- Add `kaivra mcp-install` with `--client auto|claude-code|cursor`.
- In `auto` mode, prefer Claude Code if its config path is present, then Cursor.
- Write or update the relevant local stdio config entry so the user does not have to hand-edit JSON.
- Keep the existing `kaivra-mcp` server binary; this command only installs config.

### 5. Quick render workflow

- Add `kaivra quick-render` to validate, audit, and render an existing animation file in one command.
- Add MCP `quick_render` to run `start_animation -> check_animation -> render_animation` with sensible defaults for first-time guided use.
- Default `quick_render` to `png` in dry runs and `mp4` when narration or voice is requested.

## Acceptance Criteria

- A fresh user can follow one documented install path and reach a successful `doctor` and sample render without discovering hidden package requirements.
- Missing system dependencies are reported up front with clear fix commands.
- Local model acquisition is one command, not a manual scavenger hunt.
- MCP registration works without manual config edits for supported clients.

## Test Plan

### Automated

- Add CLI tests for `kaivra doctor`, `kaivra download-model --help`, `kaivra mcp-install --help`, and `kaivra quick-render`.
- Add tests for fresh-workspace failure messages when ffmpeg, ffprobe, or Cairo are unavailable.
- Add tests for MCP config generation with mocked client config paths.
- Add integration coverage for the new `quick_render` flow with mocked render steps.

### Manual

- Walk through the new README from a clean environment and confirm it produces a first render without hidden steps.
- Run `kaivra download-model` and verify the local provider can use the downloaded model directory directly.
- Run `kaivra mcp-install --client auto` on a machine with Claude Code and one with Cursor.

## Dependencies And Sequence

- Land first because it removes friction for validating every other UX improvement.
- Coordinate with the voice orchestration plan so the install and model-download docs match the runtime behavior exactly.

## Assumptions And Defaults

- `make` is acceptable as the first supported bootstrap surface.
- Voice install remains opt-in rather than a mandatory core dependency.
- `quick_render` is intentionally a convenience flow and may expose fewer knobs than the full render commands.
