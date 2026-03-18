# Kaivra

Kaivra is a declarative animation engine for turning structured JSON or YAML into polished stills, videos, and web previews.

## First-Time Setup

Run these commands from the repo root. This is the fastest supported path on a clean machine.

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

### 3. Install Kaivra core

```bash
make install
source .venv/bin/activate
```

### 4. Optional: install voice support

Voice is intentionally packaged separately so the core renderer stays lightweight. If you want narrated renders, install the editable voice package from this repo too:

```bash
make install-voice-local
```

That installs `packages/kaivra-voice` in editable mode plus the Sherpa local dependency set. It exposes the built-in `local` and `elevenlabs` providers through Kaivra's discovery hooks.

### 5. Verify the install

```bash
kaivra doctor
```

If `doctor` is green, you are ready to use Kaivra locally and connect it to an MCP client.

### 6. Render a first silent sample

```bash
kaivra quick-render examples/algorithms/bubble_sort.json
```

That validates, audits, and renders a quick PNG into `artifacts/quick-renders/`.

### 7. Optional: render a first narrated sample

```bash
kaivra download-model
KAIVRA_VOICE_PROVIDER=local \
kaivra quick-render examples/explainers/agentic_debug_agent_explainer.json --voice
```

If voice providers are not installed yet, Kaivra will tell you to run `make install-voice-local` or the equivalent editable `pip install` command from the repo root.

## MCP Setup

Kaivra ships with a local stdio MCP server for guided authoring in tools like Claude Code, Cursor, and other MCP clients.

### One-command install

```bash
kaivra mcp-install --client auto
```

`auto` prefers Claude Code when `~/.claude.json` is present, then Cursor.

### Manual stdio MCP config

If your client asks for a command, point it at the virtualenv binary directly:

```json
{
  "mcpServers": {
    "kaivra": {
      "type": "stdio",
      "command": "/absolute/path/to/this/repo/.venv/bin/kaivra-mcp",
      "args": []
    }
  }
}
```

That same shape works for Claude Code, Cursor, and most other local stdio MCP clients. The key detail is: use the full path to `.venv/bin/kaivra-mcp` so the client does not need a manually activated shell.

## Quick Smoke Test

```bash
make doctor
make smoke
```

For a narrated smoke pass after voice install:

```bash
KAIVRA_VOICE_PROVIDER=local kaivra quick-render \
  examples/explainers/agentic_debug_agent_explainer.json \
  --voice
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
- `kaivra doctor` checks Python, Cairo, ffmpeg, ffprobe, and a smoke render.
- `kaivra quick-render` validates, audits, and renders an existing animation in one command.
- `kaivra download-model` installs the default local Sherpa voice model into `~/.kaivra/models/`.
- `kaivra mcp-install` writes a local MCP config for Claude Code or Cursor.
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

If you are using the Python API, use `register_theme("mint-breeze", {...})` for an in-memory theme or `load_theme_file("themes/mint-breeze.json")` when the theme already lives on disk.

## Audio

Kaivra keeps the core package lightweight, and voice support lives in the local editable package at `packages/kaivra-voice`.

Providers are discovered from installed `kaivra.voice_providers` entry points. After `make install-voice-local`, Kaivra can resolve `local` and `elevenlabs` automatically. Use `--voice-provider` or `KAIVRA_VOICE_PROVIDER` to pick the default provider.

If you see a "Voice providers are not installed" error, fix it with one of these repo-root commands:

```bash
make install-voice-local
# or
.venv/bin/python -m pip install -e "./packages/kaivra-voice[local]"
```

For local Sherpa narration after `make install-voice-local`, download the default model bundle with:

```bash
kaivra download-model
```

That installs into `~/.kaivra/models/vits-piper-en_US-amy-low/` and prints the resolved `model_path`, `tokens_path`, and `data_dir` so you can verify the bundle.

You can still attach pre-generated audio without the voice package:

```bash
kaivra render \
  examples/explainers/agentic_debug_agent_explainer.json \
  -o artifacts/videos/explainers/agentic_debug_agent_explainer_with_audio.mp4 \
  --audio artifacts/audio/explainers/agentic_debug_agent_explainer_audio_track.mp3 \
  --audio-timings artifacts/audio/explainers/agentic_debug_agent_explainer_audio_timings.json
```

`--audio` muxes an existing track onto the render. `--audio-timings` retimes scene pacing from a JSON sidecar, and when cue windows are present Kaivra can align scene-local emphasis beats to those cues. If the sidecar only includes scene durations, Kaivra rescales authored timings proportionally and does not infer beat windows from narration text.

On-screen narration text is controlled by `meta.show_subtitles`. Older documents that still use `meta.show_narration` remain valid as a backward-compatible alias.

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
kaivra doctor
kaivra quick-render examples/algorithms/bubble_sort.json
```

## Examples

- `examples/algorithms/bubble_sort.json`
- `examples/demos/bubble_sort_demo.json`
- `examples/demos/agentic_triage.json`
- `examples/explainers/kaivra_architecture_explainer.json`
- `examples/explainers/agentic_debug_agent_explainer.json`

More detail on the stable baseline lives in `docs/BASELINE.md`.
