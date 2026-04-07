"""Kaivra version constants — single source of truth for DSL and server versions."""

from __future__ import annotations

# Bump this when the DSL schema changes in ways LLMs should know about.
CURRENT_DSL_VERSION = "1.3"

# Short changelog an LLM can scan to understand what changed.
# Keep entries terse — this may be injected into tool responses.
DSL_CHANGELOG: list[tuple[str, str]] = [
    (
        "1.3",
        "Changed: relative motion translations replace pixel offsets, and the unused "
        "absolute layout mode was removed.",
    ),
    (
        "1.2",
        "Added: plan_animation questionnaire guidance, spoken_forms aliases, "
        "provider-aware voice sync diagnostics, scene voice lead-in, "
        "and invisible parent group audit in check_animation.",
    ),
    (
        "1.1",
        "Added: carousel object type, one-column scene template, "
        "persistent document-level objects, show_subtitles flag, "
        "narration field on scenes, pacing presets (quick-demo / balanced / educational), "
        "continuity morphs via reused object IDs across scenes.",
    ),
    ("1.0", "Initial schema."),
]


def version_drift_warning(doc_version: str) -> str | None:
    """Return a warning string if *doc_version* is behind CURRENT_DSL_VERSION, else None."""
    if doc_version == CURRENT_DSL_VERSION:
        return None
    current_entry = next((msg for ver, msg in DSL_CHANGELOG if ver == CURRENT_DSL_VERSION), None)
    return (
        f"This document targets schema {doc_version!r}, but the current version is "
        f"{CURRENT_DSL_VERSION!r}. {current_entry or ''} "
        f'Update the "version" field to "{CURRENT_DSL_VERSION}" and use the newer features.'
    )
