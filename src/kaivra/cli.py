"""CLI entry point for kaivra."""

from __future__ import annotations

import json
from pathlib import Path

import click
from click.core import ParameterSource


@click.group()
@click.version_option(version="0.1.0")
def main():
    """kaivra: Declarative animation engine for LLMs."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
def validate(input_file: str):
    """Validate a DSL file (JSON or YAML)."""
    from kaivra.dsl.parser import parse_file

    try:
        doc = parse_file(input_file)
        click.echo(f"Valid! {len(doc.scenes)} scene(s), theme: {doc.meta.theme}")
    except Exception as exc:
        raise click.ClickException(f"Validation error: {exc}") from exc


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Print the doctor report as JSON.")
def doctor(as_json: bool):
    """Check the local Kaivra install and print setup guidance."""
    from kaivra.mcp.workspace import KaivraWorkspace, format_doctor_report

    report = KaivraWorkspace().run_doctor()
    if as_json:
        click.echo(json.dumps(report, indent=2))
        return
    click.echo(format_doctor_report(report))


@main.command("download-model")
@click.option(
    "--model-name",
    default="vits-piper-en_US-amy-low",
    show_default=True,
    help="Sherpa local TTS model bundle to install for `--voice` local narration.",
)
@click.option(
    "--target-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Destination directory for the model bundle. Defaults to ~/.kaivra/models/<model-name>.",
)
@click.option(
    "--force", is_flag=True, help="Redownload and replace an existing local model directory."
)
def download_model(model_name: str, target_dir: Path | None, force: bool):
    """Download a local Sherpa TTS model bundle into ~/.kaivra/models/<model-name>."""
    from kaivra.mcp.workspace import KaivraWorkspace

    workspace = KaivraWorkspace()
    _run_preflight(
        workspace,
        "download-model",
        needs_cairo=False,
        needs_ffmpeg=False,
        needs_ffprobe=False,
    )
    try:
        result = workspace.download_model(
            model_name=model_name,
            target_dir=target_dir,
            force=force,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    status_line = (
        "Model already installed." if not result["downloaded"] else "Model download complete."
    )
    click.echo(status_line)
    click.echo(f"Model directory: {result['model_dir']}")
    click.echo(f"Model path: {result['model_path']}")
    click.echo(f"Tokens path: {result['tokens_path']}")
    click.echo(f"Data dir: {result['data_dir']}")
    click.echo("Next step: KAIVRA_VOICE_PROVIDER=local kaivra quick-render <file> --voice")


@main.command("mcp-install")
@click.option(
    "--client",
    type=click.Choice(["auto", "claude-code", "cursor"]),
    default="auto",
    show_default=True,
    help="Which local MCP client config to update.",
)
def mcp_install(client: str):
    """Install a local stdio MCP config entry for Kaivra."""
    from kaivra.mcp.workspace import KaivraWorkspace

    workspace = KaivraWorkspace()
    _run_preflight(
        workspace,
        "mcp-install",
        needs_cairo=False,
        needs_ffmpeg=False,
        needs_ffprobe=False,
    )
    try:
        result = workspace.install_mcp_config(client=client)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Updated {result['client']} MCP config: {result['config_path']}")
    click.echo(f"Command: {result['command']}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", required=True, help="Output file (e.g., output.mp4, output.png)")
@click.option("--fps", default=30, help="Frames per second for video output")
@click.option(
    "--audio",
    type=click.Path(exists=True),
    help="Optional audio file to mux onto the rendered video",
)
@click.option(
    "--audio-timings",
    type=click.Path(exists=True),
    help="Optional JSON sidecar with scene durations or cue timings for retiming",
)
@click.option(
    "--voice", is_flag=True, default=False, help="Generate voice narration from scene text"
)
@click.option(
    "--voice-provider",
    default=None,
    help="Voice provider name (default: KAIVRA_VOICE_PROVIDER or openai)",
)
@click.option("--voice-id", default=None, help="Voice ID passed to the provider")
def render(
    input_file: str,
    output: str,
    fps: int,
    audio: str | None,
    audio_timings: str | None,
    voice: bool,
    voice_provider: str | None,
    voice_id: str | None,
):
    """Render an animation to video or image."""
    from kaivra.mcp.workspace import KaivraWorkspace

    workspace = KaivraWorkspace()
    output_path = Path(output)
    _validate_render_request(
        output_path=output_path,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
    )
    _run_preflight_for_render(
        workspace,
        command_name="render",
        output_path=output_path,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
        voice_provider=voice_provider,
    )
    _render_to_output(
        input_file=input_file,
        output=output,
        fps=fps,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
        voice_provider=voice_provider,
        voice_id=voice_id,
    )


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--serve", is_flag=True, help="Start live reload server")
@click.option("--port", default=8080, help="Server port")
def preview(input_file: str, serve: bool, port: int):
    """Open web preview of an animation."""
    from kaivra.dsl.parser import parse_file
    from kaivra.mcp.workspace import KaivraWorkspace
    from kaivra.render.orchestration import (
        resolve_document_timing_config,
        resolve_theme_search_roots,
    )
    from kaivra.render.web.exporter import export_web_preview

    _run_preflight(
        KaivraWorkspace(),
        "preview",
        needs_cairo=True,
        needs_ffmpeg=False,
        needs_ffprobe=False,
    )
    doc = parse_file(input_file)
    theme_roots = resolve_theme_search_roots(input_file)
    export_web_preview(
        doc,
        serve=serve,
        port=port,
        theme_search_roots=theme_roots,
        timing_config=resolve_document_timing_config(input_file),
    )


@main.command()
def schema():
    """Output JSON Schema for the DSL (for LLM prompting)."""
    from kaivra.dsl.schema import DocumentSpec

    json_schema = DocumentSpec.model_json_schema()
    click.echo(json.dumps(json_schema, indent=2))


@main.command("quick-render")
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    default=None,
    help="Output artifact path. Defaults to artifacts/quick-renders/<name>.<format>.",
)
@click.option(
    "--format",
    "requested_format",
    type=click.Choice(["png", "mp4", "webm"]),
    default=None,
    help="Output format when --output is not provided.",
)
@click.option("--fps", default=30, help="Frames per second for video output")
@click.option(
    "--audio",
    type=click.Path(exists=True),
    help="Optional audio file to mux onto the rendered video",
)
@click.option(
    "--audio-timings",
    type=click.Path(exists=True),
    help="Optional JSON sidecar with scene durations or cue timings for retiming",
)
@click.option(
    "--voice", is_flag=True, default=False, help="Generate voice narration from scene text"
)
@click.option(
    "--voice-provider",
    default=None,
    help="Voice provider name (default: KAIVRA_VOICE_PROVIDER or openai)",
)
@click.option("--voice-id", default=None, help="Voice ID passed to the provider")
def quick_render(
    input_file: str,
    output: str | None,
    requested_format: str | None,
    fps: int,
    audio: str | None,
    audio_timings: str | None,
    voice: bool,
    voice_provider: str | None,
    voice_id: str | None,
):
    """Validate, audit, and render an existing animation in one command."""
    from kaivra.mcp.workspace import KaivraWorkspace

    input_path = Path(input_file).expanduser().resolve()
    workspace = KaivraWorkspace(input_path.parent)
    check = workspace.check_animation(
        file_path=str(input_path),
        voice=voice,
        voice_provider=voice_provider,
    )

    if check["warnings"]:
        for warning in check["warnings"]:
            click.echo(f"Warning: {warning}")

    if not check["valid"]:
        for issue in check["blocking_issues"]:
            click.echo(issue)
        raise click.ClickException(
            "Quick render stopped because the animation has blocking issues."
        )

    output_path = _resolve_quick_render_output(
        str(input_path), output, requested_format, voice, audio
    )
    _validate_render_request(
        output_path=output_path,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
    )
    _run_preflight_for_render(
        workspace,
        command_name="quick-render",
        output_path=output_path,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
        voice_provider=voice_provider,
    )
    _render_to_output(
        input_file=str(input_path),
        output=str(output_path),
        fps=fps,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
        voice_provider=voice_provider,
        voice_id=voice_id,
    )


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--outdir", default="frames", help="Output directory for PNG frames")
@click.option("-n", "--count", default=6, help="Number of random frames to render")
@click.option("--seed", default=None, type=int, help="Random seed for reproducible sampling")
def sample(input_file: str, outdir: str, count: int, seed: int | None):
    """Render a few random frames to PNG for quick iteration."""
    import os
    import random

    from kaivra.dsl.parser import parse_file
    from kaivra.render.cairo_renderer import CairoRenderer
    from kaivra.render.orchestration import (
        build_render_graph,
        resolve_document_timing_config,
        resolve_theme_search_roots,
    )

    doc = parse_file(input_file)
    theme_roots = resolve_theme_search_roots(input_file)
    graph, theme = build_render_graph(
        doc,
        theme_search_roots=theme_roots,
        timing_config=resolve_document_timing_config(input_file),
    )

    if seed is not None:
        random.seed(seed)

    os.makedirs(outdir, exist_ok=True)
    renderer = CairoRenderer(theme)
    for i in range(count):
        t = random.uniform(0.0, graph.total_duration)
        filename = f"frame_{i + 1:02d}_{t:0.2f}s.png"
        path = os.path.join(outdir, filename)
        renderer.render_frame_to_file(graph, t, path)
        click.echo(f"Wrote {path}")


@main.command()
@click.pass_context
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--layout-only",
    is_flag=True,
    help="Run only the sampled layout audit instead of the full validation and audit suite.",
)
@click.option(
    "-n",
    "--samples",
    default=None,
    type=int,
    help="Sample count per scene for `--layout-only` mode.",
)
def audit(ctx: click.Context, input_file: str, layout_only: bool, samples: int | None):
    """Audit an animation with the full check suite by default."""
    from kaivra.dsl.parser import parse_file
    from kaivra.mcp.workspace import KaivraWorkspace
    from kaivra.qa.audit import audit_scene_graph
    from kaivra.render.orchestration import (
        build_render_graph,
        resolve_document_timing_config,
        resolve_theme_search_roots,
    )

    if not layout_only and ctx.get_parameter_source("samples") != ParameterSource.DEFAULT:
        raise click.ClickException("`--samples` is only supported together with `--layout-only`.")

    if not layout_only:
        checked = KaivraWorkspace().check_animation(file_path=str(Path(input_file).resolve()))
        if checked["valid"] and not checked["audit_findings"]:
            click.echo("Audit passed: no issues found.")
            return

        for issue in checked["blocking_issues"]:
            click.echo(issue)
        for warning in checked["warnings"]:
            click.echo(warning)

        if not checked["valid"]:
            raise click.ClickException("Audit found blocking issues.")
        return

    doc = parse_file(input_file)
    theme_roots = resolve_theme_search_roots(input_file)
    graph, _theme = build_render_graph(
        doc,
        theme_search_roots=theme_roots,
        timing_config=resolve_document_timing_config(input_file),
    )
    findings = audit_scene_graph(graph, samples_per_scene=samples or 5)

    if not findings:
        click.echo("Audit passed: no sampled layout issues found.")
        return

    for finding in findings:
        node_text = f" [{', '.join(finding.node_ids)}]" if finding.node_ids else ""
        click.echo(
            f"{finding.severity.upper()} {finding.scene_id}@{finding.time_seconds:.2f}s "
            f"{finding.kind}{node_text}: {finding.message}"
        )

    if any(f.severity == "error" for f in findings):
        raise click.ClickException("Audit found overlap errors.")


class _CliProgressPrinter:
    """Deduplicate stage messages during CLI renders."""

    def __init__(self) -> None:
        self._last_message: str | None = None

    def __call__(self, _progress: float, message: str) -> None:
        if message == self._last_message:
            return
        click.echo(message)
        self._last_message = message


def _run_preflight(
    workspace,
    command_name: str,
    *,
    needs_cairo: bool,
    needs_ffmpeg: bool,
    needs_ffprobe: bool,
) -> None:
    try:
        workspace.preflight_command(
            command_name,
            needs_cairo=needs_cairo,
            needs_ffmpeg=needs_ffmpeg,
            needs_ffprobe=needs_ffprobe,
        )
        hint = workspace.consume_doctor_hint()
        if hint:
            click.echo(hint)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def _run_preflight_for_render(
    workspace,
    *,
    command_name: str,
    output_path: Path,
    audio: str | None,
    audio_timings: str | None,
    voice: bool,
    voice_provider: str | None = None,
) -> None:
    is_video = output_path.suffix.lower() in {".mp4", ".webm"}
    _run_preflight(
        workspace,
        command_name,
        needs_cairo=True,
        needs_ffmpeg=is_video or audio is not None or voice,
        needs_ffprobe=is_video or audio_timings is not None or voice,
    )
    if voice:
        try:
            workspace.validate_voice_setup(voice_provider=voice_provider)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


def _validate_render_request(
    *,
    output_path: Path,
    audio: str | None,
    audio_timings: str | None,
    voice: bool,
) -> None:
    if voice and (audio or audio_timings):
        raise click.ClickException("--voice cannot be combined with --audio or --audio-timings.")

    if output_path.suffix == ".png":
        if audio or audio_timings or voice:
            raise click.ClickException(
                "Audio options are only supported for video outputs (.mp4 or .webm)."
            )
        return

    if output_path.suffix not in {".mp4", ".webm"}:
        raise click.ClickException(f"Unsupported output format: {output_path}")


def _render_to_output(
    *,
    input_file: str,
    output: str,
    fps: int,
    audio: str | None,
    audio_timings: str | None,
    voice: bool,
    voice_provider: str | None,
    voice_id: str | None,
) -> None:
    from kaivra.dsl.parser import parse_file
    from kaivra.render.orchestration import (
        render_document_artifact,
        resolve_document_timing_config,
        resolve_theme_search_roots,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _validate_render_request(
        output_path=output_path,
        audio=audio,
        audio_timings=audio_timings,
        voice=voice,
    )

    doc = parse_file(input_file)
    theme_roots = resolve_theme_search_roots(input_file)
    timing_config = resolve_document_timing_config(input_file)
    progress = _CliProgressPrinter() if voice else None
    try:
        result = render_document_artifact(
            doc,
            output_path=output,
            fps=fps,
            audio_path=audio,
            audio_timings_path=audio_timings,
            voice=voice,
            voice_provider=voice_provider,
            voice_id=voice_id,
            theme_search_roots=theme_roots,
            timing_config=timing_config,
            progress=progress,
            log_video_progress=not voice,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_path.suffix == ".png":
        click.echo(f"Rendered frame to {output}")
    elif voice:
        click.echo(f"Rendered video with voice to {output}")
    else:
        click.echo(f"Rendered video to {output}")

    if result.retimed_document_path:
        click.echo(f"Retimed document: {result.retimed_document_path}")


def _resolve_quick_render_output(
    input_file: str,
    output: str | None,
    requested_format: str | None,
    voice: bool,
    audio: str | None,
) -> Path:
    if output:
        return Path(output)

    chosen_format = requested_format or ("mp4" if voice or audio else "png")
    artifacts_dir = Path("artifacts") / "quick-renders"
    input_path = Path(input_file)
    return artifacts_dir / f"{input_path.stem}.{chosen_format}"


if __name__ == "__main__":
    main()
