"""Workspace operations shared by the Kaivra MCP server and CLI."""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

from kaivra.audio.base import validate_voice_provider_setup
from kaivra.dsl.parser import parse_file, parse_string
from kaivra.dsl.retime import (
    EMPHASIS_ACTIONS,
    REVEAL_ACTIONS,
    _build_content_index,
    _semantic_score,
    estimate_scene_duration,
)
from kaivra.dsl.schema import ObjectType, parse_duration
from kaivra.mcp.blueprints import (
    dump_document_json,
    infer_slug,
)
from kaivra.qa.audit import audit_scene_graph
from kaivra.render.cairo_renderer import CairoRenderer
from kaivra.render.orchestration import (
    build_render_graph,
    render_document_artifact,
    resolve_document_timing_config,
    resolve_theme_search_roots,
)
from kaivra.render.web.exporter import write_web_preview
from kaivra.themes.registry import (
    get_theme,
    theme_field_names,
    theme_from_dict,
    write_theme_file,
)
from kaivra.version import version_drift_warning

ProgressReporter = Callable[[float, str], None]
_READ_TIME_WORDS_PER_MINUTE = 150
_MIN_SCENE_DURATION_SECONDS = 4.0
_MAX_SCENE_DURATION_SECONDS = 20.0
_NARRATION_OVERAGE_SECONDS = 0.8
_NARRATION_OVERAGE_RATIO = 1.15
_REDUNDANCY_WORD_THRESHOLD = 6
_REDUNDANCY_TOKEN_OVERLAP = 0.72
_REDUNDANCY_SEQUENCE_SIMILARITY = 0.78
_EXPLANATION_MIN_WORDS = 12
_DOUBLE_REVEAL_OVERLAP_SECONDS = 0.12
_DOUBLE_REVEAL_HOLD_WINDOW_SECONDS = 0.15
_EXPLANATION_MARKERS = (
    "because",
    "so that",
    "so we can",
    "so the",
    "this means",
    "that means",
    "which means",
    "the result is",
    "result is",
    "instead of",
    "whether to",
    "lets us",
    "let's us",
    "allows",
    "helps",
    "matters",
    "purpose",
    "used to",
    "turns",
    "controls",
    "keeps",
    "prevents",
    "avoid",
    "convert",
    "compress",
    "pool",
    "why",
)
_MECHANICAL_SCENE_MARKERS = (
    "weight",
    "weights",
    "bias",
    "relu",
    "sigmoid",
    "logit",
    "activation",
    "weighted sum",
    "multiply",
    "multiplied",
    "probability",
    "pre-activation",
)
_COMMON_HEADING_IDS = {"title", "subtitle", "heading", "scene_title", "scene_heading"}
_LAYPERSON_JARGON = {
    "api",
    "backend",
    "daemon",
    "endpoint",
    "fixture",
    "harness",
    "payload",
    "port",
    "queue",
    "remediation",
    "repo",
    "service",
    "stack trace",
    "test harness",
    "triage",
}

DEFAULT_LOCAL_MODEL_NAME = "vits-piper-en_US-amy-low"
DEFAULT_LOCAL_MODEL_DIR = Path.home() / ".kaivra" / "models" / DEFAULT_LOCAL_MODEL_NAME

_MODEL_ARCHIVES = {
    DEFAULT_LOCAL_MODEL_NAME: {
        "archive_url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
            "vits-piper-en_US-amy-low.tar.bz2"
        ),
        "expected_model_name": "en_US-amy-low.onnx",
    }
}

_DEFAULT_CLAUDE_CONFIG_PATH = Path.home() / ".claude.json"
_DEFAULT_CURSOR_CONFIG_PATH = Path.home() / ".cursor" / "mcp.json"
_DOCTOR_HINT_FILE_ENV = "KAIVRA_DOCTOR_HINT_FILE"
_DEFAULT_DOCTOR_HINT_PATH = Path.home() / ".kaivra" / ".doctor_hint_seen"


@dataclass(frozen=True)
class RecommendedEdit:
    scene_id: str | None
    action: str
    object_id: str | None
    field: str | None
    suggested_value: str | int | float | bool | None
    reason: str

    def to_dict(self) -> dict[str, str | int | float | bool | None]:
        return {
            "scene_id": self.scene_id,
            "action": self.action,
            "object_id": self.object_id,
            "field": self.field,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CheckFinding:
    severity: str
    scene_id: str | None
    kind: str
    message: str
    recommended_edit: RecommendedEdit | None = None

    def to_message(self) -> str:
        location = self.scene_id or "document"
        return f"{self.severity.upper()} {location} {self.kind}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "scene_id": self.scene_id,
            "kind": self.kind,
            "category": _finding_category(self),
            "message": self.message,
            "recommended_edit": self.recommended_edit.to_dict() if self.recommended_edit else None,
        }


@dataclass(frozen=True)
class ObjectRef:
    object_id: str | None
    path: str
    spec: Any


@dataclass(frozen=True)
class RevealEvent:
    object_id: str
    action: str
    start_seconds: float
    duration_seconds: float
    animation_index: int

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + max(self.duration_seconds, 0.001)


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved output locations for the local MCP workflow."""

    root: Path
    animations_dir: Path
    themes_dir: Path
    previews_dir: Path
    renders_dir: Path


class KaivraWorkspace:
    """File-system aware operations for the local MCP workflow."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or Path.cwd()).resolve()
        self.paths = WorkspacePaths(
            root=self.root,
            animations_dir=self.root / "animations",
            themes_dir=self.root / "themes",
            previews_dir=self.root / "artifacts" / "previews",
            renders_dir=self.root / "artifacts" / "renders",
        )

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a possibly relative path against the workspace root."""
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self.root / candidate).resolve()

    def plan_animation(
        self,
        *,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Return a structured questionnaire for the LLM to present to the user
        before creating an animation JSON document."""
        return {
            "status": "ok",
            "topic": topic,
            "instructions": (
                "Present these questions conversationally to the user.  "
                "Collect their answers, then use them to author the animation "
                "JSON directly.  Skip questions the user has already answered "
                "or that are not relevant.  Default narrated explainers to a "
                "process_explainer shape unless the user clearly wants another pattern.  "
                "Write narration in clear spoken English that explains the process in user-facing terms.  "
                "If the user chooses a voice mode, "
                "explicitly remind them to mirror on-screen keywords in the narration "
                "so reveals can line up cleanly."
            ),
            "suggested_meta": {
                "title": topic or "Untitled Animation",
                "theme": "modern",
                "pacing": "balanced",
                "audience": "mixed",
                "continuity": True,
                "show_subtitles": False,
            },
            "draft_defaults": {
                "audience": "mixed",
                "detail_level": "educational",
                "voice_mode": "captions",
                "pattern": "process_explainer",
                "theme": "modern",
                "num_beats": "auto",
            },
            "questions": [
                {
                    "id": "topic",
                    "category": "content",
                    "question": "What topic or concept would you like to explain?",
                    "skip_if": topic is not None,
                    "maps_to": "title",
                },
                {
                    "id": "audience",
                    "category": "content",
                    "question": "Who is the audience level for this explainer?",
                    "options": [
                        {
                            "value": "layperson",
                            "label": "Layperson — minimize jargon and internal names",
                        },
                        {
                            "value": "mixed",
                            "label": "Mixed — clear and understandable first, with light technical detail only when it helps",
                        },
                        {
                            "value": "technical",
                            "label": "Technical — comfortable with precise terms and implementation details",
                        },
                    ],
                    "default": "mixed",
                    "maps_to": "meta.audience",
                },
                {
                    "id": "detail_level",
                    "category": "pacing",
                    "question": "How detailed should the animation be?",
                    "options": [
                        {
                            "value": "quick-demo",
                            "label": "Quick demo — short, punchy, minimal narration",
                        },
                        {
                            "value": "balanced",
                            "label": "Balanced — moderate detail, good for most topics",
                        },
                        {
                            "value": "educational",
                            "label": "Educational — thorough, step-by-step explanations",
                        },
                    ],
                    "default": "balanced",
                    "maps_to": "pacing",
                },
                {
                    "id": "voice_mode",
                    "category": "audio",
                    "question": "How should narration be delivered?",
                    "options": [
                        {
                            "value": "openai",
                            "label": "OpenAI voice — lower-cost AI narration (requires API key)",
                        },
                        {
                            "value": "elevenlabs",
                            "label": "ElevenLabs voice — high-quality AI narration (requires API key)",
                        },
                        {
                            "value": "local",
                            "label": "Local voice (Sherpa) — free offline TTS narration",
                        },
                        {"value": "captions", "label": "Captions only — text subtitles, no audio"},
                        {"value": "silent", "label": "Silent — no narration or captions"},
                    ],
                    "default": "captions",
                    "maps_to_resolved": {
                        "openai": {
                            "include_narration": True,
                            "show_subtitles": True,
                            "voice_provider": "openai",
                        },
                        "elevenlabs": {
                            "include_narration": True,
                            "show_subtitles": True,
                            "voice_provider": "elevenlabs",
                        },
                        "local": {
                            "include_narration": True,
                            "show_subtitles": True,
                            "voice_provider": "local",
                        },
                        "captions": {"include_narration": True, "show_subtitles": True},
                        "silent": {"include_narration": False, "show_subtitles": False},
                    },
                },
                {
                    "id": "pattern",
                    "category": "structure",
                    "question": "What kind of animation pattern fits best?",
                    "options": [
                        {
                            "value": "process_explainer",
                            "label": "Process explainer — why it matters, then state flow, then outcome",
                        },
                        {
                            "value": "visual_explainer",
                            "label": "Visual explainer — concept-first diagram with narrated beats",
                        },
                        {
                            "value": "algorithm_walkthrough",
                            "label": "Algorithm walkthrough — step-by-step code/data visualization",
                        },
                        {
                            "value": "architecture_explainer",
                            "label": "Architecture explainer — component map and data flow when system inventory is the goal",
                        },
                        {
                            "value": "before_after_comparison",
                            "label": "Before/after comparison — contrasting two approaches",
                        },
                    ],
                    "default": "process_explainer",
                    "maps_to": "pattern",
                },
                {
                    "id": "theme",
                    "category": "visual",
                    "question": "Which visual theme would you like?",
                    "options": [
                        {
                            "value": "modern",
                            "label": "Modern — clean light background with accent colors (default)",
                        },
                        {
                            "value": "material",
                            "label": "Material — Google Material Design inspired palette",
                        },
                        {
                            "value": "whiteboard",
                            "label": "Whiteboard — hand-drawn sketch aesthetic",
                        },
                    ],
                    "default": "modern",
                    "maps_to": "theme",
                },
                {
                    "id": "num_beats",
                    "category": "structure",
                    "question": "Roughly how many sections/beats should the animation have? (or let me decide based on the topic)",
                    "default": "auto",
                    "hint": "Typically 4-8 beats for a good explainer.",
                },
            ],
            "parameter_mapping": {
                "topic → title": "The topic becomes the animation title",
                "audience → meta.audience": "Use layperson, mixed, or technical to tune narration style",
                "detail_level → pacing": "Passed directly",
                "voice_mode": "Resolves to include_narration, show_subtitles, and optionally voice_provider",
                "pattern → pattern": "Passed directly",
                "theme → theme": "Passed directly",
                "num_beats": "If user specifies a number, generate that many beat outlines",
            },
            "persistent_state_guidance": [
                "Prefer document-level persistent objects whenever labels, legends, chapter rails, or shared state carry across scenes.",
                "Use continuity morphs for scene-local objects that evolve from one beat to the next.",
                "If a chapter tracker or repeated label appears in more than one scene, try to lift it into top-level objects first.",
            ],
            "agent_quickstart": [
                "If the user has already given enough direction, do not block on every question. Assume the draft defaults and start writing the JSON immediately.",
                "For narrated explainers, default to process_explainer: show why it matters, then visualize the state flow, then close with the outcome.",
                "Use template: one-column for straightforward explainers, then add groups for rows, columns, or connector neighborhoods.",
                "Prefer persistent document-level objects first when labels, chapter rails, legends, or shared state appear in multiple scenes.",
            ],
            "draft_outline": _planner_draft_outline(topic),
            "narration_assist": {
                "goal": "Write spoken English that names the same on-screen concepts in the same order as their reveals, and explain the process in plain user-facing language first.",
                "when_voice": [
                    "Use contractions and direct address instead of title-card prose.",
                    "Mirror object labels in narration so voice-sync checks can map words to targets.",
                    "For tricky names, add object.spoken_forms aliases before rendering.",
                    "Avoid spelling out filenames, modules, or repo paths in narration unless the user explicitly asked for implementation detail.",
                ],
                "layperson_guardrails": [
                    "Replace repo names, file paths, and code identifiers with plain-English descriptions.",
                    "Spell out why the problem matters before diving into the mechanism.",
                    "Prefer 'test runner' over 'harness', 'fix' over 'remediation', and 'queue gets stuck' over 'the daemon stalls'.",
                ],
            },
            "reference_examples": [
                {
                    "uri": "kaivra://example/perspectiv_medcase_process_explainer",
                    "why": "Shows the best current quality bar for a narrated process explainer with persistent state and dense topic-specific visuals.",
                    "excerpt": _reference_example_excerpt(
                        "perspectiv_medcase_process_explainer.json"
                    ),
                },
                {
                    "uri": "kaivra://example/api_how_it_works",
                    "why": "Shows the quality bar for a narrated process explainer with a clear why -> flow -> outcome arc.",
                    "excerpt": _reference_example_excerpt("api_how_it_works.json"),
                },
                {
                    "uri": "kaivra://example/forward_propagation",
                    "why": "Shows a deeper educational explainer with continuity carry-over.",
                    "excerpt": _reference_example_excerpt("forward_propagation.json"),
                },
            ],
            "notes": [
                {
                    "id": "voice_sync_tip",
                    "when": "voice_mode is 'openai' or 'elevenlabs' or 'local'",
                    "text": (
                        "Voice sync tip: use the same keywords in narration that appear "
                        "as on-screen object content or IDs. The engine matches spoken "
                        "words to animation targets semantically — saying 'the server "
                        "boots' will sync the reveal to an object with content 'Server'. "
                        "For tricky brand names or acronyms, add object.spoken_forms like "
                        "['co pilot', 'cobalt'] so checks and cue matching still recognize "
                        "the intended target. ElevenLabs uses word-level cues; OpenAI and "
                        "local (Sherpa) use scene-level timing with the same semantic checks."
                    ),
                },
                {
                    "id": "process_default_tip",
                    "when": "always",
                    "text": (
                        "Default to process_explainer for narrated work: start with the user-facing problem, "
                        "then visualize how state moves through the system, and close with the outcome or mental model."
                    ),
                },
                {
                    "id": "example_fetch_tip",
                    "when": "always",
                    "text": (
                        "If your MCP client only shows resource descriptors first, call resources/read "
                        "on kaivra://example/perspectiv_medcase_process_explainer or "
                        "kaivra://example/api_how_it_works to fetch the full JSON example body."
                    ),
                },
            ],
            "questionnaire": {
                "required_topics": [
                    "audience",
                    "detail_level",
                    "voice_mode",
                    "pattern",
                    "theme",
                ],
                "optional_topics": ["topic", "num_beats"],
            },
        }

    def add_theme(
        self,
        *,
        name: str,
        base_theme: str | None,
        overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Create or update a custom theme file inside the workspace."""
        chosen_name = infer_slug(name)
        if not chosen_name:
            raise ValueError("Theme names cannot be empty.")

        base = self._resolve_theme(base_theme or "modern")
        raw_theme = base.to_dict()
        raw_theme.update(overrides or {})
        raw_theme["name"] = chosen_name
        theme = theme_from_dict(raw_theme)

        self.paths.themes_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.paths.themes_dir / f"{chosen_name}.json"
        write_theme_file(theme, file_path)

        return {
            "theme_name": chosen_name,
            "file_path": str(file_path),
            "theme_json": json.dumps(theme.to_dict(), indent=2),
            "supported_fields": theme_field_names(),
            "next_step": (
                f"Use theme: {chosen_name} when authoring JSON directly, "
                f"or set meta.theme to {chosen_name} in an existing document."
            ),
        }

    def check_animation(
        self,
        *,
        file_path: str | None = None,
        dsl_json: str | None = None,
        write_back: bool = False,
        voice: bool = False,
        voice_provider: str | None = None,
    ) -> dict[str, Any]:
        """Validate and audit a Kaivra document from disk or raw JSON."""
        if file_path is None and dsl_json is None:
            raise ValueError("Provide either file_path or dsl_json.")

        try:
            doc, resolved_path = self._load_document(file_path=file_path, dsl_json=dsl_json)
        except Exception as exc:
            return {
                "valid": False,
                "summary": "Validation failed before Kaivra could build the document.",
                "blocking_issues": [str(exc)],
                "warnings": [],
                "audit_findings": [],
                "narration_timing": [],
                "normalized_dsl_json": None,
                "recommended_edits": _recommend_edits_from_messages([str(exc)]),
                "file_path": str(self.resolve_path(file_path)) if file_path else None,
            }

        try:
            theme_roots = self._theme_roots_for_document(resolved_path)
            timing_config = self._timing_config_for_document(resolved_path)
            raw_findings, findings, recommended_edits = _audit_document_report(
                doc,
                theme_search_roots=theme_roots,
                timing_config=timing_config,
                voice=voice,
                voice_provider=voice_provider,
            )
        except Exception as exc:
            return {
                "valid": False,
                "summary": "Kaivra could parse the document, but follow-up checks failed.",
                "blocking_issues": [str(exc)],
                "warnings": [],
                "audit_findings": [],
                "structured_findings": [],
                "finding_groups": {
                    "blocking": [],
                    "quality": [],
                    "voice_sync": [],
                    "continuity": [],
                },
                "narration_timing": [],
                "normalized_dsl_json": None,
                "recommended_edits": _recommend_edits_from_messages([str(exc)]),
                "applied_fixes": [],
                "file_path": str(resolved_path) if resolved_path else None,
            }

        narration_timing = _narration_timing_advice(doc)
        applied_fixes: list[dict[str, Any]] = []
        if write_back:
            if resolved_path is None:
                raise ValueError("write_back requires file_path.")
            doc, applied_fixes = _apply_safe_write_back_fixes(
                doc,
                raw_findings,
            )
            raw_findings, findings, recommended_edits = _audit_document_report(
                doc,
                theme_search_roots=theme_roots,
                timing_config=timing_config,
                voice=voice,
                voice_provider=voice_provider,
            )
            narration_timing = _narration_timing_advice(doc)

        normalized = dump_document_json(doc)
        blocking = [finding for finding in findings if finding.startswith("ERROR")]
        warnings = [finding for finding in findings if not finding.startswith("ERROR")]

        drift = version_drift_warning(doc.version)
        if drift:
            warnings.insert(0, f"VERSION: {drift}")

        if write_back:
            resolved_path.write_text(normalized + "\n", encoding="utf-8")

        return {
            "valid": not blocking,
            "summary": _check_summary(blocking_count=len(blocking), warning_count=len(warnings)),
            "blocking_issues": blocking,
            "warnings": warnings,
            "audit_findings": findings,
            "structured_findings": [finding.to_dict() for finding in raw_findings],
            "finding_groups": _group_serialized_findings(raw_findings),
            "narration_timing": narration_timing,
            "normalized_dsl_json": normalized,
            "recommended_edits": recommended_edits,
            "applied_fixes": applied_fixes,
            "file_path": str(resolved_path) if resolved_path else None,
        }

    def preview_animation(
        self,
        *,
        file_path: str,
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """Write a preview HTML file and first-frame PNG to the workspace."""
        doc, resolved_path = self._load_document(file_path=file_path)
        base_name = infer_slug(output_name or resolved_path.stem)
        output_paths = self._workspace_paths_for_document(resolved_path)

        output_paths.previews_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_paths.previews_dir / f"{base_name}.html"
        png_path = output_paths.previews_dir / f"{base_name}.png"
        theme_roots = self._theme_roots_for_document(resolved_path)
        timing_config = self._timing_config_for_document(resolved_path)

        write_web_preview(
            doc,
            html_path,
            theme_search_roots=theme_roots,
            timing_config=timing_config,
        )
        graph, theme = build_render_graph(
            doc,
            theme_search_roots=theme_roots,
            timing_config=timing_config,
        )
        renderer = CairoRenderer(theme)
        renderer.render_frame_to_file(graph, 0.0, str(png_path))

        return {
            "status": "ok",
            "html_path": str(html_path),
            "preview_image_path": str(png_path),
            "source_file_path": str(resolved_path),
        }

    def render_animation(
        self,
        *,
        file_path: str,
        format: str,
        output_name: str | None = None,
        audio_path: str | None = None,
        audio_timings_path: str | None = None,
        voice: bool = False,
        voice_provider: str | None = None,
        voice_id: str | None = None,
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        """Render an animation artifact into the workspace."""
        chosen_format = format.lower()
        if chosen_format not in {"png", "mp4", "webm"}:
            raise ValueError("format must be one of: png, mp4, webm.")

        doc, resolved_path = self._load_document(file_path=file_path)
        audio_abs = self._resolve_existing_path(audio_path) if audio_path else None
        audio_timings_abs = (
            self._resolve_existing_path(audio_timings_path) if audio_timings_path else None
        )
        if voice and (audio_abs or audio_timings_abs):
            raise ValueError("voice cannot be combined with audio_path or audio_timings_path.")
        if voice:
            self.validate_voice_setup(voice_provider=voice_provider)

        output_paths = self._workspace_paths_for_document(resolved_path)
        output_paths.renders_dir.mkdir(parents=True, exist_ok=True)
        base_name = infer_slug(output_name or resolved_path.stem)
        artifact_path = output_paths.renders_dir / f"{base_name}.{chosen_format}"
        theme_roots = self._theme_roots_for_document(resolved_path)
        result = render_document_artifact(
            doc,
            output_path=artifact_path,
            fps=doc.meta.fps,
            audio_path=audio_abs,
            audio_timings_path=audio_timings_abs,
            voice=voice,
            voice_provider=voice_provider,
            voice_id=voice_id,
            theme_search_roots=theme_roots,
            timing_config=self._timing_config_for_document(resolved_path),
            progress=progress,
            log_video_progress=False,
        )

        return {
            "status": "ok",
            "artifact_path": result.artifact_path,
            "duration_seconds": result.duration_seconds,
            "warnings": list(result.warnings),
            "retimed_document_path": result.retimed_document_path,
            "source_file_path": str(resolved_path),
        }

    def validate_voice_setup(self, *, voice_provider: str | None) -> str:
        """Validate that the selected voice provider is installed and configured."""
        return validate_voice_provider_setup(voice_provider)

    def preflight_command(
        self,
        command_name: str,
        *,
        needs_cairo: bool = False,
        needs_ffmpeg: bool = False,
        needs_ffprobe: bool = False,
        needs_workspace_write: bool = False,
    ) -> dict[str, Any]:
        """Run lightweight checks and raise an actionable error before a command starts."""
        required_checks = {"python_package"}
        if needs_cairo:
            required_checks.add("pycairo")
        if needs_ffmpeg:
            required_checks.add("ffmpeg")
        if needs_ffprobe:
            required_checks.add("ffprobe")
        if needs_workspace_write:
            required_checks.add("workspace_write")

        report = self.run_doctor(required_checks=required_checks, include_smoke=False)
        if report["ok"]:
            return report
        raise RuntimeError(format_preflight_report(command_name, report))

    def consume_doctor_hint(self) -> str | None:
        """Return a one-time doctor reminder after a successful command preflight."""
        hint_path = _doctor_hint_path()
        try:
            if hint_path.exists():
                return None
            hint_path.parent.mkdir(parents=True, exist_ok=True)
            hint_path.write_text("seen\n", encoding="utf-8")
        except OSError:
            return None

        return "Tip: run `kaivra doctor` for the full environment report and setup guidance."

    def download_model(
        self,
        *,
        model_name: str = DEFAULT_LOCAL_MODEL_NAME,
        target_dir: str | Path | None = None,
        force: bool = False,
        archive_url: str | None = None,
    ) -> dict[str, Any]:
        """Download a local Sherpa model bundle into the standard Kaivra models directory."""
        download_spec = _MODEL_ARCHIVES.get(model_name)
        if download_spec is None and archive_url is None:
            raise ValueError(f"Unknown model: {model_name}")

        destination = (
            Path(target_dir or (Path.home() / ".kaivra" / "models" / model_name))
            .expanduser()
            .resolve()
        )
        if force and destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)

        already_installed = False
        try:
            model_path, tokens_path, data_dir = _resolve_local_model_paths(destination)
            already_installed = True
        except FileNotFoundError:
            archive = archive_url or str(download_spec["archive_url"])
            with tempfile.TemporaryDirectory(prefix="kaivra_model_") as tmpdir:
                archive_path = Path(tmpdir) / f"{model_name}.tar.bz2"
                _download_file(archive, archive_path)
                _extract_tarball(archive_path, destination)
            model_path, tokens_path, data_dir = _resolve_local_model_paths(destination)

        return {
            "status": "ok",
            "model_name": model_name,
            "downloaded": not already_installed,
            "model_dir": str(destination),
            "model_path": str(model_path),
            "tokens_path": str(tokens_path),
            "data_dir": str(data_dir),
        }

    def install_mcp_config(
        self,
        *,
        client: str,
        server_name: str = "kaivra",
        command: str | None = None,
    ) -> dict[str, Any]:
        """Write or update a local stdio MCP config for Claude Code or Cursor."""
        chosen_client = _resolve_mcp_client(client)
        command_path = command or _resolve_mcp_server_command()
        config_path = _config_path_for_client(chosen_client)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError(f"Config file is not a JSON object: {config_path}")
        else:
            config = {}

        mcp_servers = config.setdefault("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            raise ValueError(f"mcpServers must be a JSON object in {config_path}")

        mcp_servers[server_name] = _mcp_server_entry(command_path)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        return {
            "status": "ok",
            "client": chosen_client,
            "config_path": str(config_path),
            "server_name": server_name,
            "command": command_path,
            "config_json": json.dumps({server_name: mcp_servers[server_name]}, indent=2),
        }

    def run_doctor(
        self,
        *,
        required_checks: set[str] | None = None,
        include_smoke: bool = True,
    ) -> dict[str, Any]:
        """Check that the local machine can run the Kaivra MCP workflow."""
        issues: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []
        requested_checks = set(
            required_checks
            or {
                "python_package",
                "pycairo",
                "ffmpeg",
                "ffprobe",
                "workspace_write",
                "smoke_render",
            }
        )
        if include_smoke:
            requested_checks.add("smoke_render")

        def add_check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": ok, "detail": detail})

        python_ok = True
        if "python_package" in requested_checks:
            try:
                importlib.import_module("kaivra")
                add_check("python_package", True, "Kaivra imports successfully.")
            except Exception as exc:
                python_ok = False
                add_check("python_package", False, f"Kaivra import failed: {exc}")
                issues.append(
                    _issue("python_package", str(exc), _platform_fix_commands()["python_package"])
                )

        cairo_ok = True
        if "pycairo" in requested_checks:
            try:
                importlib.import_module("cairo")
                add_check("pycairo", True, "pycairo imports successfully.")
            except Exception as exc:
                cairo_ok = False
                add_check("pycairo", False, f"pycairo import failed: {exc}")
                issues.append(_issue("pycairo", str(exc), _platform_fix_commands()["pycairo"]))

        ffmpeg_ok = True
        if "ffmpeg" in requested_checks:
            ffmpeg_ok, ffmpeg_detail = _command_available("ffmpeg")
            add_check("ffmpeg", ffmpeg_ok, ffmpeg_detail)
            if not ffmpeg_ok:
                issues.append(_issue("ffmpeg", ffmpeg_detail, _platform_fix_commands()["ffmpeg"]))

        ffprobe_ok = True
        if "ffprobe" in requested_checks:
            ffprobe_ok, ffprobe_detail = _command_available("ffprobe")
            add_check("ffprobe", ffprobe_ok, ffprobe_detail)
            if not ffprobe_ok:
                issues.append(
                    _issue("ffprobe", ffprobe_detail, _platform_fix_commands()["ffprobe"])
                )

        workspace_ok = True
        if "workspace_write" in requested_checks:
            try:
                tmp = tempfile.NamedTemporaryFile(dir=self.root, prefix=".kaivra_mcp_", delete=True)
                tmp.close()
                add_check("workspace_write", True, f"Workspace {self.root} is writable.")
            except Exception as exc:
                workspace_ok = False
                add_check("workspace_write", False, f"Workspace is not writable: {exc}")
                issues.append(
                    _issue("workspace_write", str(exc), ["Use a writable local workspace."])
                )

        if (
            include_smoke
            and "smoke_render" in requested_checks
            and python_ok
            and cairo_ok
            and ffmpeg_ok
            and ffprobe_ok
            and workspace_ok
        ):
            from kaivra.mcp.blueprints import build_starter_document
            from kaivra.render.cairo_renderer import CairoRenderer
            from kaivra.render.orchestration import build_render_graph

            try:
                smoke_doc = build_starter_document(
                    title="Doctor Smoke Test",
                    pattern="algorithm_walkthrough",
                    beats=["Goal: Verify the local Kaivra install."],
                    theme="modern",
                    audience=None,
                    include_narration=False,
                )
                graph, theme = build_render_graph(
                    smoke_doc,
                    theme_search_roots=[self.paths.themes_dir],
                )
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    smoke_path = Path(tmp.name)
                try:
                    CairoRenderer(theme).render_frame_to_file(graph, 0.0, str(smoke_path))
                    add_check(
                        "smoke_render",
                        True,
                        "Validated a starter document and rendered a smoke-test PNG.",
                    )
                finally:
                    smoke_path.unlink(missing_ok=True)
            except Exception as exc:
                add_check("smoke_render", False, f"Smoke render failed: {exc}")
                issues.append(
                    _issue(
                        "smoke_render",
                        str(exc),
                        ["Run `kaivra validate` on a sample file and check the local install."],
                    )
                )
        elif include_smoke and "smoke_render" in requested_checks:
            add_check(
                "smoke_render",
                False,
                "Skipped until Python, Cairo, ffmpeg, and workspace checks pass.",
            )

        mcp_command = _safe_resolve_mcp_server_command()

        return {
            "ok": not issues,
            "workspace_root": str(self.root),
            "checks": checks,
            "issues": issues,
            "mcp_command": mcp_command,
            "default_voice_provider": "openai",
            "local_voice": {
                "model_name": DEFAULT_LOCAL_MODEL_NAME,
                "model_dir": str(DEFAULT_LOCAL_MODEL_DIR),
                "download_command": f"kaivra download-model --model-name {DEFAULT_LOCAL_MODEL_NAME}",
            },
            "next_steps": [
                "Run `kaivra mcp-install --client auto` after the doctor is green.",
                (
                    "For the default cloud narration path, set `OPENAI_API_KEY`, then "
                    "`kaivra quick-render examples/explainers/agentic_debug_agent_explainer.json --voice`."
                ),
                (
                    "For offline local narration, run `kaivra download-model`, then "
                    "`KAIVRA_VOICE_PROVIDER=local kaivra quick-render "
                    "examples/explainers/agentic_debug_agent_explainer.json --voice`."
                ),
            ],
            "claude_code": {
                "command": mcp_command,
                "args": [],
                "config_path": str(_DEFAULT_CLAUDE_CONFIG_PATH),
                "config_json": json.dumps(
                    {
                        "mcpServers": {
                            "kaivra": {
                                "type": "stdio",
                                "command": mcp_command,
                                "args": [],
                            }
                        }
                    },
                    indent=2,
                ),
            },
            "cursor": {
                "command": mcp_command,
                "args": [],
                "config_path": str(_DEFAULT_CURSOR_CONFIG_PATH),
            },
        }

    def _load_document(
        self,
        *,
        file_path: str | None = None,
        dsl_json: str | None = None,
    ) -> tuple[Any, Path | None]:
        if file_path is not None:
            resolved = self.resolve_path(file_path)
            if not resolved.exists():
                raise FileNotFoundError(f"File not found: {resolved}")
            return parse_file(resolved), resolved

        if dsl_json is None:
            raise ValueError("Provide either file_path or dsl_json.")
        return parse_string(dsl_json, format="json"), None

    def _resolve_existing_path(self, path: str | None) -> Path:
        if path is None:
            raise ValueError("Expected a file path.")
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        return resolved

    def _resolve_theme(self, name: str) -> Any:
        return get_theme(
            name,
            search_roots=resolve_theme_search_roots(self.root, cwd=self.root),
        )

    def _theme_roots_for_document(self, resolved_path: Path | None) -> list[Path]:
        from kaivra.render.orchestration import resolve_theme_search_roots

        if resolved_path is None:
            return [self.paths.themes_dir]
        return resolve_theme_search_roots(resolved_path, cwd=self.root)

    def _timing_config_for_document(self, resolved_path: Path | None) -> Any:
        if resolved_path is None:
            return resolve_document_timing_config(self.root, cwd=self.root)
        return resolve_document_timing_config(resolved_path, cwd=self.root)

    def _workspace_paths_for_document(self, resolved_path: Path | None) -> WorkspacePaths:
        root = self._workspace_root_for_document(resolved_path)
        return WorkspacePaths(
            root=root,
            animations_dir=root / "animations",
            themes_dir=root / "themes",
            previews_dir=root / "artifacts" / "previews",
            renders_dir=root / "artifacts" / "renders",
        )

    def _workspace_root_for_document(self, resolved_path: Path | None) -> Path:
        if resolved_path is None:
            return self.root
        if self.root != Path("/") and resolved_path.is_relative_to(self.root):
            return self.root

        search_start = resolved_path if resolved_path.is_dir() else resolved_path.parent
        for parent in (search_start, *search_start.parents):
            if parent.name == "animations":
                return parent.parent
            if any((parent / name).is_dir() for name in ("animations", "themes", "artifacts")):
                return parent
        return search_start

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        counter = 2
        while True:
            candidate = path.with_name(f"{stem}-{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1


def format_doctor_report(report: dict[str, Any]) -> str:
    """Render a human-friendly CLI summary for the doctor command."""
    lines = [
        f"Workspace: {report['workspace_root']}",
        f"Status: {'ok' if report['ok'] else 'issues found'}",
        "",
        "Checks:",
    ]
    for check in report["checks"]:
        marker = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- {marker} {check['name']}: {check['detail']}")

    if report["issues"]:
        lines.extend(["", "Fixes:"])
        for issue in report["issues"]:
            lines.append(f"- {issue['title']}: {issue['detail']}")
            for step in issue["fix_steps"]:
                lines.append(f"  {step}")

    lines.extend(
        [
            "",
            "MCP Config:",
            f"- Resolved kaivra-mcp command: {report.get('mcp_command') or 'not found'}",
            f"- Claude Code config: {report['claude_code']['config_path']}",
            f"- Cursor config: {report['cursor']['config_path']}",
            "- Suggested Claude Code config:",
            report["claude_code"]["config_json"],
            "",
            "Voice Defaults:",
            f"- Default cloud provider: {report['default_voice_provider']}",
            "- OpenAI API key env: OPENAI_API_KEY",
            "",
            "Local Voice:",
            f"- Default model name: {report['local_voice']['model_name']}",
            f"- Default model dir: {report['local_voice']['model_dir']}",
            f"- Download command: {report['local_voice']['download_command']}",
        ]
    )
    return "\n".join(lines)


def format_preflight_report(command_name: str, report: dict[str, Any]) -> str:
    """Render a concise preflight failure message for guided commands."""
    lines = [f"`{command_name}` cannot continue until local setup issues are fixed."]
    for issue in report["issues"]:
        lines.append(f"- {issue['title']}: {issue['detail']}")
        for step in issue["fix_steps"]:
            lines.append(f"  {step}")
    lines.append("Run `kaivra doctor` for the full environment report.")
    return "\n".join(lines)


def _voice_sync_findings(
    doc: Any,
    *,
    voice_provider: str | None = None,
) -> list[CheckFinding]:
    """Check that narration keywords overlap with animation target content.

    These warnings are useful for every provider: ElevenLabs gets more precise
    cue alignment, while OpenAI and local renders still benefit from narration
    that names the same concepts in the same order as the visuals.
    """
    findings: list[CheckFinding] = []
    sync_actions = REVEAL_ACTIONS | EMPHASIS_ACTIONS

    for scene_spec in doc.scenes:
        narration = getattr(scene_spec, "narration", None)
        if not narration:
            continue

        scene_id = scene_spec.id or "unknown"

        # Build content index from scene + document-level objects.
        object_lists = []
        if scene_spec.objects:
            object_lists.append([obj.model_dump(exclude_none=True) for obj in scene_spec.objects])
        if doc.objects:
            object_lists.append([obj.model_dump(exclude_none=True) for obj in doc.objects])
        content_index = _build_content_index(*object_lists) if object_lists else {}
        object_meta = _build_object_metadata_index(*object_lists) if object_lists else {}
        if not content_index:
            continue

        seen_targets: set[tuple[str, str, str]] = set()
        for anim in scene_spec.animations or []:
            action = anim.action if hasattr(anim, "action") else None
            if action not in sync_actions:
                continue
            action_value = getattr(action, "value", action)
            if not isinstance(action_value, str):
                continue

            targets = anim.target if isinstance(anim.target, list) else [anim.target]
            for target_id in targets:
                if target_id is None:
                    continue
                target_key = (scene_id, action_value, target_id)
                if target_key in seen_targets:
                    continue
                seen_targets.add(target_key)

                target_meta = object_meta.get(target_id, {})
                target_type = target_meta.get("type")
                if target_type == "connector":
                    continue
                if action_value in EMPHASIS_ACTIONS and target_type == "token":
                    continue

                content = content_index.get(target_id, "")
                if not content:
                    continue
                score = _semantic_score(narration, content)
                if score == 0:
                    target_terms = [
                        token
                        for token in dict.fromkeys(_tokenize_for_overlap(content))
                        if len(token) >= 3
                    ]
                    narration_terms = [
                        token
                        for token in dict.fromkeys(_tokenize_for_overlap(narration))
                        if len(token) >= 3
                    ]
                    detail_parts: list[str] = []
                    if target_terms:
                        detail_parts.append(
                            "Missing target terms: " + ", ".join(target_terms[:4]) + "."
                        )
                    if narration_terms:
                        detail_parts.append(
                            "Narration terms seen: " + ", ".join(narration_terms[:6]) + "."
                        )
                    detail_suffix = (" " + " ".join(detail_parts)) if detail_parts else ""
                    if voice_provider == "elevenlabs":
                        message = (
                            f"{action_value} targeting '{target_id}' "
                            f"(content: '{content.strip()}') has no keyword match "
                            f"in narration — ElevenLabs will fall back to positional "
                            f"matching instead of precise word-level sync.{detail_suffix}"
                        )
                    elif voice_provider == "openai":
                        message = (
                            f"{action_value} targeting '{target_id}' "
                            f"(content: '{content.strip()}') has no keyword match "
                            f"in narration — OpenAI voice keeps scene-level timing, so the "
                            f"beat may feel less intentional unless the narration names the same concept."
                            f"{detail_suffix}"
                        )
                    else:
                        message = (
                            f"{action_value} targeting '{target_id}' "
                            f"(content: '{content.strip()}') has no keyword match "
                            f"in narration — local voice keeps scene-level timing, but the "
                            f"beat may feel less intentional unless the narration names the same concept."
                            f"{detail_suffix}"
                        )
                    findings.append(
                        CheckFinding(
                            severity="warning",
                            scene_id=scene_id,
                            kind="voice_sync",
                            message=message,
                        )
                    )

    return findings


def _audit_document(
    doc: Any,
    *,
    theme_search_roots: list[Path] | None = None,
    timing_config: Any = None,
) -> list[str]:
    _raw_findings, findings, _recommended_edits = _audit_document_report(
        doc,
        theme_search_roots=theme_search_roots,
        timing_config=timing_config,
    )
    return findings


def _audit_document_report(
    doc: Any,
    *,
    theme_search_roots: list[Path] | None = None,
    timing_config: Any = None,
    voice: bool = False,
    voice_provider: str | None = None,
) -> tuple[
    list[CheckFinding],
    list[str],
    list[dict[str, str | int | float | bool | None]],
]:
    preflight_findings = _preflight_high_level_animation_findings(doc)
    if any(finding.severity == "error" for finding in preflight_findings):
        serialized_findings = _serialize_findings(preflight_findings)
        recommended_edits = _recommended_edits_from_findings(preflight_findings)
        if not recommended_edits:
            recommended_edits = _recommend_edits_from_messages(serialized_findings)
        return preflight_findings, serialized_findings, recommended_edits

    graph, _theme = build_render_graph(
        doc,
        theme_search_roots=theme_search_roots,
        timing_config=timing_config,
    )
    findings: list[CheckFinding] = []
    findings.extend(_layout_audit_findings(graph))

    persistent_refs = _collect_object_refs(doc.objects, prefix="objects")
    scene_map = {scene.id: scene for scene in graph.scenes}

    for scene_index, scene_spec in enumerate(doc.scenes):
        scene_id = scene_spec.id or f"scene_{scene_index}"
        resolved_scene = scene_map.get(scene_id)
        if resolved_scene is None:
            continue
        previous_scene_spec = doc.scenes[scene_index - 1] if scene_index > 0 else None

        scene_refs = _collect_object_refs(
            scene_spec.objects,
            prefix=f"scenes[{scene_index}].objects",
        )
        in_scope_refs = persistent_refs + scene_refs
        in_scope_ids = _available_ids(in_scope_refs)

        findings.extend(_scene_duration_findings(scene_spec=scene_spec, scene=resolved_scene))
        findings.extend(
            _narration_findings(
                scene_spec=scene_spec,
                resolved_scene=resolved_scene,
                show_subtitles=doc.meta.show_subtitles,
                scene_refs=in_scope_refs,
                voice=voice,
            )
        )
        findings.extend(
            _audience_narration_findings(
                scene_spec=scene_spec,
                resolved_scene=resolved_scene,
                audience=getattr(doc.meta, "audience", None),
            )
        )
        findings.extend(
            _explanatory_narration_findings(
                scene_spec=scene_spec,
                resolved_scene=resolved_scene,
                scene_refs=in_scope_refs,
            )
        )
        findings.extend(
            _scene_reference_findings(
                scene_id=resolved_scene.id,
                scene_spec=scene_spec,
                scene_index=scene_index,
                resolved_scene=resolved_scene,
                object_refs=in_scope_refs,
                available_ids=in_scope_ids,
            )
        )
        findings.extend(
            _scene_visibility_findings(
                scene_id=resolved_scene.id,
                scene_spec=scene_spec,
                scene_index=scene_index,
                resolved_scene=resolved_scene,
                object_refs=scene_refs,
            )
        )
        findings.extend(
            _scene_double_reveal_findings(
                scene_id=resolved_scene.id,
                scene_spec=scene_spec,
                previous_scene_spec=previous_scene_spec,
                scene_index=scene_index,
            )
        )

    findings.extend(_repetitive_scaffold_findings(doc.scenes))
    findings.extend(_continuity_content_findings(doc))

    if voice:
        findings.extend(_voice_sync_findings(doc, voice_provider=voice_provider))

    serialized_findings = _serialize_findings(findings)
    recommended_edits = _recommended_edits_from_findings(findings)
    if not recommended_edits:
        recommended_edits = _recommend_edits_from_messages(serialized_findings)
    return findings, serialized_findings, recommended_edits


def _preflight_high_level_animation_findings(doc: Any) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    persistent_refs = _collect_object_refs(doc.objects, prefix="objects")
    for scene_index, scene_spec in enumerate(doc.scenes):
        scene_id = scene_spec.id or f"scene_{scene_index}"
        scene_refs = _collect_object_refs(
            scene_spec.objects,
            prefix=f"scenes[{scene_index}].objects",
        )
        object_map = {
            ref.object_id: ref.spec for ref in persistent_refs + scene_refs if ref.object_id
        }
        for animation_index, anim in enumerate(scene_spec.animations):
            findings.extend(
                _high_level_animation_findings(
                    scene_id=scene_id,
                    scene_index=scene_index,
                    animation_index=animation_index,
                    anim=anim,
                    object_map=object_map,
                )
            )
    return findings


def _layout_audit_findings(graph: Any) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    scene_map = {scene.id: scene for scene in graph.scenes}
    for finding in audit_scene_graph(graph, samples_per_scene=4):
        suggested_edit: RecommendedEdit | None = None
        scene = scene_map.get(finding.scene_id)
        if scene is not None:
            suggested_edit = _layout_recommendation(scene, finding)
        findings.append(
            CheckFinding(
                severity=finding.severity,
                scene_id=finding.scene_id,
                kind=f"{finding.kind}@{finding.time_seconds:.2f}s",
                message=finding.message,
                recommended_edit=suggested_edit,
            )
        )
    return findings


def _scene_duration_findings(*, scene_spec: Any, scene: Any) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    if scene.duration < _MIN_SCENE_DURATION_SECONDS:
        findings.append(
            CheckFinding(
                severity="warning",
                scene_id=scene.id,
                kind="pacing",
                message=(
                    f"Scene lasts {scene.duration:.1f}s, which is shorter than the recommended "
                    f"{_MIN_SCENE_DURATION_SECONDS:.0f}s minimum."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene.id,
                    action="retime_scene",
                    object_id=None,
                    field="duration",
                    suggested_value=_format_duration_value(_MIN_SCENE_DURATION_SECONDS),
                    reason="Very short scenes tend to rush the motion and narration.",
                ),
            )
        )
    if scene.duration > _MAX_SCENE_DURATION_SECONDS:
        findings.append(
            CheckFinding(
                severity="warning",
                scene_id=scene.id,
                kind="pacing",
                message=(
                    f"Scene lasts {scene.duration:.1f}s, which is longer than the recommended "
                    f"{_MAX_SCENE_DURATION_SECONDS:.0f}s maximum."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene.id,
                    action="retime_scene",
                    object_id=None,
                    field="duration",
                    suggested_value=_format_duration_value(_MAX_SCENE_DURATION_SECONDS),
                    reason="Long scenes are often easier to follow when split into tighter beats.",
                ),
            )
        )
    max_timeline_end = max(
        (keyframe.start_time + keyframe.duration for keyframe in getattr(scene, "timeline", [])),
        default=0.0,
    )
    if (
        getattr(scene_spec, "duration", "auto") != "auto"
        and max_timeline_end > scene.duration + 0.01
    ):
        findings.append(
            CheckFinding(
                severity="warning",
                scene_id=scene.id,
                kind="timing",
                message=(
                    f"Resolved animations run until {max_timeline_end:.1f}s, but the scene duration "
                    f"is pinned to {scene.duration:.1f}s."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene.id,
                    action="review_timing",
                    object_id=None,
                    field="duration",
                    suggested_value=None,
                    reason="Increase the explicit scene duration or move the final anchored event earlier.",
                ),
            )
        )
    return findings


def _high_level_animation_findings(
    *,
    scene_id: str,
    scene_index: int,
    animation_index: int,
    anim: Any,
    object_map: dict[str, Any],
) -> list[CheckFinding]:
    if anim.action.value != "reveal-children":
        return []

    target_path = f"scenes[{scene_index}].animations[{animation_index}].target"
    if not isinstance(anim.target, str) or not anim.target.strip():
        return [
            CheckFinding(
                severity="error",
                scene_id=scene_id,
                kind="reference",
                message=(
                    f"Animation {animation_index} uses `reveal-children` without a target group ID."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="replace_target",
                    object_id=None,
                    field=target_path,
                    suggested_value=None,
                    reason="Reveal-children needs the ID of a group in the same scene.",
                ),
            )
        ]

    target_spec = object_map.get(anim.target)
    if target_spec is None:
        return [
            CheckFinding(
                severity="error",
                scene_id=scene_id,
                kind="reference",
                message=f"Animation {animation_index} targets missing group `{anim.target}`.",
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="replace_target",
                    object_id=None,
                    field=target_path,
                    suggested_value=_closest_id_suggestion(anim.target, set(object_map)),
                    reason="Reveal-children must reference a valid group object ID.",
                ),
            )
        ]
    if target_spec.type != ObjectType.GROUP:
        return [
            CheckFinding(
                severity="error",
                scene_id=scene_id,
                kind="reference",
                message=(
                    f"Animation {animation_index} uses `reveal-children` for `{anim.target}`, "
                    "but that object is not a group."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="review_animation",
                    object_id=anim.target,
                    field=target_path,
                    suggested_value=None,
                    reason="Reveal-children only works with group objects.",
                ),
            )
        ]
    if not getattr(target_spec, "children", None):
        return [
            CheckFinding(
                severity="error",
                scene_id=scene_id,
                kind="reference",
                message=(
                    f"Animation {animation_index} uses `reveal-children` for `{anim.target}`, "
                    "but the group has no immediate children."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="review_animation",
                    object_id=anim.target,
                    field=target_path,
                    suggested_value=None,
                    reason="Reveal-children needs a group with authored child objects.",
                ),
            )
        ]
    return []


def _narration_findings(
    *,
    scene_spec: Any,
    resolved_scene: Any,
    show_subtitles: bool,
    scene_refs: list[ObjectRef],
    voice: bool,
) -> list[CheckFinding]:
    narration = (scene_spec.narration or "").strip()
    if not narration:
        return []

    findings: list[CheckFinding] = []
    read_time = _estimate_read_time_seconds(narration)
    if (
        read_time > resolved_scene.duration * _NARRATION_OVERAGE_RATIO
        and read_time - resolved_scene.duration >= _NARRATION_OVERAGE_SECONDS
    ):
        max_words = max(1, int(resolved_scene.duration * (_READ_TIME_WORDS_PER_MINUTE / 60.0)))
        findings.append(
            CheckFinding(
                severity="warning",
                scene_id=resolved_scene.id,
                kind="narration",
                message=(
                    ("Pre-retiming diagnostic: " if voice else "")
                    + f"Narration needs about {read_time:.1f}s at {_READ_TIME_WORDS_PER_MINUTE} WPM, "
                    f"but the scene lasts {resolved_scene.duration:.1f}s."
                    + (
                        " Voice retiming will stretch the scene automatically during a voiced render."
                        if voice
                        else ""
                    )
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=resolved_scene.id,
                    action="shorten_text",
                    object_id=None,
                    field="narration",
                    suggested_value=max_words,
                    reason=(
                        "Only shorten the narration if you want less retiming or plan a silent render."
                        if voice
                        else "Shorten the narration or lengthen the scene so the delivery does not feel rushed."
                    ),
                ),
            )
        )

    if show_subtitles:
        redundant_ref = _find_redundant_text_ref(scene_refs, narration)
        if redundant_ref is not None:
            findings.append(
                CheckFinding(
                    severity="warning",
                    scene_id=resolved_scene.id,
                    kind="redundant_copy",
                    message=(
                        f"On-screen text `{redundant_ref.object_id}` substantially duplicates the narration "
                        "while captions are enabled."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=resolved_scene.id,
                        action="shorten_text",
                        object_id=redundant_ref.object_id,
                        field="content",
                        suggested_value=None,
                        reason="Keep the body copy focused on labels or keywords instead of repeating the caption verbatim.",
                    ),
                )
            )

    return findings


def _audience_narration_findings(
    *,
    scene_spec: Any,
    resolved_scene: Any,
    audience: Any,
) -> list[CheckFinding]:
    audience_value = getattr(audience, "value", audience)
    if audience_value not in {"layperson", "mixed"}:
        return []

    narration = (scene_spec.narration or "").strip()
    if not narration:
        return []

    matched_terms: list[str] = []
    file_matches = re.findall(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|json|yaml|yml|md)\b", narration)
    path_matches = re.findall(r"(?:^|[\s(])(/[\w./-]+|[\w.-]+/[\w./-]+)", narration)
    identifier_matches = re.findall(
        r"\b[a-z]+(?:_[a-z0-9]+)+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b", narration
    )

    matched_terms.extend(file_matches[:3])
    matched_terms.extend(match.strip(" (") for match in path_matches[:3])
    matched_terms.extend(identifier_matches[:3])

    lowered = narration.lower()
    for term in sorted(_LAYPERSON_JARGON):
        if term in lowered:
            matched_terms.append(term)

    deduped_terms = [term for term in dict.fromkeys(matched_terms) if term]
    if not deduped_terms:
        return []

    if audience_value == "mixed":
        strong_internal_terms = len(file_matches) + len(path_matches) + len(identifier_matches)
        jargon_hits = [term for term in deduped_terms if term.lower() in _LAYPERSON_JARGON]
        if strong_internal_terms < 2 and len(jargon_hits) < 3:
            return []
        message = (
            "Narration targets a mixed audience but still leans on internal identifiers or implementation jargon: "
            + ", ".join(deduped_terms[:6])
            + "."
        )
        reason = (
            "Keep the default narration understandable on first listen. Replace file names, paths, and internal "
            "implementation terms with user-facing process language unless the user explicitly asked for technical detail."
        )
    else:
        message = (
            "Narration targets a layperson audience but still uses file names, code paths, or technical jargon: "
            + ", ".join(deduped_terms[:6])
            + "."
        )
        reason = (
            "Replace internal identifiers and jargon with plain-English descriptions that explain the idea "
            "without requiring repo or implementation context."
        )

    return [
        CheckFinding(
            severity="warning",
            scene_id=resolved_scene.id,
            kind="audience_language",
            message=message,
            recommended_edit=RecommendedEdit(
                scene_id=resolved_scene.id,
                action="simplify_language",
                object_id=None,
                field="narration",
                suggested_value=None,
                reason=reason,
            ),
        )
    ]


def _explanatory_narration_findings(
    *,
    scene_spec: Any,
    resolved_scene: Any,
    scene_refs: list[ObjectRef],
) -> list[CheckFinding]:
    narration = (scene_spec.narration or "").strip()
    if not narration:
        return []
    if len(narration.split()) < _EXPLANATION_MIN_WORDS:
        return []
    if _has_explanatory_language(narration):
        return []
    if not _scene_needs_explanatory_narration(scene_refs, narration):
        return []

    return [
        CheckFinding(
            severity="warning",
            scene_id=resolved_scene.id,
            kind="explanatory_narration",
            message=(
                "Narration walks through the mechanics but never explains what this step "
                "accomplishes or why it matters."
            ),
            recommended_edit=RecommendedEdit(
                scene_id=resolved_scene.id,
                action="expand_text",
                object_id=None,
                field="narration",
                suggested_value=None,
                reason=(
                    "Add one plain-English clause about the purpose of the step so the scene "
                    "teaches meaning, not just arithmetic."
                ),
            ),
        )
    ]


def _scene_reference_findings(
    *,
    scene_id: str,
    scene_spec: Any,
    scene_index: int,
    resolved_scene: Any,
    object_refs: list[ObjectRef],
    available_ids: set[str],
) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    object_map = {ref.object_id: ref.spec for ref in object_refs if ref.object_id}
    scene_local_ids = {
        ref.object_id
        for ref in object_refs
        if ref.object_id and ref.path.startswith(f"scenes[{scene_index}]")
    }
    for object_ref in object_refs:
        if object_ref.spec.type == ObjectType.CONNECTOR:
            findings.extend(_connector_reference_findings(scene_id, object_ref, available_ids))

    for animation_index, anim in enumerate(scene_spec.animations):
        findings.extend(
            _high_level_animation_findings(
                scene_id=scene_id,
                scene_index=scene_index,
                animation_index=animation_index,
                anim=anim,
                object_map=object_map,
            )
        )
        target_path = f"scenes[{scene_index}].animations[{animation_index}].target"
        targets = _normalized_animation_targets(anim.target)
        if anim.target is None or not targets:
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=(
                        f"Animation {animation_index} has no target, so `{anim.action.value}` will not affect any object."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=target_path,
                        suggested_value=None,
                        reason="Object animations need at least one valid target ID.",
                    ),
                )
            )
            continue

        if anim.action.value == "swap" and len(targets) != 2:
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=(
                        f"Animation {animation_index} uses `swap` but targets {len(targets)} objects instead of exactly 2."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=target_path,
                        suggested_value=None,
                        reason="Swap animations need exactly two valid target IDs.",
                    ),
                )
            )

        if anim.action.value == "replace" and len(targets) != 1:
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=(
                        f"Animation {animation_index} uses `replace` but targets {len(targets)} objects instead of exactly 1."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=target_path,
                        suggested_value=None,
                        reason="Replace animations need exactly one target ID plus one `with` ID.",
                    ),
                )
            )

        for target_index, target_id in enumerate(targets):
            if target_id in available_ids:
                continue
            target_field = (
                target_path
                if not isinstance(anim.target, list)
                else f"{target_path}[{target_index}]"
            )
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=f"Animation {animation_index} targets missing object `{target_id}`.",
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=target_field,
                        suggested_value=_closest_id_suggestion(target_id, available_ids),
                        reason="Animation targets must resolve to scene-local or document-level object IDs.",
                    ),
                )
            )

        if anim.with_id and anim.with_id not in available_ids:
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=f"Animation {animation_index} replaces with missing object `{anim.with_id}`.",
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=f"scenes[{scene_index}].animations[{animation_index}].with",
                        suggested_value=_closest_id_suggestion(anim.with_id, available_ids),
                        reason="Replace animations need a valid replacement object ID.",
                    ),
                )
            )
        elif anim.action.value == "replace":
            if not anim.with_id:
                findings.append(
                    CheckFinding(
                        severity="error",
                        scene_id=scene_id,
                        kind="reference",
                        message=f"Animation {animation_index} uses `replace` without a `with` object ID.",
                        recommended_edit=RecommendedEdit(
                            scene_id=scene_id,
                            action="replace_target",
                            object_id=None,
                            field=f"scenes[{scene_index}].animations[{animation_index}].with",
                            suggested_value=None,
                            reason="Replace animations need a replacement object ID in the same scene.",
                        ),
                    )
                )
            elif anim.with_id not in scene_local_ids:
                findings.append(
                    CheckFinding(
                        severity="error",
                        scene_id=scene_id,
                        kind="reference",
                        message=(
                            f"Animation {animation_index} replaces with `{anim.with_id}`, "
                            "but the replacement object must be authored in the same scene."
                        ),
                        recommended_edit=RecommendedEdit(
                            scene_id=scene_id,
                            action="move_object_into_scene",
                            object_id=anim.with_id,
                            field=f"scenes[{scene_index}].objects",
                            suggested_value=None,
                            reason="Replace v1 only supports same-scene before/after swaps.",
                        ),
                    )
                )
            elif (
                targets
                and targets[0] in resolved_scene.node_map
                and anim.with_id in resolved_scene.node_map
            ):
                target_rect = resolved_scene.node_map[targets[0]].rect
                replacement_rect = resolved_scene.node_map[anim.with_id].rect
                if not _rects_materially_aligned(target_rect, replacement_rect):
                    findings.append(
                        CheckFinding(
                            severity="error",
                            scene_id=scene_id,
                            kind="reference",
                            message=(
                                f"Animation {animation_index} uses `replace` for `{targets[0]}` -> "
                                f"`{anim.with_id}`, but the two objects do not share the same position. "
                                "Align them first."
                            ),
                            recommended_edit=RecommendedEdit(
                                scene_id=scene_id,
                                action="align_replacement",
                                object_id=anim.with_id,
                                field=f"scenes[{scene_index}].objects",
                                suggested_value=None,
                                reason="Replace only cross-fades same-position objects in v1.",
                            ),
                        )
                    )

        if anim.to_id and anim.to_id not in available_ids:
            findings.append(
                CheckFinding(
                    severity="error",
                    scene_id=scene_id,
                    kind="reference",
                    message=f"Animation {animation_index} moves toward missing object `{anim.to_id}`.",
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="replace_target",
                        object_id=None,
                        field=f"scenes[{scene_index}].animations[{animation_index}].to_id",
                        suggested_value=_closest_id_suggestion(anim.to_id, available_ids),
                        reason="`move-to` style animations need a valid destination object ID.",
                    ),
                )
            )

    return findings


def _scene_visibility_findings(
    *,
    scene_id: str,
    scene_spec: Any,
    scene_index: int,
    resolved_scene: Any,
    object_refs: list[ObjectRef],
) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for object_ref in object_refs:
        object_id = object_ref.object_id
        if not object_id:
            continue
        node = resolved_scene.node_map.get(object_id)
        if node is None or node.persistent:
            continue
        if getattr(object_ref.spec, "visible", None) is True or node.default_visible:
            continue
        if _has_effective_reveal_path(object_id, resolved_scene.timeline):
            continue
        findings.append(
            CheckFinding(
                severity="warning",
                scene_id=scene_id,
                kind="visibility",
                message=(
                    f"Object `{object_id}` has no visibility animation and will never appear "
                    "while `auto_visible` is off."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="add_visibility_animation",
                    object_id=object_id,
                    field=f"scenes[{scene_index}].animations",
                    suggested_value=None,
                    reason="Add a `fade-in` or make the object visible by default so it can appear on screen.",
                ),
            )
        )

    # Second pass: check for invisible parent groups blocking visible children.
    raw_objects = getattr(scene_spec, "objects", None) or []
    if raw_objects:
        parent_map = _object_parent_map(raw_objects)
        revealed_ids: set[str] = set()
        for obj_ref in object_refs:
            oid = obj_ref.object_id
            if oid and _has_effective_reveal_path(oid, resolved_scene.timeline):
                revealed_ids.add(oid)

        checked_ancestors: set[str] = set()
        for child_id in revealed_ids:
            ancestor_id = parent_map.get(child_id)
            while ancestor_id is not None:
                if ancestor_id in checked_ancestors:
                    break
                checked_ancestors.add(ancestor_id)
                node = resolved_scene.node_map.get(ancestor_id)
                if node is None or node.persistent or node.default_visible:
                    ancestor_id = parent_map.get(ancestor_id)
                    continue
                ancestor_ref = next((r for r in object_refs if r.object_id == ancestor_id), None)
                if ancestor_ref and getattr(ancestor_ref.spec, "visible", None) is True:
                    ancestor_id = parent_map.get(ancestor_id)
                    continue
                if _has_effective_reveal_path(ancestor_id, resolved_scene.timeline):
                    ancestor_id = parent_map.get(ancestor_id)
                    continue
                findings.append(
                    CheckFinding(
                        severity="error",
                        scene_id=scene_id,
                        kind="visibility",
                        message=(
                            f"Group `{ancestor_id}` has no visibility animation and will block "
                            f"its children (including `{child_id}`) from appearing while "
                            "`auto_visible` is off."
                        ),
                        recommended_edit=RecommendedEdit(
                            scene_id=scene_id,
                            action="enable_layout_group_visibility",
                            object_id=ancestor_id,
                            field=f"scenes[{scene_index}].objects",
                            suggested_value=True,
                            reason=(
                                "For layout-only parent groups, set `visible: true`; otherwise add a "
                                "`fade-in` on the group so its children can appear."
                            ),
                        ),
                    )
                )
                break  # Only report the nearest blocking ancestor

    return findings


def _repetitive_scaffold_findings(scene_specs: list[Any]) -> list[CheckFinding]:
    narrated_runs: list[tuple[str, tuple[str, ...]]] = []
    for index, scene_spec in enumerate(scene_specs):
        narration = (getattr(scene_spec, "narration", None) or "").strip()
        if not narration:
            continue
        object_ids = tuple(
            sorted(_collect_scene_object_ids(getattr(scene_spec, "objects", []) or []))
        )
        if len(object_ids) < 4:
            continue
        scene_id = getattr(scene_spec, "id", None) or f"scene_{index}"
        narrated_runs.append((scene_id, object_ids))

    findings: list[CheckFinding] = []
    run_start = 0
    while run_start < len(narrated_runs):
        run_end = run_start + 1
        while (
            run_end < len(narrated_runs)
            and narrated_runs[run_end][1] == narrated_runs[run_start][1]
        ):
            run_end += 1
        if run_end - run_start >= 3:
            scene_ids = [scene_id for scene_id, _ in narrated_runs[run_start:run_end]]
            repeated_ids = narrated_runs[run_start][1][:4]
            findings.append(
                CheckFinding(
                    severity="warning",
                    scene_id=scene_ids[0],
                    kind="starter_scaffold",
                    message=(
                        f"Scenes {', '.join(scene_ids)} reuse the same local object scaffold "
                        f"({', '.join(f'`{object_id}`' for object_id in repeated_ids)}...) with mostly swapped text. "
                        "That still reads like a starter template rather than a scene-specific explainer."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_ids[0],
                        action="customize_scene_structure",
                        object_id=None,
                        field="scenes",
                        suggested_value=None,
                        reason=(
                            "Replace repeated scaffold cards with topic-specific values, states, and connectors "
                            "so each beat has its own visual structure."
                        ),
                    ),
                )
            )
        run_start = run_end
    return findings


def _scene_double_reveal_findings(
    *,
    scene_id: str,
    scene_spec: Any,
    previous_scene_spec: Any | None,
    scene_index: int,
) -> list[CheckFinding]:
    reveal_events = _collect_reveal_events(scene_spec)
    if not reveal_events:
        return []

    findings: list[CheckFinding] = []
    incoming_fade_duration = _incoming_scene_fade_duration(previous_scene_spec)
    if incoming_fade_duration > 0:
        early_reveals = sorted(
            {
                event.object_id
                for event in reveal_events
                if event.start_seconds < incoming_fade_duration - _DOUBLE_REVEAL_HOLD_WINDOW_SECONDS
            }
        )
        if early_reveals:
            object_list = ", ".join(f"`{object_id}`" for object_id in early_reveals[:3])
            if len(early_reveals) > 3:
                object_list += f", and {len(early_reveals) - 3} more"
            findings.append(
                CheckFinding(
                    severity="warning",
                    scene_id=scene_id,
                    kind="double_reveal",
                    message=(
                        f"The previous scene fades into this one over {incoming_fade_duration:.1f}s, "
                        f"but {object_list} also start revealing immediately. That can make the content "
                        "look like it appears twice."
                    ),
                    recommended_edit=RecommendedEdit(
                        scene_id=scene_id,
                        action="retime_visibility",
                        object_id=early_reveals[0] if len(early_reveals) == 1 else None,
                        field=f"scenes[{scene_index}].animations",
                        suggested_value=None,
                        reason=(
                            "Delay object reveals until the incoming scene fade is done, or make the "
                            "object instant if the scene transition already introduces it."
                        ),
                    ),
                )
            )

    parent_map = _object_parent_map(scene_spec.objects)
    events_by_object: dict[str, list[RevealEvent]] = defaultdict(list)
    for event in reveal_events:
        events_by_object[event.object_id].append(event)

    warned_pairs: set[tuple[str, str]] = set()
    for child_id, parent_id in parent_map.items():
        ancestor_id = parent_id
        while ancestor_id is not None:
            if ancestor_id in events_by_object and child_id in events_by_object:
                if any(
                    _gradual_reveal_overlap(ancestor_event, child_event)
                    for ancestor_event in events_by_object[ancestor_id]
                    for child_event in events_by_object[child_id]
                ):
                    pair = (ancestor_id, child_id)
                    if pair not in warned_pairs:
                        warned_pairs.add(pair)
                        findings.append(
                            CheckFinding(
                                severity="warning",
                                scene_id=scene_id,
                                kind="double_reveal",
                                message=(
                                    f"Group `{ancestor_id}` and child `{child_id}` both reveal during "
                                    "the same window, so the child may look like it fades in twice."
                                ),
                                recommended_edit=RecommendedEdit(
                                    scene_id=scene_id,
                                    action="simplify_reveal",
                                    object_id=child_id,
                                    field=f"scenes[{scene_index}].animations",
                                    suggested_value=None,
                                    reason=(
                                        "Let either the group or the child control the reveal timing, "
                                        "not both at once."
                                    ),
                                ),
                            )
                        )
            ancestor_id = parent_map.get(ancestor_id)

    return findings


def _continuity_content_findings(doc: Any) -> list[CheckFinding]:
    if not getattr(doc.meta, "continuity", False):
        return []

    findings: list[CheckFinding] = []
    previous_scene_content: dict[str, tuple[str, str | None]] | None = None
    previous_scene_id: str | None = None

    for scene_index, scene_spec in enumerate(doc.scenes):
        scene_id = scene_spec.id or f"scene_{scene_index}"
        current_content = _collect_scene_content_map(getattr(scene_spec, "objects", None) or [])
        if previous_scene_content is not None and previous_scene_id is not None:
            for object_id, (content, object_type) in current_content.items():
                prior = previous_scene_content.get(object_id)
                if prior is None:
                    continue
                prior_content, prior_type = prior
                if _should_skip_continuity_warning(
                    object_id=object_id,
                    object_type=object_type,
                    prior_content=prior_content,
                    content=content,
                ):
                    continue
                if not content or not prior_content:
                    continue
                if content == prior_content and object_type == prior_type:
                    continue
                similarity = SequenceMatcher(None, prior_content.lower(), content.lower()).ratio()
                overlap = _token_overlap_ratio(
                    _tokenize_for_overlap(prior_content),
                    _tokenize_for_overlap(content),
                )
                if similarity >= 0.45 or overlap >= 0.5:
                    continue
                findings.append(
                    CheckFinding(
                        severity="warning",
                        scene_id=scene_id,
                        kind="continuity",
                        message=(
                            f"Object `{object_id}` is reused from scene `{previous_scene_id}` but its content "
                            f"changes sharply from '{prior_content}' to '{content}'. That may break continuity morphing."
                        ),
                        recommended_edit=RecommendedEdit(
                            scene_id=scene_id,
                            action="split_continuity_id",
                            object_id=object_id,
                            field=f"scenes[{scene_index}].objects",
                            suggested_value=None,
                            reason=(
                                "Keep the same ID only when the object is truly the same visual state. "
                                "Rename it or keep the content closer if you want a continuity morph."
                            ),
                        ),
                    )
                )
        previous_scene_content = current_content
        previous_scene_id = scene_id

    return findings


def _should_skip_continuity_warning(
    *,
    object_id: str,
    object_type: str | None,
    prior_content: str,
    content: str,
) -> bool:
    if object_type == "text" and object_id in _COMMON_HEADING_IDS:
        if len(prior_content.split()) <= 6 and len(content.split()) <= 6:
            return True
    return False


def _collect_scene_content_map(objects: list[Any]) -> dict[str, tuple[str, str | None]]:
    content_map: dict[str, tuple[str, str | None]] = {}

    def walk(nodes: list[Any]) -> None:
        for node in nodes:
            object_id = getattr(node, "id", None)
            if object_id:
                content_value = getattr(node, "content", None)
                if isinstance(content_value, str) and content_value.strip():
                    object_type = getattr(node, "type", None)
                    if hasattr(object_type, "value"):
                        object_type = object_type.value
                    content_map[object_id] = (content_value.strip(), object_type)
            walk(getattr(node, "children", None) or [])

    walk(objects)
    return content_map


def _build_object_metadata_index(
    *object_lists: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for obj_list in object_lists:
        for obj in obj_list or []:
            if isinstance(obj, dict):
                _index_object_metadata(obj, metadata)
    return metadata


def _index_object_metadata(obj: dict[str, Any], metadata: dict[str, dict[str, Any]]) -> None:
    obj_id = obj.get("id")
    if isinstance(obj_id, str) and obj_id:
        metadata[obj_id] = {
            "type": obj.get("type"),
            "layout": obj.get("layout"),
        }
    for child in obj.get("children", []) or []:
        if isinstance(child, dict):
            _index_object_metadata(child, metadata)


def _has_effective_reveal_path(object_id: str, timeline: list[Any]) -> bool:
    visibility_actions = {
        "appear",
        "fade-in",
        "build",
        "draw",
        "type",
        "scale",
        "move",
        "move-to",
        "swap",
        "highlight",
        "pulse",
        "replace",
    }
    for keyframe in timeline:
        action = getattr(keyframe.action, "value", keyframe.action)
        if action not in visibility_actions:
            continue
        if keyframe.target_id == object_id or getattr(keyframe, "with_id", None) == object_id:
            return True
    return False


def _collect_reveal_events(scene_spec: Any) -> list[RevealEvent]:
    events: list[RevealEvent] = []
    for animation_index, anim in enumerate(getattr(scene_spec, "animations", []) or []):
        action = getattr(getattr(anim, "action", None), "value", getattr(anim, "action", None))
        if action not in {"appear", "fade-in", "draw", "type", "replace"}:
            continue
        start_seconds = parse_duration(getattr(anim, "at", None) or "0s")
        duration_seconds = parse_duration(getattr(anim, "duration", None) or "0s")
        target = getattr(anim, "target", None)
        target_ids = [target] if isinstance(target, str) else list(target or [])
        if action == "replace":
            with_id = getattr(anim, "with_id", None)
            if with_id:
                target_ids.append(with_id)
        for object_id in target_ids:
            if not object_id:
                continue
            events.append(
                RevealEvent(
                    object_id=object_id,
                    action=action,
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    animation_index=animation_index,
                )
            )
    return events


def _collect_scene_object_ids(objects: list[Any]) -> set[str]:
    object_ids: set[str] = set()
    for obj in objects:
        object_id = getattr(obj, "id", None)
        if object_id:
            object_ids.add(object_id)
        object_ids.update(_collect_scene_object_ids(getattr(obj, "children", None) or []))
    return object_ids


def _incoming_scene_fade_duration(previous_scene_spec: Any | None) -> float:
    if previous_scene_spec is None or getattr(previous_scene_spec, "transition", None) is None:
        return 0.0
    return parse_duration(getattr(previous_scene_spec.transition, "duration", "0s"))


def _object_parent_map(objects: list[Any]) -> dict[str, str | None]:
    parent_map: dict[str, str | None] = {}

    def walk(nodes: list[Any], parent_id: str | None) -> None:
        for node in nodes:
            node_id = getattr(node, "id", None)
            if node_id:
                parent_map[node_id] = parent_id
            walk(getattr(node, "children", None) or [], node_id)

    walk(objects, None)
    return parent_map


def _gradual_reveal_overlap(left: RevealEvent, right: RevealEvent) -> bool:
    if not (_is_gradual_reveal(left) or _is_gradual_reveal(right)):
        return False
    overlap_seconds = min(left.end_seconds, right.end_seconds) - max(
        left.start_seconds, right.start_seconds
    )
    if overlap_seconds >= _DOUBLE_REVEAL_OVERLAP_SECONDS:
        return True
    return abs(left.start_seconds - right.start_seconds) <= _DOUBLE_REVEAL_HOLD_WINDOW_SECONDS


def _is_gradual_reveal(event: RevealEvent) -> bool:
    return event.action != "appear" or event.duration_seconds > 0


def _connector_reference_findings(
    scene_id: str,
    object_ref: ObjectRef,
    available_ids: set[str],
) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for endpoint_field, endpoint_value in (
        ("from", object_ref.spec.from_id),
        ("to", object_ref.spec.to_id),
    ):
        if endpoint_value and endpoint_value in available_ids:
            continue
        missing_target = endpoint_value or "<missing>"
        findings.append(
            CheckFinding(
                severity="error",
                scene_id=scene_id,
                kind="reference",
                message=(
                    f"Connector `{object_ref.object_id}` has an invalid `{endpoint_field}` endpoint "
                    f"({missing_target!r})."
                ),
                recommended_edit=RecommendedEdit(
                    scene_id=scene_id,
                    action="fix_connector_endpoint",
                    object_id=object_ref.object_id,
                    field=f"{object_ref.path}.{endpoint_field}",
                    suggested_value=_closest_id_suggestion(endpoint_value, available_ids),
                    reason="Connectors need valid source and destination IDs to render correctly.",
                ),
            )
        )
    return findings


def _serialize_findings(findings: list[CheckFinding]) -> list[str]:
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return [
        finding.to_message()
        for finding in sorted(
            findings,
            key=lambda finding: (
                severity_order.get(finding.severity.lower(), 99),
                finding.scene_id or "",
                finding.kind,
                finding.message,
            ),
        )
    ]


def _finding_category(finding: CheckFinding) -> str:
    if finding.severity.lower() == "error":
        return "blocking"
    if finding.kind.startswith("voice_sync"):
        return "voice_sync"
    if finding.kind.startswith("continuity"):
        return "continuity"
    return "quality"


def _group_serialized_findings(findings: list[CheckFinding]) -> dict[str, list[str]]:
    grouped = {"blocking": [], "quality": [], "voice_sync": [], "continuity": []}
    for finding in sorted(
        findings,
        key=lambda item: (
            0 if item.severity.lower() == "error" else 1,
            item.scene_id or "",
            item.kind,
            item.message,
        ),
    ):
        grouped[_finding_category(finding)].append(finding.to_message())
    return grouped


def _recommended_edits_from_findings(
    findings: list[CheckFinding],
) -> list[dict[str, str | int | float | bool | None]]:
    edits = [
        finding.recommended_edit for finding in findings if finding.recommended_edit is not None
    ]
    return [edit.to_dict() for edit in _dedupe_recommended_edits(edits)]


def _recommend_edits_from_messages(
    messages: list[str | dict[str, Any] | RecommendedEdit],
) -> list[dict[str, str | int | float | bool | None]]:
    normalized = _normalize_recommended_edits(
        [message for message in messages if not isinstance(message, str)]
    )
    if normalized:
        return normalized

    recommendations: list[RecommendedEdit] = []
    joined = "\n".join(
        message if isinstance(message, str) else json.dumps(message, sort_keys=True)
        for message in messages
    ).lower()
    if "overlap" in joined:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="reduce_scene_density",
                object_id=None,
                field=None,
                suggested_value=None,
                reason="Reduce the number of visible elements or switch to a simpler layout.",
            )
        )
    if "clipping" in joined or "outside the canvas" in joined:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="shorten_text",
                object_id=None,
                field="content",
                suggested_value=None,
                reason="Shorten the visible copy or split it across multiple beats so it fits the canvas.",
            )
        )
    if "unknown theme" in joined:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="replace_theme",
                object_id=None,
                field="meta.theme",
                suggested_value="modern",
                reason="Use a built-in theme or create one with add_theme before rendering.",
            )
        )
    if "invalid duration" in joined:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="retime_scene",
                object_id=None,
                field="duration",
                suggested_value="0.8s",
                reason="Use duration strings like `0.8s` or `300ms`.",
            )
        )
    if "file not found" in joined:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="fix_file_path",
                object_id=None,
                field="file_path",
                suggested_value=None,
                reason="Point the tool at an existing workspace-relative or absolute path.",
            )
        )
    if not recommendations:
        recommendations.append(
            RecommendedEdit(
                scene_id=None,
                action="review_document",
                object_id=None,
                field=None,
                suggested_value=None,
                reason="Start from the nearest starter pattern and re-run check_animation after edits.",
            )
        )
    return [
        recommendation.to_dict() for recommendation in _dedupe_recommended_edits(recommendations)
    ]


def _normalize_recommended_edits(
    edits: list[str | dict[str, Any] | RecommendedEdit],
) -> list[dict[str, str | int | float | bool | None]]:
    normalized: list[RecommendedEdit] = []
    for edit in edits:
        if isinstance(edit, RecommendedEdit):
            normalized.append(edit)
            continue
        if isinstance(edit, dict):
            required_keys = {
                "scene_id",
                "action",
                "object_id",
                "field",
                "suggested_value",
                "reason",
            }
            if required_keys <= edit.keys():
                normalized.append(
                    RecommendedEdit(
                        scene_id=edit.get("scene_id"),
                        action=str(edit.get("action")),
                        object_id=edit.get("object_id"),
                        field=edit.get("field"),
                        suggested_value=edit.get("suggested_value"),
                        reason=str(edit.get("reason")),
                    )
                )
            continue
        if isinstance(edit, str) and edit.strip():
            normalized.append(
                RecommendedEdit(
                    scene_id=None,
                    action="review_document",
                    object_id=None,
                    field=None,
                    suggested_value=None,
                    reason=edit.strip(),
                )
            )
    return [edit.to_dict() for edit in _dedupe_recommended_edits(normalized)]


def _dedupe_recommended_edits(edits: list[RecommendedEdit]) -> list[RecommendedEdit]:
    seen: set[
        tuple[str | None, str, str | None, str | None, str | int | float | bool | None, str]
    ] = set()
    deduped: list[RecommendedEdit] = []
    for edit in edits:
        key = (
            edit.scene_id,
            edit.action,
            edit.object_id,
            edit.field,
            edit.suggested_value,
            edit.reason,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edit)
    return deduped


def _apply_safe_write_back_fixes(
    doc: Any,
    findings: list[CheckFinding],
) -> tuple[Any, list[dict[str, Any]]]:
    raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
    applied_fixes: list[dict[str, Any]] = []

    target_ids = {
        finding.recommended_edit.object_id
        for finding in findings
        if finding.kind == "visibility"
        and finding.recommended_edit is not None
        and finding.recommended_edit.action == "enable_layout_group_visibility"
        and finding.recommended_edit.object_id
    }
    for scene_index, scene in enumerate(raw_doc.get("scenes", []) or []):
        scene_id = scene.get("id") or f"scene_{scene_index}"
        for obj in scene.get("objects", []) or []:
            applied_fixes.extend(
                _enable_safe_group_visibility(obj, scene_id=scene_id, target_ids=target_ids)
            )

    if not applied_fixes:
        return doc, applied_fixes
    return parse_string(json.dumps(raw_doc), format="json"), applied_fixes


def _enable_safe_group_visibility(
    obj: dict[str, Any],
    *,
    scene_id: str,
    target_ids: set[str],
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    object_id = obj.get("id")
    children = obj.get("children")
    if (
        object_id in target_ids
        and obj.get("type") == "group"
        and isinstance(children, list)
        and children
        and not obj.get("content")
        and obj.get("visible") is not True
    ):
        obj["visible"] = True
        applied.append(
            {
                "scene_id": scene_id,
                "object_id": object_id,
                "action": "enable_layout_group_visibility",
                "field": "visible",
                "value": True,
                "reason": "Enabled `visible: true` on a layout-only parent group so animated children can appear.",
            }
        )

    for child in children or []:
        if isinstance(child, dict):
            applied.extend(
                _enable_safe_group_visibility(child, scene_id=scene_id, target_ids=target_ids)
            )
    return applied


def _collect_object_refs(objects: list[Any], *, prefix: str) -> list[ObjectRef]:
    refs: list[ObjectRef] = []
    for index, obj in enumerate(objects):
        path = f"{prefix}[{index}]"
        refs.append(ObjectRef(object_id=getattr(obj, "id", None), path=path, spec=obj))
        refs.extend(
            _collect_object_refs(getattr(obj, "children", None) or [], prefix=f"{path}.children")
        )
    return refs


def _available_ids(refs: list[ObjectRef]) -> set[str]:
    return {ref.object_id for ref in refs if ref.object_id}


def _layout_recommendation(scene: Any, finding: Any) -> RecommendedEdit:
    node_map = getattr(scene, "node_map", {})
    for node_id in getattr(finding, "node_ids", ()):
        node = node_map.get(node_id)
        if node is None:
            continue
        if getattr(node, "content", None):
            return RecommendedEdit(
                scene_id=scene.id,
                action="shorten_text",
                object_id=node_id,
                field="content",
                suggested_value=None,
                reason="This text-heavy element is the likeliest source of the layout issue.",
            )
    return RecommendedEdit(
        scene_id=scene.id,
        action="retime_scene",
        object_id=None,
        field="duration",
        suggested_value=_format_duration_value(
            min(
                _MAX_SCENE_DURATION_SECONDS,
                max(_MIN_SCENE_DURATION_SECONDS, scene.duration + 1.0),
            )
        ),
        reason="Give the scene a little more breathing room or split it into smaller beats.",
    )


def _estimate_read_time_seconds(text: str) -> float:
    words = len(re.findall(r"\b[\w'-]+\b", text))
    if words == 0:
        return 0.0
    return words / (_READ_TIME_WORDS_PER_MINUTE / 60.0)


def _find_redundant_text_ref(scene_refs: list[ObjectRef], narration: str) -> ObjectRef | None:
    narration_tokens = _tokenize_for_overlap(narration)
    if len(narration_tokens) < _REDUNDANCY_WORD_THRESHOLD:
        return None

    best_match: tuple[float, ObjectRef] | None = None
    for object_ref in scene_refs:
        content = (getattr(object_ref.spec, "content", None) or "").strip()
        if not content or object_ref.spec.type == ObjectType.CONNECTOR:
            continue
        style = (getattr(object_ref.spec, "style", None) or "").strip()
        if style in {"heading", "section-heading", "code"}:
            continue
        content_tokens = _tokenize_for_overlap(content)
        if len(content_tokens) < _REDUNDANCY_WORD_THRESHOLD:
            continue
        overlap = _token_overlap_ratio(content_tokens, narration_tokens)
        similarity = SequenceMatcher(
            None, " ".join(content_tokens), " ".join(narration_tokens)
        ).ratio()
        score = max(overlap, similarity)
        if overlap < _REDUNDANCY_TOKEN_OVERLAP and similarity < _REDUNDANCY_SEQUENCE_SIMILARITY:
            continue
        if best_match is None or score > best_match[0]:
            best_match = (score, object_ref)
    return best_match[1] if best_match else None


def _narration_timing_advice(doc: Any) -> list[dict[str, Any]]:
    advice: list[dict[str, Any]] = []
    for scene_index, scene in enumerate(doc.scenes):
        narration = (getattr(scene, "narration", None) or "").strip()
        if not narration:
            continue
        current_duration = getattr(scene, "duration", "0s")
        if current_duration == "auto":
            current_seconds = estimate_scene_duration(
                scene.model_dump(mode="json", by_alias=True, exclude_none=True)
            )
        else:
            current_seconds = parse_duration(current_duration)
        estimated_seconds = _estimate_read_time_seconds(narration)
        suggested_seconds = _round_up_duration_seconds(max(current_seconds, estimated_seconds))
        advice.append(
            {
                "scene_id": getattr(scene, "id", None) or f"scene_{scene_index}",
                "current_duration_seconds": round(current_seconds, 2),
                "estimated_read_time_seconds": round(estimated_seconds, 2),
                "suggested_duration_seconds": round(suggested_seconds, 2),
                "suggested_duration": _format_duration_value(suggested_seconds),
                "needs_review": (
                    estimated_seconds > current_seconds * _NARRATION_OVERAGE_RATIO
                    and estimated_seconds - current_seconds >= _NARRATION_OVERAGE_SECONDS
                ),
            }
        )
    return advice


def _round_up_duration_seconds(value: float) -> float:
    return max(0.5, math.ceil(value * 2.0) / 2.0)


def _planner_draft_outline(topic: str | None) -> list[dict[str, str]]:
    subject = (topic or "the concept").strip()
    lowered = subject.lower()
    mechanism_title = f"How {subject} moves through the system"
    if lowered.startswith("how "):
        mechanism_title = subject[0].upper() + subject[1:]
    return [
        {
            "scene_id": "problem",
            "purpose": "Show the pain or confusion first so the viewer cares.",
            "suggested_title": f"Why {subject} matters",
        },
        {
            "scene_id": "entry",
            "purpose": "Show what enters the system or where the process begins.",
            "suggested_title": f"Where {subject} begins",
        },
        {
            "scene_id": "flow",
            "purpose": "Walk through the step-by-step state flow with the main diagram.",
            "suggested_title": mechanism_title,
        },
        {
            "scene_id": "outcome",
            "purpose": "Close with the outcome, benefit, or mental model to remember.",
            "suggested_title": f"The outcome for {subject}",
        },
    ]


def _reference_example_excerpt(filename: str, *, max_lines: int = 22) -> str:
    root = Path(__file__).resolve().parents[3]
    lines = (root / "examples" / "reference" / filename).read_text(encoding="utf-8").splitlines()
    excerpt = lines[:max_lines]
    if len(lines) > max_lines:
        excerpt.append("...")
    return "\n".join(excerpt)


def _tokenize_for_overlap(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _token_overlap_ratio(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    right_counts: dict[str, int] = {}
    for token in right:
        right_counts[token] = right_counts.get(token, 0) + 1
    matches = 0
    for token in left:
        remaining = right_counts.get(token, 0)
        if remaining <= 0:
            continue
        matches += 1
        right_counts[token] = remaining - 1
    return matches / len(left)


def _normalized_animation_targets(target: str | list[str] | None) -> list[str]:
    if isinstance(target, str):
        return [target]
    if isinstance(target, list):
        return [item for item in target if isinstance(item, str)]
    return []


def _closest_id_suggestion(target_id: str | None, available_ids: set[str]) -> str | None:
    if not target_id or not available_ids:
        return None
    matches = get_close_matches(target_id, sorted(available_ids), n=1, cutoff=0.55)
    return matches[0] if matches else None


def _format_duration_value(seconds: float) -> str:
    rounded = round(seconds, 1)
    if rounded.is_integer():
        return f"{int(rounded)}s"
    return f"{rounded:.1f}s"


def _rects_materially_aligned(left: Any, right: Any) -> bool:
    return (
        abs(left.x - right.x) <= 8.0
        and abs(left.y - right.y) <= 8.0
        and abs(left.width - right.width) <= 8.0
        and abs(left.height - right.height) <= 8.0
    )


def _check_summary(*, blocking_count: int, warning_count: int) -> str:
    if blocking_count == 0 and warning_count == 0:
        return "Kaivra validation and audit passed cleanly."
    if blocking_count == 0:
        suffix = "warning" if warning_count == 1 else "warnings"
        return f"Kaivra validation passed with {warning_count} {suffix} to review."
    return "Kaivra found blocking issues to review before final rendering."


def _command_available(command: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if executable is None:
        return False, f"{command} was not found on PATH."

    proc = subprocess.run(
        [executable, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        return False, f"{command} exists but could not run cleanly."
    return True, f"{command} is available at {executable}."


def _platform_fix_commands() -> dict[str, list[str]]:
    system = platform.system().lower()
    if system == "darwin":
        cairo_cmd = "brew install cairo pkg-config"
        ffmpeg_cmd = "brew install ffmpeg"
    else:
        cairo_cmd = "sudo apt install libcairo2-dev pkg-config"
        ffmpeg_cmd = "sudo apt install ffmpeg"

    return {
        "python_package": [
            "Install the repo in a virtualenv with `python -m pip install -e '.[dev]'`.",
        ],
        "pycairo": [
            cairo_cmd,
            "Then reinstall the Python package with `python -m pip install -e '.[dev]'`.",
        ],
        "ffmpeg": [ffmpeg_cmd],
        "ffprobe": [ffmpeg_cmd],
    }


def _issue(title: str, detail: str, fix_steps: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "detail": detail,
        "fix_steps": fix_steps,
    }


def _doctor_hint_path() -> Path:
    override = os.environ.get(_DOCTOR_HINT_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return _DEFAULT_DOCTOR_HINT_PATH


def _download_file(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url) as response, destination.open("wb") as dst:
        shutil.copyfileobj(response, dst)


def _extract_tarball(archive_path: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="kaivra_extract_") as tmpdir:
        extract_root = Path(tmpdir)
        with tarfile.open(archive_path) as archive:
            archive.extractall(extract_root, filter="data")

        entries = [path for path in extract_root.iterdir()]
        source_root = extract_root
        if len(entries) == 1 and entries[0].is_dir():
            source_root = entries[0]

        for child in source_root.iterdir():
            target = destination / child.name
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                shutil.copy2(child, target)


def _resolve_local_model_paths(model_dir: str | Path) -> tuple[Path, Path, Path]:
    root = Path(model_dir).expanduser().resolve()
    if root.is_file():
        root = root.parent

    model_candidates = sorted(root.glob("*.onnx"))
    if not model_candidates:
        raise FileNotFoundError(f"No .onnx model file found in {root}")

    tokens_path = root / "tokens.txt"
    if not tokens_path.exists():
        raise FileNotFoundError(f"tokens.txt not found in {root}")

    data_dir = root / "espeak-ng-data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"espeak-ng-data directory not found in {root}")

    return model_candidates[0], tokens_path, data_dir


def _resolve_mcp_client(client: str) -> str:
    chosen = client.lower()
    if chosen == "auto":
        if _DEFAULT_CLAUDE_CONFIG_PATH.exists():
            return "claude-code"
        if _DEFAULT_CURSOR_CONFIG_PATH.exists() or _DEFAULT_CURSOR_CONFIG_PATH.parent.exists():
            return "cursor"
        return "claude-code"
    if chosen not in {"claude-code", "cursor"}:
        raise ValueError("client must be one of: auto, claude-code, cursor.")
    return chosen


def _config_path_for_client(client: str) -> Path:
    if client == "claude-code":
        return _DEFAULT_CLAUDE_CONFIG_PATH
    return _DEFAULT_CURSOR_CONFIG_PATH


def _mcp_server_entry(command: str) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": command,
        "args": [],
    }


def _resolve_mcp_server_command() -> str:
    command = _safe_resolve_mcp_server_command()
    if command is not None:
        return command
    raise ValueError(
        "Could not find the `kaivra-mcp` executable. Reinstall the repo in the active virtualenv first."
    )


def _safe_resolve_mcp_server_command() -> str | None:
    sibling = Path(sys.executable).resolve().with_name("kaivra-mcp")
    if sibling.exists():
        return str(sibling)

    discovered = shutil.which("kaivra-mcp")
    if discovered:
        return discovered
    return None


def _has_explanatory_language(narration: str) -> bool:
    lowered = narration.lower()
    return any(marker in lowered for marker in _EXPLANATION_MARKERS)


def _scene_needs_explanatory_narration(scene_refs: list[ObjectRef], narration: str) -> bool:
    scene_text = " ".join(filter(None, (_object_ref_text(ref) for ref in scene_refs)))
    combined = f"{scene_text} {narration}".lower()
    if re.search(r"\d+(?:\.\d+)?\s*[=+*/-]\s*\d+(?:\.\d+)?", combined):
        return True
    return any(marker in combined for marker in _MECHANICAL_SCENE_MARKERS)


def _object_ref_text(ref: ObjectRef) -> str:
    spec = ref.spec
    parts: list[str] = []
    for field_name in ("content", "label"):
        value = getattr(spec, field_name, None)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts)
