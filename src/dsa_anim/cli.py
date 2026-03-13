"""CLI entry point for dsa-anim."""

import click
import json
import sys


@click.group()
@click.version_option(version="0.1.0")
def main():
    """dsa-anim: Declarative animation engine for LLMs."""
    pass


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
def validate(input_file: str):
    """Validate a DSL file (JSON or YAML)."""
    from dsa_anim.dsl.parser import parse_file

    try:
        doc = parse_file(input_file)
        click.echo(f"Valid! {len(doc.scenes)} scene(s), theme: {doc.meta.theme}")
    except Exception as e:
        click.echo(f"Validation error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", required=True, help="Output file (e.g., output.mp4, output.png)")
@click.option("--fps", default=30, help="Frames per second for video output")
def render(input_file: str, output: str, fps: int):
    """Render an animation to video or image."""
    from dsa_anim.dsl.parser import parse_file
    from dsa_anim.scene_graph.builder import build_scene_graph
    from dsa_anim.themes.registry import get_theme

    doc = parse_file(input_file)
    theme = get_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)

    if output.endswith(".png"):
        from dsa_anim.render.cairo_renderer import CairoRenderer

        renderer = CairoRenderer(theme)
        renderer.render_frame_to_file(graph, 0.0, output)
        click.echo(f"Rendered frame to {output}")
    elif output.endswith((".mp4", ".webm")):
        from dsa_anim.render.video.exporter import export_video

        export_video(graph, theme, output, fps=fps)
        click.echo(f"Rendered video to {output}")
    else:
        click.echo(f"Unsupported output format: {output}", err=True)
        sys.exit(1)


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


if __name__ == "__main__":
    main()
