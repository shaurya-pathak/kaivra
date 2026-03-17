# Kaivra

Kaivra is a declarative animation engine for turning structured JSON or YAML into polished stills, videos, and web previews.

## Quick Start

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'

kaivra validate examples/algorithms/bubble_sort.json
kaivra render examples/algorithms/bubble_sort.json -o output.mp4
kaivra preview examples/demos/bubble_sort_demo.json --serve
kaivra audit examples/explainers/agentic_debug_agent_explainer.json
kaivra schema
kaivra-mcp doctor
```

## CLI

- `kaivra validate` checks an animation file against the DSL.
- `kaivra render` exports PNG, MP4, or web-backed output.
- `kaivra preview` builds the browser preview player.
- `kaivra audit` samples scenes for overlap and clipping issues.
- `kaivra schema` prints the JSON Schema for authoring.

## Local MCP

Kaivra now ships with a local stdio MCP server for guided authoring in tools like Claude Code.

Quick path from this repo:

```bash
# macOS
brew install cairo pkg-config ffmpeg

# Ubuntu / Debian
sudo apt install libcairo2-dev pkg-config ffmpeg

source .venv/bin/activate
python -m pip install -e '.[dev]'
kaivra-mcp doctor
claude mcp add kaivra -- kaivra-mcp
```

The MCP exposes a compact workflow:

- `doctor_kaivra`
- `add_theme`
- `start_animation`
- `check_animation`
- `preview_animation`
- `render_animation`

It writes starter files to `animations/`, custom themes to `themes/`, previews to `artifacts/previews/`, and final renders to `artifacts/renders/`.

More setup detail lives in `docs/LOCAL_MCP.md`.

## Themes

Kaivra supports built-in themes and local JSON theme files.

```bash
mkdir -p themes
# add a custom theme file like themes/mint-breeze.json
# then set "meta.theme": "mint-breeze" in your animation JSON
kaivra render examples/algorithms/bubble_sort.json -o output.mp4
```

If you are using the MCP flow, `add_theme` will create the theme JSON for you inside `themes/`.

## Audio

Kaivra keeps the core CLI audio-provider agnostic.
It does not synthesize speech; audio must be produced outside the renderer.

```bash
kaivra render \
  examples/explainers/agentic_debug_agent_explainer.json \
  -o artifacts/videos/explainers/agentic_debug_agent_explainer_with_audio.mp4 \
  --audio artifacts/audio/explainers/agentic_debug_agent_explainer_audio_track.mp3 \
  --audio-timings artifacts/audio/explainers/agentic_debug_agent_explainer_audio_timings.json
```

`--audio` muxes an existing track onto the render. `--audio-timings` retimes scene pacing from a JSON sidecar, and when cue windows are present Kaivra can align scene-local emphasis beats to those cues. If the sidecar only includes scene durations, Kaivra rescales authored timings proportionally and does not infer beat windows from narration text.

## Repository Layout

```text
src/kaivra/
examples/
docs/
tests/
```

## Checks

```bash
source .venv/bin/activate
python -m compileall src tests
python -m pytest
kaivra validate examples/explainers/agentic_debug_agent_explainer.json
kaivra audit examples/explainers/agentic_debug_agent_explainer.json
```

## Examples

- `examples/algorithms/bubble_sort.json`
- `examples/demos/bubble_sort_demo.json`
- `examples/demos/agentic_triage.json`
- `examples/explainers/kaivra_architecture_explainer.json`
- `examples/explainers/agentic_debug_agent_explainer.json`

More detail on the stable baseline lives in `docs/BASELINE.md`.
