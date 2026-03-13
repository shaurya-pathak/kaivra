# DSA Explainer Todo

Follow-up list for the architecture explainer, the DSA engine, and the voice-synced render pipeline.

## Immediate Quality Fixes

- [ ] Prevent all component overlap before render time.
- [ ] Add a layout collision pass that flags overlaps with object IDs and scene names.
- [ ] Investigate why scene timing is drifting far away from the narration timing in the explainer render.
- [ ] Verify whether the audio-aware duration override is actually being applied per scene and per animation envelope.
- [ ] Add a sync regression test that checks scene duration, glow timing, and voice timing stay aligned.
- [ ] Slow down continuity transitions between scenes so the relaxed pacing carries through the full video.
- [ ] Tune continuity easing and default continuity duration for long-form narrated explainers.

## Motion And Typography

- [ ] Stop text from resizing while parent bubbles or cards scale.
- [ ] Decouple font size from box scale so only the outer shape breathes.
- [ ] Add a stable "scale shell, not text" animation mode for boxes and tokens.
- [ ] Smooth out the "bubbling" effect so cards settle instead of constantly re-rendering visually.
- [ ] Add more follow-through on enlarging and shrinking emphasized elements.
- [ ] Ensure every glow has time to ramp down before the next major motion starts.
- [ ] Add a general "relaxed pacing" profile that lengthens settle times, glow release, and scene continuity automatically.

## Carousel Improvements

- [ ] Make the carousel actually move horizontally when the active chapter changes.
- [ ] Keep the active chapter centered and clearly larger than neighboring chapters.
- [ ] Animate the incoming next chapter into place instead of only changing the highlight.
- [ ] Add peeking neighbors, depth, and velocity easing so the carousel feels like a real track.
- [ ] Let chapter transitions inherit narration timing so chapter movement lands with the voice.

## Architecture Demo Upgrades

- [ ] Show one semantic object traveling through the system: prompt -> JSON -> scene graph -> layout -> timeline -> renderer -> output.
- [ ] Add a true handoff animation where text becomes JSON, JSON becomes a graph, and the graph becomes output artifacts.
- [ ] Add richer intermediate representations so the architecture feels transformed, not just relabeled.
- [ ] Make the "direct video" failure case visually louder with explicit drift, jump, and inconsistency cues.
- [ ] Add a clearer contrast between "native language of the LLM" and "demands of visual media."
- [ ] Turn the final scene into a stronger thesis shot that summarizes why software beats direct frame generation.

## DSL And Engine Features

- [ ] Add first-class morph and handoff primitives for object-to-object transformation across scenes.
- [ ] Add narration-aware animation scheduling so key moments can snap to word timestamps or phrase timestamps.
- [ ] Expose pacing presets in the DSL: `tight`, `balanced`, `relaxed`, `cinematic`.
- [ ] Add scene-safe zones and composition guides so important content does not sit too high or leave awkward dead space.
- [ ] Add per-scene "do not scale text" and "keep object bounds stable" controls.
- [ ] Add a carousel layout mode with built-in active-center behavior rather than faking it with static tokens.
- [ ] Add a persistent object trail mode for showing a single entity moving through a multi-step pipeline.

## Tooling And QA

- [ ] Build a render audit that checks for overlaps, clipped text, excessive empty space, and unreadable labels.
- [ ] Add frame sampling tools that generate scene thumbnails automatically after render.
- [ ] Add a timeline debug view that overlays scene boundaries, animation ranges, and narration timing.
- [ ] Add a "voice sync preview" that shows audio waveform plus animation beats before the full render.
- [ ] Add snapshot tests for continuity so shared objects land in the exact same place across scene boundaries.
- [ ] Add typography stability tests so scaling changes do not cause text jitter or reflow.

## Authoring Workflow

- [ ] Make it easier for the LLM to produce polished long-form explainers without hand-tuning every scene.
- [ ] Add authoring templates for architecture demos, pipeline demos, and before/after comparisons.
- [ ] Teach the DSL generator to use persistent IDs aggressively when scenes are meant to feel continuous.
- [ ] Add a higher-level "story beat" layer so narration, chapter changes, and visual beats are authored together.
- [ ] Build a default demo checklist that runs before export: pacing, overlap, sync, carousel, continuity, and final thesis shot.
