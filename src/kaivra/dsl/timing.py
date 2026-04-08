"""Shared timing config discovery and semantic timing helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaivra.dsl.schema import parse_duration

DEFAULT_TIMING_CONFIG_FILE = "kaivra.config.json"
_PROJECT_ROOT_MARKERS = (".git", "pyproject.toml")
_DURATION_LITERAL_UNITS = ("s", "ms")


@dataclass(frozen=True)
class TimingConfig:
    """Resolved timing policy loaded from repo config plus defaults."""

    gap_tokens: dict[str, str]
    duration_tokens: dict[str, str]
    action_durations: dict[str, str]
    tail_padding: str


DEFAULT_TIMING_CONFIG = TimingConfig(
    gap_tokens={
        "none": "0s",
        "short": "0.4s",
        "medium": "0.8s",
        "long": "1.2s",
    },
    duration_tokens={
        "instant": "0s",
        "short": "0.4s",
        "medium": "0.8s",
        "long": "1.2s",
    },
    action_durations={
        "appear": "0s",
        "disappear": "0s",
        "fade-in": "0.5s",
        "fade-out": "0.5s",
        "move": "0.8s",
        "move-to": "0.8s",
        "swap": "0.8s",
        "scale": "0.7s",
        "draw": "0.9s",
        "type": "1.0s",
        "highlight": "1.0s",
        "pulse": "1.0s",
        "build": "1.0s",
        "replace": "0.7s",
    },
    tail_padding="0.8s",
)


def find_timing_config_path(
    document_path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> Path | None:
    """Locate the nearest repo-level timing config for a document."""
    path = Path(document_path).expanduser().resolve()
    search_start = path if path.is_dir() else path.parent
    project_root = _find_project_root(search_start)

    for parent in (search_start, *search_start.parents):
        candidate = parent / DEFAULT_TIMING_CONFIG_FILE
        if candidate.is_file():
            return candidate
        if project_root is not None and parent == project_root:
            break

    if cwd is not None:
        fallback = Path(cwd).expanduser().resolve() / DEFAULT_TIMING_CONFIG_FILE
        if fallback.is_file():
            return fallback
    return None


def _find_project_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if any((parent / marker).exists() for marker in _PROJECT_ROOT_MARKERS):
            return parent
    return None


def load_timing_config(path: str | Path | None = None) -> TimingConfig:
    """Load timing config from disk, merging onto built-in defaults."""
    if path is None:
        return DEFAULT_TIMING_CONFIG

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Timing config must be a JSON object.")

    timing = raw.get("timing", raw)
    if not isinstance(timing, dict):
        raise ValueError("Timing config 'timing' section must be a JSON object.")

    return TimingConfig(
        gap_tokens=_merge_string_map(DEFAULT_TIMING_CONFIG.gap_tokens, timing.get("gaps"), "gaps"),
        duration_tokens=_merge_string_map(
            DEFAULT_TIMING_CONFIG.duration_tokens,
            timing.get("durations"),
            "durations",
        ),
        action_durations=_merge_string_map(
            DEFAULT_TIMING_CONFIG.action_durations,
            timing.get("action_durations"),
            "action_durations",
        ),
        tail_padding=_resolve_string_value(
            timing.get("tail_padding", DEFAULT_TIMING_CONFIG.tail_padding),
            field="tail_padding",
        ),
    )


def resolve_timing_config(
    document_path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> TimingConfig:
    """Load the nearest timing config for a document, or built-in defaults."""
    return load_timing_config(find_timing_config_path(document_path, cwd=cwd))


def is_duration_literal(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped == "auto" or stripped.endswith(_DURATION_LITERAL_UNITS)


def resolve_duration_value(
    value: str | None,
    *,
    config: TimingConfig,
    field: str,
    tokens: dict[str, str] | None = None,
    fallback: str | None = None,
) -> float:
    """Resolve an absolute duration literal or semantic token into seconds."""
    candidate = (value or fallback or "").strip()
    if not candidate:
        raise ValueError(f"{field} requires a duration value.")
    if is_duration_literal(candidate):
        return parse_duration(candidate)

    token_sets = [tokens or {}, config.duration_tokens, config.gap_tokens]
    for token_map in token_sets:
        resolved = token_map.get(candidate)
        if resolved:
            return parse_duration(resolved)

    raise ValueError(f"Unknown timing token {candidate!r} for {field}.")


def merge_timing_config(base: TimingConfig | None) -> TimingConfig:
    """Return a usable config object, defaulting to built-in values."""
    return base or DEFAULT_TIMING_CONFIG


def _merge_string_map(
    base: dict[str, str],
    raw: Any,
    field: str,
) -> dict[str, str]:
    if raw is None:
        return dict(base)
    if not isinstance(raw, dict):
        raise ValueError(f"Timing config field {field!r} must be an object.")

    merged = dict(base)
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"Timing config field {field!r} must use non-empty string keys.")
        merged[key.strip()] = _resolve_string_value(value, field=f"{field}.{key}")
    return merged


def _resolve_string_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Timing config field {field!r} must be a non-empty string.")
    return value.strip()
