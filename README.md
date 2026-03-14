# dsa-anim

Declarative animation engine for LLMs: JSON or YAML in, animation out.

We are intentionally treating the current surface area as the stable base. The goal is not to keep inventing features; the goal is to make the existing ones reliable, documented, and easy for both humans and LLMs to use well.

## What It Does

- Validates a semantic animation DSL.
- Resolves scenes into a renderer-friendly scene graph.
- Renders stills, videos, and browser previews.
- Audits animations for overlap and clipping problems.
- Attaches external audio to rendered videos.
- Retimes scene pacing from audio timing sidecars.
- Aligns local emphasis beats such as `highlight`, `pulse`, and `focus_style` to audio cues when timing data is available.

## Locked CLI Surface

- `dsa-anim validate`
- `dsa-anim render`
- `dsa-anim preview`
- `dsa-anim audit`
- `dsa-anim schema`

The stable audio-related render flags are:

- `--audio`
- `--audio-timings`

## Quick Start

```bash
source .venv/bin/activate

dsa-anim validate examples/archived/llm_inference.json
dsa-anim render examples/algorithms/bubble_sort.json -o output.mp4
dsa-anim preview examples/demos/bubble_sort_demo.json --serve
dsa-anim audit examples/explainers/agentic_debug_agent_explainer.json
dsa-anim schema
```

## Audio Workflow

`dsa-anim` is audio-provider agnostic.

- `--audio` muxes an existing audio file onto a rendered video.
- `--audio-timings` retimes scenes from a JSON sidecar.

Example:

```bash
source .venv/bin/activate

dsa-anim render \
  examples/explainers/agentic_debug_agent_explainer.json \
  -o artifacts/videos/explainers/agentic_debug_agent_explainer_voice_local.mp4 \
  --audio artifacts/audio/explainers/agentic_debug_agent_explainer_local_tts.m4a \
  --audio-timings artifacts/audio/explainers/agentic_debug_agent_explainer_local_tts_timings.json
```

Supported timing sidecars:

```json
{
  "scene_durations": {
    "setup": 8.4,
    "compare_swap": 9.1
  }
}
```

```json
{
  "scenes": [
    {
      "id": "setup",
      "duration_seconds": 8.4,
      "cues": [
        { "start_seconds": 1.1, "duration_seconds": 0.9, "text": "first beat" },
        { "at": "3.5s", "end": "4.4s", "kind": "phrase" }
      ]
    }
  ]
}
```

Cue-aware retiming rules:

- Broad persistent chapter glows stay broad.
- Scene-local glows and pulses snap to cue windows.
- `focus_style` timing also snaps to cue windows.
- If a sidecar only has scene durations, DSA falls back to narration-clause inference for local emphasis timing.

## Repository Layout

```text
src/dsa_anim/
  cli.py
  audio/
  dsl/
  layout/
  qa/
  render/
  scene_graph/
  themes/
  utils/

examples/
  algorithms/
  demos/
  explainers/
  archived/

docs/
  BASELINE.md
  backlog/
```

## Quality Checks

Core validation loop:

```bash
source .venv/bin/activate

python -m compileall src tests
dsa-anim validate examples/explainers/agentic_debug_agent_explainer.json
dsa-anim audit examples/explainers/agentic_debug_agent_explainer.json
```

Pytest lives in the dev dependency set:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

## Examples

- `/Users/shauryapathak/Desktop/Development/dsa-animation/examples/algorithms/bubble_sort.json`
- `/Users/shauryapathak/Desktop/Development/dsa-animation/examples/demos/bubble_sort_demo.json`
- `/Users/shauryapathak/Desktop/Development/dsa-animation/examples/demos/agentic_triage.json`
- `/Users/shauryapathak/Desktop/Development/dsa-animation/examples/explainers/dsa_architecture_explainer.json`
- `/Users/shauryapathak/Desktop/Development/dsa-animation/examples/explainers/agentic_debug_agent_explainer.json`

## Design Intent

- Semantic layout first, not hand-authored pixel coordinates.
- Beautiful defaults over scene-by-scene micromanagement.
- Stable primitives that LLMs can use consistently.
- External audio support without hard-coding a specific TTS provider into DSA itself.

More detail on the frozen baseline is in `/Users/shauryapathak/Desktop/Development/dsa-animation/docs/BASELINE.md`.
