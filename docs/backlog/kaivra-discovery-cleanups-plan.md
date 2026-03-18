# Kaivra Discovery Cleanups Plan

## Summary

Close the remaining naming, API, and consistency gaps surfaced during the UX review. These fixes are smaller than the main workflow plans, but they remove footguns that make the tool feel unfinished. This plan is the place for compatibility-minded cleanup work that does not justify its own larger initiative.

## Implementation Changes

### 1. Narration naming and behavior

- Introduce `show_subtitles` as the clearer public name for rendering narration text on screen.
- Keep `show_narration` as a backward-compatible alias for at least one minor release.
- When voice rendering is enabled and the user does not explicitly set the field, default subtitles off.
- Update docs and resource text to describe the field as subtitle rendering, not audio generation.

### 2. Theme-resolution parity

- Use one shared theme-search-root resolver in CLI and MCP.
- For CLI flows, search `themes/` from the nearest ancestor workspace plus `cwd/themes`.
- Ensure `render`, `sample`, `audit`, and any future quick-render path all use the same theme-resolution helper.

### 3. Theme registration ergonomics

- Expand `register_theme` so it accepts either a `ThemeSpec` or `name + data` input.
- Keep the existing `ThemeSpec` call signature working.
- Document `load_theme_file` and the new helper together so callers understand which surface to use.

### 4. Audio concat and format cleanup

- Remove any remaining code paths that name concatenated WAV assets as `.mp3`.
- Ensure concat and mux helpers use extensions that match the actual intermediate format.
- Add regression coverage so format naming bugs do not return.

### 5. Remaining layout and install cleanup

- Fix any lingering starter-layout semantics where content is described as `stack` but behaves as `flow`, or the reverse.
- Update root-level docs so voice installation and provider discovery are called out explicitly.
- Keep this plan focused on cleanup and compatibility, not new product surfaces already owned by the other backlog plans.

## Acceptance Criteria

- Users can use `show_subtitles` immediately without breaking older documents that still use `show_narration`.
- Custom themes resolve the same way in CLI and MCP for the same workspace.
- The theme-registration API feels discoverable and no longer nudges users into the wrong helper.
- Intermediate narration audio files use correct formats and mux cleanly.

## Test Plan

### Automated

- Add schema and parser tests for `show_subtitles` plus backward-compatible `show_narration`.
- Add regression tests for custom theme lookup in both CLI and MCP flows.
- Add unit tests for the overloaded `register_theme` helper.
- Add audio-format regression tests covering concat extension naming and mux success.

### Manual

- Render one document using `show_subtitles` and one using the old field and confirm equivalent on-screen behavior.
- Load the same custom theme through CLI and MCP and confirm both resolve it.
- Exercise a narrated render path and confirm the intermediate-format cleanup does not change final output behavior.

## Dependencies And Sequence

- Land last so it can absorb smaller cleanup tasks discovered while shipping the larger plans.
- Pull any item out into another plan only if it grows into a user-visible feature rather than a compatibility cleanup.

## Assumptions And Defaults

- `show_subtitles` becomes the preferred field name, but `show_narration` remains accepted for compatibility.
- Theme registration stays JSON-first; the new helper only makes the API more ergonomic.
- This plan should stay small and surgical compared with the other workflow plans.
