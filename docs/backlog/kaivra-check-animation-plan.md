# Kaivra Check Animation Plan

## Summary

Expand `check_animation` from a parser-plus-layout audit into a richer preflight pass that can catch pacing problems, redundant narration, broken references, and likely repair actions before the user wastes time on a full render. The goal is to keep the current fast feedback loop while making the output more actionable.

## Implementation Changes

### 1. Public surface

- Preserve the existing top-level response shape, but enrich `warnings`, `blocking_issues`, and `recommended_edits`.
- Change `recommended_edits` from plain strings to structured objects with this schema:
  - `scene_id: str | null`
  - `action: str`
  - `object_id: str | null`
  - `field: str | null`
  - `suggested_value: str | int | float | bool | null`
  - `reason: str`
- Keep backward compatibility by accepting old string lists in any code path that reads historical artifacts, but return structured objects from the new implementation.

### 2. Duration and narration checks

- Warn when a scene is shorter than 4 seconds or longer than 20 seconds.
- When a scene has narration text, estimate read time at 150 words per minute and warn if the narration is materially longer than the scene duration.
- When `show_narration` or its eventual subtitle alias is enabled and on-screen body text substantially duplicates narration, warn about redundancy instead of blocking.

### 3. Reference validation

- For every connector, verify `from` and `to` resolve to scene-local or document-level object IDs that exist.
- For every animation target, verify the target ID or target list resolves to in-scope objects.
- Treat missing connector and animation targets as blocking issues because the resulting render is visibly broken or misleading.

### 4. Structured fix suggestions

- Emit targeted edits for each detected issue, such as `remove_object`, `shorten_text`, `retime_scene`, `replace_target`, or `fix_connector_endpoint`.
- Include the scene ID and object ID whenever possible so agents or users can patch the document deterministically.
- Keep the current generic recommendation logic only as a fallback when a specific structured edit cannot be derived.

## Acceptance Criteria

- `check_animation` reports pacing and narration mismatches before render.
- Broken connector or animation targets surface as blocking issues with specific repair suggestions.
- Recommended edits are machine-usable enough for a follow-up agent step or deterministic UI.
- Existing callers that only inspect `valid`, `summary`, and `audit_findings` keep working.

## Test Plan

### Automated

- Add tests for too-short and too-long scenes.
- Add tests for narration-read-time warnings against scene duration.
- Add tests for redundant narration and body text.
- Add tests for invalid connector endpoints and invalid animation targets.
- Add tests confirming `recommended_edits` returns structured objects with the expected fields.

### Manual

- Run `check_animation` on a deliberately broken sample and confirm the output identifies the exact scene and object to fix.
- Run `check_animation` on a narrated explainer with repeated on-screen copy and confirm the warning is non-blocking but clear.
- Confirm a clean starter document still returns a short, low-noise success response.

## Dependencies And Sequence

- Land after the first visual and pacing improvements so the new warnings match the intended authoring model.
- Coordinate with the cleanup plan if `show_narration` is renamed or aliased.

## Assumptions And Defaults

- Read-time estimation uses 150 words per minute and errs on the side of warning, not blocking.
- Missing connector or animation targets are blocking errors.
- Layout overlap and clipping remain part of the check; this plan extends rather than replaces the current audit.
