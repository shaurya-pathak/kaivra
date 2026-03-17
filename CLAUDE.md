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

- **New object type**: Add to `ObjectType` enum in schema.py, add fields to `ObjectSpec`, add size estimator in `_sizing.py`, add draw method in `cairo_renderer.py`, add JS draw function in `web/exporter.py`
- **New animation**: Add to `AnimAction` enum in schema.py, handle in `timeline.py` `apply_animations_at_time`, handle in JS `applyAnimations`
- **New layout**: Add to `LayoutType` enum, create strategy class in `layout/strategies/`, register in `layout/engine.py`
- **New theme**: Create file in `themes/`, register in `themes/registry.py`

## Testing

```bash
source .venv/bin/activate
kaivra validate examples/algorithms/bubble_sort.json   # parse + validate
kaivra render examples/algorithms/bubble_sort.json -o test.png  # static frame
kaivra render examples/algorithms/bubble_sort.json -o test.mp4  # full video
```
