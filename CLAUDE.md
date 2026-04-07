# kaivra

Declarative animation engine for LLMs — "Typst for animations." JSON DSL → animated video/web preview.

## Quick Start

```bash
source .venv/bin/activate
kaivra validate examples/algorithms/bubble_sort.json
kaivra render examples/algorithms/bubble_sort.json -o output.mp4
kaivra preview examples/algorithms/bubble_sort.json --serve
kaivra schema  # JSON Schema for LLM prompting
```

## Project Structure

```
examples/
  algorithms/                    # small source examples like bubble sort
  demos/                         # polished demo JSON files
  explainers/                    # long-form narrated explainers
  archived/                      # older reference examples kept for context
docs/
  backlog/                       # project follow-up notes and TODOs
src/kaivra/
  cli.py                          # Click CLI entry point
  dsl/
    schema.py                     # Pydantic v2 models — THE core DSL definition
    parser.py                     # JSON/YAML loading + validation + auto-ID
  scene_graph/
    models.py                     # Internal IR: SceneGraph, SceneNode, keyframes
    builder.py                    # DSL → scene graph (layout + timeline resolution)
    timeline.py                   # Animation state computation at time t
  layout/
    engine.py                     # Layout dispatcher
    strategies/                   # center, grid, flow, stack, split
      _sizing.py                  # Object size estimation heuristics
  render/
    cairo_renderer.py             # Cairo-based frame renderer (all draw logic)
    video/exporter.py             # Frame-by-frame → ffmpeg pipe → MP4/WebM
    web/exporter.py               # Self-contained HTML + Canvas JS player
  themes/
    base.py                       # ThemeSpec dataclass + style/color/gap resolution
    whiteboard.py                 # Default theme
    registry.py                   # Theme lookup
  utils/
    easing.py                     # Easing functions (linear, ease-in-out, spring, bounce)
    geometry.py                   # Rect, Point, Size
    color.py                      # Hex ↔ RGBA conversion
```

## Tech Stack

- **Python 3.13** with uv for package management
- **Pydantic v2** — DSL schema + JSON Schema export
- **pycairo** — 2D rendering
- **ffmpeg** (system) — video encoding
- **Click** — CLI
- **Jinja2 / vanilla JS** — web preview player

## Key Conventions

- DSL format is **JSON primary**, YAML accepted (YAML is a JSON superset)
- Layout is **semantic** — no pixel coordinates in the DSL. Use layout types: center, grid, flow, stack, split
- Objects start **hidden** — animations make them visible (appear, fade-in, type, etc.)
- The `kaivra schema` command exports the full JSON Schema — feed this to LLMs so they know what to generate
- Video rendering pipes raw BGRA frames to ffmpeg via stdin (no temp files)
- Web preview is a single self-contained HTML file with an embedded Canvas 2D player

## Adding New Features

**IMPORTANT: Renderer changes require MCP prompt + test updates.** The Cairo renderer (`cairo_renderer.py`) and web exporter (`web/exporter.py`) must stay in sync — every visual feature must work in both. When you change rendering behavior, you must also:
1. Update the MCP system prompt in `mcp/server.py` (the `"instructions"` string) so LLMs know the feature exists
2. Update or add tests in `tests/test_mcp_server.py` to assert the prompt mentions the new capability
3. Run `pytest tests/` to verify nothing broke

### DSL versioning

**Do NOT edit `version.py` directly in a PR.** Version bumps are automated via changesets to avoid merge conflicts.

Instead, add a file to `changes/<short-feature-name>.md` with two things:

```
bump: minor
Short description of what changed for the LLM changelog.
```

Use `bump: minor` for backward-compatible additions and `bump: major` for breaking changes.

The CI `changeset` job will fail the PR if `src/kaivra/` or `tests/` files changed without a corresponding `changes/*.md` file.

**Applying changesets (maintainer, before merging a batch of PRs):**
```bash
python scripts/apply_changesets.py          # dry run — shows what will happen
python scripts/apply_changesets.py --write  # applies: bumps version.py, updates all example/test "version" fields, deletes changeset files
```

The script handles everything automatically:
- Picks the highest bump level across all pending changesets (major > minor)
- Bumps `CURRENT_DSL_VERSION` and prepends to `DSL_CHANGELOG` in `version.py`
- Updates all `"version"` fields in `examples/**/*.json` and `tests/**/*.py`
- Deletes the processed changeset files

### Checklists by feature type

- **New object type**: Add to `ObjectType` enum in `schema.py` → add fields to `ObjectSpec` → add size estimator in `_sizing.py` → add draw method in `cairo_renderer.py` → add JS draw function in `web/exporter.py` → serialize new fields in `_serialize_node()` in `web/exporter.py` → update MCP prompt + tests → add a changeset (`bump: minor`)
- **New animation**: Add to `AnimAction` enum in `schema.py` → handle in `timeline.py` `apply_animations_at_time` → handle in JS `applyAnimations` → update MCP prompt + tests → add a changeset (`bump: minor`)
- **New layout**: Add to `LayoutType` enum → create strategy class in `layout/strategies/` → register in `layout/engine.py` → update MCP prompt + tests → add a changeset (`bump: minor`)
- **New theme**: Create file in `themes/` → register in `themes/registry.py`
- **Renderer-only change** (e.g. connector routing, new draw logic): Update both `cairo_renderer.py` AND `web/exporter.py` → update MCP prompt if it affects how LLMs should author content → update tests → add a changeset if it changes what LLMs can generate
- **Breaking DSL change** (removes/renames fields, changes behavior): add a changeset with `bump: major`

### Dual-renderer parity

The Cairo renderer and the web Canvas JS player must produce visually equivalent output. When modifying draw logic:
- `cairo_renderer.py` — Python/Cairo implementation
- `web/exporter.py` — JavaScript/Canvas 2D implementation (embedded in the HTML template as an f-string; use `{{` / `}}` for literal JS braces)
- `web/exporter.py` `_serialize_node()` — ensure any new SceneNode fields are serialized to JSON for the JS player

## Testing

```bash
source .venv/bin/activate
kaivra validate examples/algorithms/bubble_sort.json   # parse + validate
kaivra render examples/algorithms/bubble_sort.json -o test.png  # static frame
kaivra render examples/algorithms/bubble_sort.json -o test.mp4  # full video
pytest tests/                                                    # unit + integration
```
