# Local Kaivra MCP

Kaivra includes a local stdio MCP server for guided animation authoring.

## Install

Run these commands from the repo root.

Kaivra targets Python 3.12+. If you use `uv`, the repo's [`.python-version`](/Users/shauryapathak/Desktop/Development/dsa-animation/.python-version) file gives it a supported default interpreter for the local virtualenv.

### 1. Install `uv`

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install system dependencies

macOS:

```bash
brew install cairo pkg-config ffmpeg
```

Ubuntu / Debian:

```bash
sudo apt install libcairo2-dev pkg-config ffmpeg
```

### 3. Install Kaivra core

```bash
make install
source .venv/bin/activate
```

### 4. Optional: install voice support

If you want local or provider-backed narration, install the editable voice package too:

```bash
make install-voice-local
```

That install exposes the built-in `openai`, `local`, and `elevenlabs` providers through Kaivra's provider discovery hooks. Use `--voice-provider` or `KAIVRA_VOICE_PROVIDER` when you want to force one. If you omit `voice_provider`, Kaivra defaults to `openai` for cloud narration.

If you want the default local Sherpa bundle after that:

```bash
kaivra download-model
```

### 5. Verify the local setup

```bash
kaivra doctor
```

If `doctor` is green, point your MCP client at `.venv/bin/kaivra-mcp`. The doctor report prints the exact resolved command path plus the default local voice model name and destination directory.

## MCP Client Setup

### Automatic install

```bash
kaivra mcp-install --client auto
```

`auto` prefers Claude Code when `~/.claude.json` already exists, then Cursor.

### Generic stdio config

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

Use that same command path pattern for Cursor or any other local stdio MCP client.

After any editable install or package update that changes Kaivra code, restart the MCP client so it reloads the `kaivra-mcp` process instead of serving stale imports.
Use `kaivra doctor` if you want to verify the exact binary path your MCP client should be launching.

## Workflow

The MCP is intentionally small and opinionated:

1. `add_theme` creates a reusable custom theme JSON in the workspace.
2. `plan_animation` gathers topic, audience, theme, structure, and voice choices.
3. Write the animation JSON directly in `animations/`.
4. `check_animation` validates, normalizes, and audits the result.
5. `preview_animation` writes an HTML preview and a PNG still.
6. `render_animation` writes the final PNG, MP4, or WebM artifact.

`animations/` is a local workspace and is gitignored by default. If a draft graduates into a curated repo example, move it into `examples/` intentionally. Keep throwaway or alternate example variants under `examples/local/`.

The MCP is tuned for narrated process explainers: prefer `process_explainer` for narrated flows, use `visual_explainer` when one strong concept diagram is the right core visual, and build scene-specific diagrams from boxes, connectors, groups, and tokens. Use connector `draw` animations to show flow. Prefer persistent document-level objects when labels, chapter trackers, or shared state should stay on screen across scenes. Reuse the same `id` and the same content when a value carries from one scene into the next so continuity can create a smooth carry-over. Prefer `fade-in` for smooth reveals, and use `appear` when you want an intentional instant snap-in. Write narration in clear spoken English and avoid filenames, repo paths, and internal component inventories unless the user explicitly wants implementation detail. Revealing a group will also reveal descendants that do not have their own visibility animation.

`add_theme` accepts a theme name, an optional `base_theme`, and an `overrides` object whose keys match the `ThemeSpec` fields, such as `accent`, `background_color`, `box_fill`, or `box_border`.

If you edit JSON directly, use `meta.show_subtitles` when you want narration text rendered on screen. Older `meta.show_narration` files still load, but `show_subtitles` is the preferred field name now.

For default cloud narration, the recommended loop is:

1. `export OPENAI_API_KEY=your-key`
2. `kaivra quick-render <file> --voice`

For offline local narration, the recommended loop is:

1. `kaivra doctor`
2. `kaivra download-model`
3. `KAIVRA_VOICE_PROVIDER=local kaivra quick-render <file> --voice`

## Patterns

- `process_explainer`
- `visual_explainer`
- `algorithm_walkthrough`
- `architecture_explainer`
- `before_after_comparison`

## Local Paths

- Source files: `animations/`
- Theme files: `themes/`
- Preview artifacts: `artifacts/previews/`
- Final renders: `artifacts/renders/`
