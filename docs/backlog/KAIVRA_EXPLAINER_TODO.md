# Kaivra Explainer Todo

Follow-up list for the architecture explainer, the Kaivra engine, and the audio-timed render pipeline.

## Completed Recently

- [x] Add external-audio retiming support so authored scene animations can be retimed from supplied scene durations and cue windows before render.
- [x] Add a reusable scene retimer in `kaivra` so scene durations, focus timing, camera timing, and motion envelopes can scale with external timing metadata.
- [x] Validate that a retimed document still parses cleanly through the DSL.
- [x] Stop box/token text from scaling with the shell by default so emphasis pulses do not cause font bubbling.
- [x] Add an object-level `scale_text` control so authored demos can opt back into text scaling when they actually want it.
- [x] Make carousel layouts infer the active chapter from scene emphasis and move the rail so the active item lands in center.
- [x] Add a first-pass `kaivra audit` command that samples scenes and reports overlap/clipping issues before export.
- [x] Add carousel peeking behavior plus springier continuity motion for chapter rails.
- [x] Add CLI-level `--audio` muxing and generic `--audio-timings` retiming support to `kaivra render`.

## Current Priorities

- [ ] P1: Add cue-aware animation scheduling that can snap beats to explicit word or phrase timestamps from a timing sidecar.
- [ ] P1: Add a relaxed pacing profile that slows settle time, glow release, and continuity by default.
- [ ] P1: Add a handoff/morph primitive for pipeline demos and architecture explainers.
- [ ] P1: Turn carousel clipping audits into layout-aware guidance with suggested fixes instead of raw warnings.
- [ ] P1: Add stronger depth and velocity styling so carousel motion feels more premium than simply shifted and scaled.

## Immediate Quality Fixes

- [ ] Prevent all component overlap before render time.
- [ ] Add a layout collision pass that flags overlaps with object IDs and scene names.
- [ ] Investigate remaining cases where scene timing can still drift from supplied cue timing after sidecar-based retiming.
- [ ] Extend audio-aware retiming beyond scene envelopes so authored beats can optionally snap to exact cue or word timestamps from the sidecar.
- [ ] Add a sync regression test that checks scene duration, glow timing, and cue timing stay aligned.
- [ ] Slow down continuity transitions between scenes so the relaxed pacing carries through the full video.
- [ ] Tune continuity easing and default continuity duration for long-form explainers with attached audio.

## Motion And Typography

- [x] Stop text from resizing while parent bubbles or cards scale.
- [x] Decouple font size from box scale so only the outer shape breathes.
- [x] Add a stable "scale shell, not text" animation mode for boxes and tokens.
- [ ] Smooth out the "bubbling" effect so cards settle instead of constantly re-rendering visually.
- [ ] Add more follow-through on enlarging and shrinking emphasized elements.
- [ ] Ensure every glow has time to ramp down before the next major motion starts.
- [ ] Add a general "relaxed pacing" profile that lengthens settle times, glow release, and scene continuity automatically.

## Carousel Improvements

- [x] Make the carousel actually move horizontally when the active chapter changes.
- [x] Keep the active chapter centered while the rail shifts scene to scene.
- [x] Animate the incoming next chapter into place instead of only changing the highlight.
- [x] Add peeking neighbors and springier velocity so the carousel feels more like a track.
- [ ] Let chapter transitions inherit explicit cue timing so chapter movement lands with the supplied audio.

## Architecture Demo Upgrades

- [ ] Show one semantic object traveling through the system: prompt -> JSON -> scene graph -> layout -> timeline -> renderer -> output.
- [ ] Add a true handoff animation where text becomes JSON, JSON becomes a graph, and the graph becomes output artifacts.
- [ ] Add richer intermediate representations so the architecture feels transformed, not just relabeled.
- [ ] Make the "direct video" failure case visually louder with explicit drift, jump, and inconsistency cues.
- [ ] Add a clearer contrast between "native language of the LLM" and "demands of visual media."
- [ ] Turn the final scene into a stronger thesis shot that summarizes why software beats direct frame generation.

## DSL And Engine Features

- [ ] Add first-class morph and handoff primitives for object-to-object transformation across scenes.
- [ ] Add timestamp-aware animation scheduling so key moments can snap to explicit word or phrase timestamps.
- [ ] Expose pacing presets in the DSL: `tight`, `balanced`, `relaxed`, `cinematic`.
- [ ] Add scene-safe zones and composition guides so important content does not sit too high or leave awkward dead space.
- [ ] Add per-scene "do not scale text" and "keep object bounds stable" controls.
- [ ] Add a carousel layout mode with built-in active-center behavior rather than faking it with static tokens.
- [ ] Add a persistent object trail mode for showing a single entity moving through a multi-step pipeline.

## Tooling And QA

- [x] Build a render audit that checks for overlaps and clipped elements before export.
- [ ] Extend the render audit to cover excessive empty space and unreadable labels.
- [ ] Add frame sampling tools that generate scene thumbnails automatically after render.
- [ ] Add a timeline debug view that overlays scene boundaries, animation ranges, and supplied audio timing.
- [ ] Add an "audio sync preview" that shows audio waveform plus animation beats before the full render.
- [ ] Add snapshot tests for continuity so shared objects land in the exact same place across scene boundaries.
- [ ] Add typography stability tests so scaling changes do not cause text jitter or reflow.

## Authoring Workflow

- [ ] Make it easier for the LLM to produce polished long-form explainers without hand-tuning every scene.
- [ ] Add authoring templates for architecture demos, pipeline demos, and before/after comparisons.
- [ ] Teach the DSL generator to use persistent IDs aggressively when scenes are meant to feel continuous.
- [ ] Add a higher-level "story beat" layer so captions, chapter changes, and visual beats are authored together.
- [ ] Build a default demo checklist that runs before export: pacing, overlap, sync, carousel, continuity, and final thesis shot.
