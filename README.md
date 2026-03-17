# Kaivra

Kaivra is a declarative animation engine for turning structured JSON or YAML into polished stills, videos, and web previews.

## First-Time Setup

Run these commands from the repo root.

### 1. Install `uv`

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If you already have `uv`, skip that step.

### 2. Install system dependencies

macOS:

```bash
brew install cairo pkg-config ffmpeg
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install libcairo2-dev pkg-config ffmpeg
```

### 3. Create the environment and install the repo

```bash
uv sync --extra dev
source .venv/bin/activate
```

### 4. Verify the install

```bash
kaivra-mcp doctor
```

If `doctor` is green, you are ready to use Kaivra locally and connect it to an MCP client.

## MCP Setup

Kaivra ships with a local stdio MCP server for guided authoring in tools like Claude Code, Cursor, and other MCP clients.

### Fastest Claude Code setup

From the repo root:

```bash
claude mcp add kaivra -- "$(pwd)/.venv/bin/kaivra-mcp"
```

### Generic stdio MCP config

If your client asks for a command, point it at the virtualenv binary directly:

```json
{
  "mcpServers": {
    "kaivra": {
      "command": "/absolute/path/to/this/repo/.venv/bin/kaivra-mcp",
      "args": []
    }
  }
}
```

That same shape works well as the starting point for Cursor and most other local stdio MCP clients. The key detail is: use the full path to `.venv/bin/kaivra-mcp` so the client does not need a manually activated shell.

## Quick Smoke Test

```bash
source .venv/bin/activate
kaivra validate examples/algorithms/bubble_sort.json
kaivra render examples/algorithms/bubble_sort.json -o output.mp4
kaivra-mcp doctor
```

## Local MCP

The MCP exposes a compact workflow:

- `doctor_kaivra`
- `add_theme`
- `start_animation`
- `check_animation`
- `preview_animation`
- `render_animation`

It writes starter files to `animations/`, custom themes to `themes/`, previews to `artifacts/previews/`, and final renders to `artifacts/renders/`.

More setup detail lives in `docs/LOCAL_MCP.md`.

## CLI

- `kaivra validate` checks an animation file against the DSL.
- `kaivra render` exports PNG, MP4, or web-backed output.
- `kaivra preview` builds the browser preview player.
- `kaivra audit` samples scenes for overlap and clipping issues.
- `kaivra schema` prints the JSON Schema for authoring.

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
