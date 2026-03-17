"""Workspace operations shared by the Kaivra MCP server and CLI."""

from __future__ import annotations

import importlib
import json
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaivra.audio.mux import mux_audio
from kaivra.audio.timings import load_audio_timing_data
from kaivra.dsl.parser import parse_file, parse_string
from kaivra.dsl.retime import retime_document_to_audio_timings
from kaivra.mcp.blueprints import (
    build_starter_document,
    dump_document_json,
    infer_slug,
)
from kaivra.qa.audit import audit_scene_graph
from kaivra.render.cairo_renderer import CairoRenderer
from kaivra.render.video.exporter import export_video
from kaivra.render.web.exporter import write_web_preview
from kaivra.scene_graph.builder import build_scene_graph
from kaivra.themes.registry import (
    get_theme,
    theme_field_names,
    theme_from_dict,
    write_theme_file,
)

ProgressReporter = Callable[[float, str], None]


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

    def start_animation(
        self,
        *,
        title: str,
        pattern: str | None,
        beats: list[Any] | None,
        theme: str | None,
        audience: str | None,
        include_narration: bool,
        slug: str | None,
    ) -> dict[str, Any]:
        """Create a starter animation file and return the normalized JSON."""
        chosen_theme = theme or "modern"
        self._resolve_theme(chosen_theme)
        doc = build_starter_document(
            title=title,
            pattern=pattern,
            beats=beats,
            theme=chosen_theme,
            audience=audience,
            include_narration=include_narration,
        )
        chosen_slug = infer_slug(slug or title)
        self.paths.animations_dir.mkdir(parents=True, exist_ok=True)
        path = self._unique_path(self.paths.animations_dir / f"{chosen_slug}.json")
        dsl_json = dump_document_json(doc)
        path.write_text(dsl_json + "\n", encoding="utf-8")

        return {
            "file_path": str(path),
            "dsl_json": dsl_json,
            "defaults": {
                "theme": doc.meta.theme,
                "resolution": list(doc.meta.resolution),
                "fps": doc.meta.fps,
                "show_narration": doc.meta.show_narration,
                "continuity": doc.meta.continuity,
            },
            "next_step": "Run check_animation on the created file before previewing or rendering.",
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
            "next_step": f"Use theme: {chosen_name} in start_animation or set meta.theme to {chosen_name}.",
        }

    def check_animation(
        self,
        *,
        file_path: str | None = None,
        dsl_json: str | None = None,
        write_back: bool = False,
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
                "normalized_dsl_json": None,
                "recommended_edits": _recommend_edits_from_messages([str(exc)]),
                "file_path": str(self.resolve_path(file_path)) if file_path else None,
            }

        try:
            normalized = dump_document_json(doc)
            findings = _audit_document(doc, theme_search_roots=[self.paths.themes_dir])
        except Exception as exc:
            return {
                "valid": False,
                "summary": "Kaivra could parse the document, but follow-up checks failed.",
                "blocking_issues": [str(exc)],
                "warnings": [],
                "audit_findings": [],
                "normalized_dsl_json": None,
                "recommended_edits": _recommend_edits_from_messages([str(exc)]),
                "file_path": str(resolved_path) if resolved_path else None,
            }

        blocking = [finding for finding in findings if finding.startswith("ERROR")]
        warnings = [finding for finding in findings if not finding.startswith("ERROR")]

        if write_back:
            if resolved_path is None:
                raise ValueError("write_back requires file_path.")
            resolved_path.write_text(normalized + "\n", encoding="utf-8")

        return {
            "valid": not blocking,
            "summary": (
                "Kaivra validation and audit passed."
                if not blocking and not warnings
                else "Kaivra found issues to review before final rendering."
            ),
            "blocking_issues": blocking,
            "warnings": warnings,
            "audit_findings": findings,
            "normalized_dsl_json": normalized,
            "recommended_edits": _recommend_edits_from_messages(blocking + warnings),
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

        self.paths.previews_dir.mkdir(parents=True, exist_ok=True)
        html_path = self.paths.previews_dir / f"{base_name}.html"
        png_path = self.paths.previews_dir / f"{base_name}.png"

        write_web_preview(doc, html_path)
        graph, theme = _build_render_graph(doc, theme_search_roots=[self.paths.themes_dir])
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
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        """Render an animation artifact into the workspace."""
        chosen_format = format.lower()
        if chosen_format not in {"png", "mp4", "webm"}:
            raise ValueError("format must be one of: png, mp4, webm.")

        doc, resolved_path = self._load_document(file_path=file_path)
        audio_abs = self._resolve_existing_path(audio_path) if audio_path else None
        audio_timings_abs = (
            self._resolve_existing_path(audio_timings_path)
            if audio_timings_path
            else None
        )

        self.paths.renders_dir.mkdir(parents=True, exist_ok=True)
        base_name = infer_slug(output_name or resolved_path.stem)
        artifact_path = self.paths.renders_dir / f"{base_name}.{chosen_format}"

        if chosen_format == "png":
            if audio_abs or audio_timings_abs:
                raise ValueError("PNG renders do not accept audio_path or audio_timings_path.")
            if progress is not None:
                progress(0.2, "Building the first frame.")
            graph, theme = _build_render_graph(doc, theme_search_roots=[self.paths.themes_dir])
            CairoRenderer(theme).render_frame_to_file(graph, 0.0, str(artifact_path))
            if progress is not None:
                progress(1.0, "PNG render complete.")
            return {
                "status": "ok",
                "artifact_path": str(artifact_path),
                "duration_seconds": 0.0,
                "warnings": [],
                "source_file_path": str(resolved_path),
            }

        if progress is not None:
            progress(0.1, "Preparing the scene graph.")
        graph, theme = _build_render_graph(
            doc,
            audio_timings_path=audio_timings_abs,
            theme_search_roots=[self.paths.themes_dir],
        )

        def video_progress(done: int, total: int) -> None:
            if progress is None or total <= 0:
                return
            progress(0.15 + (done / total) * 0.75, "Rendering video frames.")

        if audio_abs:
            if progress is not None:
                progress(0.15, "Rendering a silent video before muxing audio.")
            with tempfile.NamedTemporaryFile(
                prefix=f"{artifact_path.stem}_silent_",
                suffix=f".{chosen_format}",
                dir=self.paths.renders_dir,
                delete=False,
            ) as tmp:
                silent_path = Path(tmp.name)

            try:
                export_video(
                    graph,
                    theme,
                    str(silent_path),
                    fps=doc.meta.fps,
                    log_progress=False,
                    progress_callback=video_progress,
                )
                if progress is not None:
                    progress(0.92, "Muxing the external audio track.")
                mux_audio(str(silent_path), str(audio_abs), str(artifact_path))
            finally:
                silent_path.unlink(missing_ok=True)
        else:
            export_video(
                graph,
                theme,
                str(artifact_path),
                fps=doc.meta.fps,
                log_progress=False,
                progress_callback=video_progress,
            )

        if progress is not None:
            progress(1.0, "Video render complete.")
        warnings: list[str] = []
        if audio_timings_abs and not audio_abs:
            warnings.append("Applied audio timings for pacing, but no audio track was attached.")

        return {
            "status": "ok",
            "artifact_path": str(artifact_path),
            "duration_seconds": round(graph.total_duration, 2),
            "warnings": warnings,
            "source_file_path": str(resolved_path),
        }

    def run_doctor(self) -> dict[str, Any]:
        """Check that the local machine can run the Kaivra MCP workflow."""
        issues: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def add_check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": ok, "detail": detail})

        python_ok = True
        try:
            importlib.import_module("kaivra")
            add_check("python_package", True, "Kaivra imports successfully.")
        except Exception as exc:
            python_ok = False
            add_check("python_package", False, f"Kaivra import failed: {exc}")
            issues.append(_issue("python_package", str(exc), _platform_fix_commands()["python_package"]))

        cairo_ok = True
        try:
            importlib.import_module("cairo")
            add_check("pycairo", True, "pycairo imports successfully.")
        except Exception as exc:
            cairo_ok = False
            add_check("pycairo", False, f"pycairo import failed: {exc}")
            issues.append(_issue("pycairo", str(exc), _platform_fix_commands()["pycairo"]))

        ffmpeg_ok, ffmpeg_detail = _command_available("ffmpeg")
        add_check("ffmpeg", ffmpeg_ok, ffmpeg_detail)
        if not ffmpeg_ok:
            issues.append(_issue("ffmpeg", ffmpeg_detail, _platform_fix_commands()["ffmpeg"]))

        ffprobe_ok, ffprobe_detail = _command_available("ffprobe")
        add_check("ffprobe", ffprobe_ok, ffprobe_detail)
        if not ffprobe_ok:
            issues.append(_issue("ffprobe", ffprobe_detail, _platform_fix_commands()["ffprobe"]))

        workspace_ok = True
        try:
            tmp = tempfile.NamedTemporaryFile(dir=self.root, prefix=".kaivra_mcp_", delete=True)
            tmp.close()
            add_check("workspace_write", True, f"Workspace {self.root} is writable.")
        except Exception as exc:
            workspace_ok = False
            add_check("workspace_write", False, f"Workspace is not writable: {exc}")
            issues.append(_issue("workspace_write", str(exc), ["Use a writable local workspace."]))

        if python_ok and cairo_ok and ffmpeg_ok and ffprobe_ok and workspace_ok:
            try:
                smoke_doc = build_starter_document(
                    title="Doctor Smoke Test",
                    pattern="process_explainer",
                    beats=["Goal: Verify the local Kaivra install."],
                    theme="modern",
                    audience=None,
                    include_narration=False,
                )
                graph, theme = _build_render_graph(
                    smoke_doc,
                    theme_search_roots=[self.paths.themes_dir],
                )
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    smoke_path = Path(tmp.name)
                try:
                    CairoRenderer(theme).render_frame_to_file(graph, 0.0, str(smoke_path))
                    add_check("smoke_render", True, "Validated a starter document and rendered a smoke-test PNG.")
                finally:
                    smoke_path.unlink(missing_ok=True)
            except Exception as exc:
                add_check("smoke_render", False, f"Smoke render failed: {exc}")
                issues.append(_issue("smoke_render", str(exc), ["Run `kaivra validate` on a sample file and check the local install."]))
        else:
            add_check("smoke_render", False, "Skipped until Python, Cairo, ffmpeg, and workspace checks pass.")

        return {
            "ok": not issues,
            "workspace_root": str(self.root),
            "checks": checks,
            "issues": issues,
            "next_steps": [
                "Run `claude mcp add kaivra -- kaivra-mcp` after the doctor is green.",
                "Then ask Claude Code to create a short animation and let it call `start_animation` first.",
            ],
            "claude_code": {
                "command": "kaivra-mcp",
                "args": [],
                "config_json": json.dumps(
                    {
                        "mcpServers": {
                            "kaivra": {
                                "command": "kaivra-mcp",
                                "args": [],
                            }
                        }
                    },
                    indent=2,
                ),
                "add_command": "claude mcp add kaivra -- kaivra-mcp",
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
        return get_theme(name, search_roots=[self.paths.themes_dir])

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
            "Claude Code:",
            f"- Add command: {report['claude_code']['add_command']}",
            "- Manual config:",
            report["claude_code"]["config_json"],
        ]
    )
    return "\n".join(lines)


def _build_render_graph(
    doc: Any,
    audio_timings_path: Path | None = None,
    *,
    theme_search_roots: list[Path] | None = None,
) -> tuple[Any, Any]:
    if audio_timings_path is not None:
        raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
        timing_data = load_audio_timing_data(audio_timings_path)
        retimed = retime_document_to_audio_timings(raw_doc, timing_data)
        doc = parse_string(json.dumps(retimed), format="json")

    theme = get_theme(doc.meta.theme, search_roots=theme_search_roots)
    graph = build_scene_graph(doc, theme)
    return graph, theme


def _audit_document(doc: Any, *, theme_search_roots: list[Path] | None = None) -> list[str]:
    theme = get_theme(doc.meta.theme, search_roots=theme_search_roots)
    graph = build_scene_graph(doc, theme)
    findings = audit_scene_graph(graph, samples_per_scene=4)
    result: list[str] = []
    for finding in findings:
        result.append(
            f"{finding.severity.upper()} {finding.scene_id}@{finding.time_seconds:.2f}s "
            f"{finding.kind}: {finding.message}"
        )
    return result


def _recommend_edits_from_messages(messages: list[str]) -> list[str]:
    if not messages:
        return []

    recommendations: list[str] = []
    joined = "\n".join(messages).lower()
    if "overlap" in joined:
        recommendations.append("Reduce the number of objects in the crowded scene or switch to one-column/two-column templates.")
    if "clipping" in joined or "outside the canvas" in joined:
        recommendations.append("Shorten long text, split copy into multiple text lines, or reduce the number of side-by-side elements.")
    if "unknown theme" in joined:
        recommendations.append("Use a built-in theme like modern/whiteboard, or create a custom one with add_theme.")
    if "invalid duration" in joined:
        recommendations.append("Use duration strings like '0.8s' or '300ms'.")
    if "file not found" in joined:
        recommendations.append("Pass a workspace-relative path or an absolute file path that already exists.")
    if not recommendations:
        recommendations.append("Start from the nearest starter pattern and re-run check_animation after edits.")
    return recommendations


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
