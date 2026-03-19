# Kaivra LLM Polish Cleanup Plan

## Summary

Kaivra is in good shape functionally, but there are still a few traces of LLM-generated roughness in the docs and product copy. This is not a correctness plan. It is a polish pass for places where the repository feels a little too repetitive, over-explained, or mechanically phrased.

## What Still Feels Slightly Sloppy

### 1. README duplication and density

- The first-run story is now correct, but the README repeats setup guidance across `First-Time Setup`, `MCP Setup`, `Quick Smoke Test`, and `Audio`.
- Some sections explain the same idea twice with slightly different wording.
- The narrated and silent first-run flows are useful, but the page could be made easier to scan by tightening repeated explanation text.

### 2. Error-message tone and consistency

- Some CLI and provider errors are very polished and actionable.
- Others still read like internal implementation errors instead of user-facing guidance.
- We should make all first-run failures sound like one coherent product voice.

### 3. MCP resource copy is strong but still a bit verbose

- The authoring profile and pattern catalog are much better than before, but some bullets still feel padded.
- A shorter, sharper version would likely guide models just as well while reducing prompt noise.

### 4. Backlog and docs naming drift

- There is still some overlap between "first-run ergonomics", "discovery cleanups", and the new UX polish changes.
- A future cleanup pass should prune or merge backlog plans that now describe already-landed work.

### 5. Test naming and intent clarity

- The smoke coverage is good, but some test names now mix "smoke", "first-run", and "integration" language somewhat loosely.
- A small rename pass would make it easier to understand which tests are true end-to-end confidence checks versus focused regression tests.

## Suggested Cleanup Work

### 1. Tighten README without changing behavior

- Rewrite the README to keep one canonical bootstrap path and one short narrated path.
- Remove repeated explanation text when the same command already appears earlier.
- Keep the examples, but bias for scanability over completeness.

### 2. Standardize user-facing failure text

- Review CLI exceptions for install, provider discovery, file resolution, and preflight failures.
- Normalize them around one voice: concise, specific, and immediately actionable.
- Avoid wording that sounds like an internal stack trace unless the user truly needs debugging detail.

### 3. Trim prompt-resource copy

- Shorten the MCP authoring profile and pattern descriptions where they repeat guidance.
- Keep the strongest wording about visual explainers, narration pacing, and connector usage.
- Remove filler sentences that do not materially change model behavior.

### 4. Reconcile backlog docs

- Mark already-landed items in older backlog plans.
- Merge tiny overlap plans where they no longer justify separate files.
- Keep the backlog focused on open work instead of a mix of shipped and unshipped ideas.

### 5. Clarify test tiers

- Rename or regroup tests so "smoke", "workflow", and "unit" meaning is obvious.
- Keep true smoke tests minimal and representative.
- Push narrower behavioral assertions into more specific test modules when helpful.

## Acceptance Criteria

- README reads like a deliberate human onboarding doc rather than an accretion of correct notes.
- User-facing errors feel consistent across voice, render, doctor, and MCP-install flows.
- MCP guidance remains strong while using fewer words.
- Backlog files more clearly reflect what is still open.

## Priority

- Low.
- Do this only after user-facing workflow gaps or substantive rendering issues are addressed.
- Treat it as product polish, not blocker work.
