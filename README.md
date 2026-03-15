# dsa-anim

`dsa-anim` is a declarative animation engine for turning JSON or YAML into:

- MP4/WebM videos
- PNG stills
- a browser preview

It is meant for explainers, product demos, and step-by-step visualizations where layout and timing matter more than hand-placing pixels.

## What It Does

- validates an animation DSL
- builds a scene graph from semantic layout rules
- renders video, still frames, and a web preview
- audits scenes for overlap and clipping
- supports external theme files
- retimes scenes from audio timing metadata
- can generate offline narration locally with Sherpa

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

dsa-anim validate examples/demos/bubble_sort_demo.json
dsa-anim render examples/demos/bubble_sort_demo.json -o out.mp4
dsa-anim preview examples/demos/bubble_sort_demo.json --serve
dsa-anim audit examples/demos/bubble_sort_demo.json
```

You will also need `ffmpeg` installed for video output.

## Common Commands

```bash
dsa-anim validate FILE.json
dsa-anim render FILE.json -o out.mp4
dsa-anim render FILE.json -o frame.png
dsa-anim preview FILE.json --serve
dsa-anim audit FILE.json
dsa-anim schema
dsa-anim theme-schema
dsa-anim validate-theme examples/themes/nvidia.json
```

## Themes

Built-in themes still work through `meta.theme`.

You can override them with an external JSON theme file:

```bash
dsa-anim render \
  examples/demos/bubble_sort_demo.json \
  -o out.mp4 \
  --theme-file examples/themes/nvidia.json
```

Bundled external theme:

- `examples/themes/nvidia.json`

## Local Voice

Local voice is optional and uses Sherpa.

Install the extra:

```bash
source .venv/bin/activate
python -m pip install -e '.[local-voice]'
```

Render with local narration:

```bash
dsa-anim render \
  examples/explainers/agentic_debug_agent_explainer.json \
  -o out.mp4 \
  --voice-mode local \
  --voice-model /path/to/sherpa-model-dir
```

The model directory should contain:

- an `.onnx` model
- `tokens.txt`
- `espeak-ng-data/`

`dsa-anim` will use the Sherpa executable if it exists, and otherwise fall back to the installed Python API. Local voice currently retimes by generated scene duration; it does not produce word-level timing data on its own.

## Audio Inputs

If you already have narration audio, you can render with it directly:

```bash
dsa-anim render \
  examples/demos/agentic_triage.json \
  -o out.mp4 \
  --audio narration.wav \
  --audio-timings timings.json
```

Supported timing sidecars:

```json
{
  "scene_durations": {
    "intro": 4.2,
    "explain": 7.8
  }
}
```

```json
{
  "scenes": [
    {
      "id": "intro",
      "duration_seconds": 4.2,
      "cues": [
        { "start_seconds": 0.6, "duration_seconds": 0.8, "text": "first beat" }
      ]
    }
  ]
}
```

## Repo Layout

```text
src/dsa_anim/
  cli.py
  dsl/
  scene_graph/
  layout/
  render/
  audio/
  themes/
  qa/

examples/
  algorithms/
  demos/
  explainers/
```

## Development

Run the basic checks:

```bash
source .venv/bin/activate
python -m compileall src tests
pytest -q
```

Useful example files:

- `examples/demos/bubble_sort_demo.json`
- `examples/demos/agentic_triage.json`
- `examples/explainers/agentic_debug_agent_explainer.json`
