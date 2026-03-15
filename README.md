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
- Supports scene templates including `one-column`, `two-column`, and `title-opener`.

## Locked CLI Surface

- `dsa-anim validate`
- `dsa-anim render`
- `dsa-anim preview`
- `dsa-anim audit`
- `dsa-anim schema`
- `dsa-anim theme-schema`
- `dsa-anim validate-theme`

The stable audio-related render flags are:

- `--audio`
- `--audio-timings`
- `--voice-mode local`
- `--voice-model`
- `--theme-file`

## Quick Start

```bash
source .venv/bin/activate

dsa-anim validate examples/archived/llm_inference.json
dsa-anim render examples/algorithms/bubble_sort.json -o output.mp4
dsa-anim preview examples/demos/bubble_sort_demo.json --serve
dsa-anim audit examples/explainers/agentic_debug_agent_explainer.json
dsa-anim schema
dsa-anim theme-schema
dsa-anim validate-theme examples/themes/nvidia.json
```

## Audio Workflow

`dsa-anim` still supports provider-agnostic external audio, and now also has a built-in local Sherpa path for offline narration.

- `--audio` muxes an existing audio file onto a rendered video.
- `--audio-timings` retimes scenes from a JSON sidecar.
- `--voice-mode local` synthesizes narration per scene with Sherpa, retimes the animation from the generated clip lengths, and muxes the result automatically.
- `--theme-file` overrides the document theme with an external JSON theme preset.

Example:

```bash
source .venv/bin/activate

dsa-anim render \
  examples/explainers/agentic_debug_agent_explainer.json \
  -o artifacts/videos/explainers/agentic_debug_agent_explainer_voice_local.mp4 \
  --audio artifacts/audio/explainers/agentic_debug_agent_explainer_local_tts.m4a \
  --audio-timings artifacts/audio/explainers/agentic_debug_agent_explainer_local_tts_timings.json
```

Local Sherpa example:

```bash
source .venv/bin/activate
python -m pip install -e '.[local-voice]'

dsa-anim render \
  examples/demos/agentic_triage.json \
  -o artifacts/videos/nvidia_agentic_triage_sherpa.mp4 \
  --theme-file examples/themes/nvidia.json \
  --voice-mode local \
  --voice-model /path/to/sherpa-model-dir \
  --voice-artifacts-dir artifacts/audio/agentic_triage_sherpa
```

### Local Voice Setup

Install the local voice extra:

```bash
source .venv/bin/activate
python -m pip install -e '.[local-voice]'
```

Use a Sherpa model bundle directory, not just a loose `.onnx` file, so the CLI can discover the companion assets automatically. The current implementation was verified with `vits-piper-en_US-lessac-medium`.

At render time, the CLI will:

- use the standalone `sherpa-onnx-offline-tts` binary when it is available
- otherwise fall back to the installed `sherpa_onnx` Python API, which is the path currently used on this macOS setup
- synthesize one narration clip per scene
- pad each scene slightly so visual beats can settle
- retime the document from the generated scene durations
- mux the combined WAV onto the final video

Current timing behavior for local voice is duration-aware, not word-timestamp-aware:

- scene durations come from the generated Sherpa clips
- local emphasis still uses the existing narration-clause inference unless you provide a richer `--audio-timings` sidecar yourself

The local voice flow looks for these assets automatically beside the selected model when you do not pass explicit overrides:

- `tokens.txt`
- `espeak-ng-data/`
- optional `lexicon.txt`

You can also configure them through environment variables:

- `DSA_ANIM_SHERPA_MODEL`
- `DSA_ANIM_SHERPA_TOKENS`
- `DSA_ANIM_SHERPA_DATA_DIR`
- `DSA_ANIM_SHERPA_LEXICON`
- `DSA_ANIM_SHERPA_RULE_FSTS`
- `DSA_ANIM_SHERPA_SPEAKER`
- `DSA_ANIM_SHERPA_SPEED`
- `DSA_ANIM_SHERPA_PAD`
- `DSA_ANIM_SHERPA_BIN`

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

## External Themes

You can override a document's built-in theme name with an external JSON theme file:

```bash
source .venv/bin/activate

dsa-anim validate examples/demos/bubble_sort_demo.json --theme-file examples/themes/nvidia.json
dsa-anim render examples/demos/bubble_sort_demo.json -o output.png --theme-file examples/themes/nvidia.json
dsa-anim preview examples/demos/bubble_sort_demo.json --theme-file examples/themes/nvidia.json
```

Use `dsa-anim theme-schema` to generate the JSON Schema for theme files, and `dsa-anim validate-theme` to validate one directly.

## Title Opener

Use `template: "title-opener"` for a real title card instead of hand-authoring an awkward fake intro scene.

Default behavior for a title opener:

- hides persistent document-level chrome unless you explicitly opt back in
- suppresses the top progress bar
- upgrades heading text to a larger display style
- centers title and supporting copy into a calmer opener layout

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
