# Local Kaivra MCP

Kaivra includes a local stdio MCP server for guided animation authoring.

## Install

macOS:

```bash
brew install cairo pkg-config ffmpeg
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Ubuntu / Debian:

```bash
sudo apt install libcairo2-dev pkg-config ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Then verify the local setup:

```bash
kaivra-mcp doctor
```

## Claude Code

Fastest setup:

```bash
claude mcp add kaivra -- kaivra-mcp
```

Manual config shape:

```json
{
  "mcpServers": {
    "kaivra": {
      "command": "kaivra-mcp",
      "args": []
    }
  }
}
```

## Workflow

The MCP is intentionally small and opinionated:

1. `add_theme` creates a reusable custom theme JSON in the workspace.
2. `start_animation` creates a starter file from a title, pattern, and beat list.
3. `check_animation` validates, normalizes, and audits the result.
4. `preview_animation` writes an HTML preview and a PNG still.
5. `render_animation` writes the final PNG, MP4, or WebM artifact.

`add_theme` accepts a theme name, an optional `base_theme`, and an `overrides` object whose keys match the `ThemeSpec` fields, such as `accent`, `background_color`, `box_fill`, or `box_border`.

## Patterns

- `process_explainer`
- `algorithm_walkthrough`
- `architecture_explainer`
- `before_after_comparison`

## Local Paths

- Source files: `animations/`
- Theme files: `themes/`
- Preview artifacts: `artifacts/previews/`
- Final renders: `artifacts/renders/`
