# Local Kaivra MCP

Kaivra includes a local stdio MCP server for guided animation authoring.

## Install

Run these commands from the repo root.

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

### 3. Create the environment and install Kaivra

```bash
uv sync --extra dev
source .venv/bin/activate
```

### 4. Verify the local setup

```bash
kaivra-mcp doctor
```

If `doctor` is green, point your MCP client at `.venv/bin/kaivra-mcp`.

## MCP Client Setup

### Claude Code

Fastest setup:

```bash
claude mcp add kaivra -- "$(pwd)/.venv/bin/kaivra-mcp"
```

### Generic stdio config

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

Use that same command path pattern for Cursor or any other local stdio MCP client.

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
