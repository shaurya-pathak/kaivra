"""CLI entry point for dsa-anim."""

import click
import json
import tempfile
from pathlib import Path


@click.group()
@click.version_option(version="0.1.0")
def main():
    """dsa-anim: Declarative animation engine for LLMs."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
def validate(input_file: str):
    """Validate a DSL file (JSON or YAML)."""
    from dsa_anim.dsl.parser import parse_file

    try:
        doc = parse_file(input_file)
        click.echo(f"Valid! {len(doc.scenes)} scene(s), theme: {doc.meta.theme}")
    except Exception as exc:
        raise click.ClickException(f"Validation error: {exc}") from exc


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", required=True, help="Output file (e.g., output.mp4, output.png)")
@click.option("--fps", default=30, help="Frames per second for video output")
@click.option("--audio", type=click.Path(exists=True), help="Optional audio file to mux onto the rendered video")
@click.option(
    "--audio-timings",
    type=click.Path(exists=True),
    help="Optional JSON sidecar with scene durations or cue timings for retiming",
)
def render(input_file: str, output: str, fps: int, audio: str | None, audio_timings: str | None):
    """Render an animation to video or image."""
    from dsa_anim.audio.mux import mux_audio
    from dsa_anim.render.cairo_renderer import CairoRenderer
    from dsa_anim.render.video.exporter import export_video

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix == ".png":
        if audio or audio_timings:
            raise click.ClickException(
                "Audio options are only supported for video outputs (.mp4 or .webm)."
            )
        graph, theme = _build_render_graph(input_file, audio_timings)
        renderer = CairoRenderer(theme)
        renderer.render_frame_to_file(graph, 0.0, output)
        click.echo(f"Rendered frame to {output}")
        return

    if output_path.suffix not in {".mp4", ".webm"}:
        raise click.ClickException(f"Unsupported output format: {output}")

    graph, theme = _build_render_graph(input_file, audio_timings)
    if audio:
        with tempfile.NamedTemporaryFile(
            prefix=f"{output_path.stem}_silent_",
            suffix=output_path.suffix,
            dir=output_path.parent,
            delete=False,
        ) as tmp:
            silent_path = tmp.name

        try:
            export_video(graph, theme, silent_path, fps=fps)
            mux_audio(silent_path, audio, output)
        finally:
            Path(silent_path).unlink(missing_ok=True)
    else:
        export_video(graph, theme, output, fps=fps)
    click.echo(f"Rendered video to {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--serve", is_flag=True, help="Start live reload server")
@click.option("--port", default=8080, help="Server port")
def preview(input_file: str, serve: bool, port: int):
    """Open web preview of an animation."""
    from dsa_anim.dsl.parser import parse_file
    from dsa_anim.render.web.exporter import export_web_preview

    doc = parse_file(input_file)
    export_web_preview(doc, serve=serve, port=port)


@main.command()
def schema():
    """Output JSON Schema for the DSL (for LLM prompting)."""
    from dsa_anim.dsl.schema import DocumentSpec

    json_schema = DocumentSpec.model_json_schema()
    click.echo(json.dumps(json_schema, indent=2))


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--outdir", default="frames", help="Output directory for PNG frames")
@click.option("-n", "--count", default=6, help="Number of random frames to render")
@click.option("--seed", default=None, type=int, help="Random seed for reproducible sampling")
def sample(input_file: str, outdir: str, count: int, seed: int | None):
    """Render a few random frames to PNG for quick iteration."""
    import os
    import random

    from dsa_anim.dsl.parser import parse_file
    from dsa_anim.scene_graph.builder import build_scene_graph
    from dsa_anim.themes.registry import get_theme
    from dsa_anim.render.cairo_renderer import CairoRenderer

    doc = parse_file(input_file)
    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)

    if seed is not None:
        random.seed(seed)

    os.makedirs(outdir, exist_ok=True)
    renderer = CairoRenderer(theme)
    for i in range(count):
        t = random.uniform(0.0, graph.total_duration)
        filename = f"frame_{i+1:02d}_{t:0.2f}s.png"
        path = os.path.join(outdir, filename)
        renderer.render_frame_to_file(graph, t, path)
        click.echo(f"Wrote {path}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-n", "--samples", default=5, show_default=True, help="Sample count per scene")
def audit(input_file: str, samples: int):
    """Audit an animation for overlap and clipping issues."""
    from dsa_anim.dsl.parser import parse_file
    from dsa_anim.scene_graph.builder import build_scene_graph
    from dsa_anim.themes.registry import get_theme
    from dsa_anim.qa.audit import audit_scene_graph

    doc = parse_file(input_file)
    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)
    findings = audit_scene_graph(graph, samples_per_scene=samples)

    if not findings:
        click.echo("Audit passed: no overlap or clipping issues found.")
        return

    for finding in findings:
        node_text = f" [{', '.join(finding.node_ids)}]" if finding.node_ids else ""
        click.echo(
            f"{finding.severity.upper()} {finding.scene_id}@{finding.time_seconds:.2f}s "
            f"{finding.kind}{node_text}: {finding.message}"
        )

    if any(f.severity == "error" for f in findings):
        raise click.ClickException("Audit found overlap errors.")


def _build_render_graph(input_file: str, audio_timings: str | None):
    from dsa_anim.audio.timings import load_audio_timing_data
    from dsa_anim.dsl.parser import parse_file, parse_string
    from dsa_anim.dsl.retime import retime_document_to_audio_timings
    from dsa_anim.scene_graph.builder import build_scene_graph
    from dsa_anim.themes.registry import get_theme

    doc = parse_file(input_file)
    if audio_timings:
        raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
        timing_data = load_audio_timing_data(audio_timings)
        retimed = retime_document_to_audio_timings(raw_doc, timing_data)
        doc = parse_string(json.dumps(retimed), format="json")

    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)
    return graph, theme


if __name__ == "__main__":
    main()
