"""CLI entry point for kaivra."""

from __future__ import annotations

import click
import json
import tempfile
from pathlib import Path


def theme_file_option(func):
    """Shared CLI option for external JSON theme files."""
    return click.option(
        "--theme-file",
        type=click.Path(exists=True, dir_okay=False),
        help="External JSON theme file to use instead of the built-in theme name.",
    )(func)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """kaivra: Declarative animation engine for LLMs."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@theme_file_option
def validate(input_file: str, theme_file: str | None):
    """Validate a DSL file (JSON or YAML)."""
    from kaivra.dsl.parser import parse_file
    from kaivra.themes.loader import resolve_theme

    try:
        doc = parse_file(input_file)
        theme = resolve_theme(doc.meta.theme, theme_file)
        click.echo(f"Valid! {len(doc.scenes)} scene(s), theme: {theme.name}")
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
@click.option(
    "--voice-mode",
    type=click.Choice(["none", "local"]),
    default="none",
    show_default=True,
    help="Narration synthesis mode. 'local' uses Sherpa-ONNX offline TTS.",
)
@click.option(
    "--voice-model",
    type=click.Path(exists=True),
    help="Sherpa VITS/Piper model (.onnx) or model directory. Falls back to KAIVRA_SHERPA_MODEL.",
)
@click.option(
    "--voice-tokens",
    type=click.Path(exists=True, dir_okay=False),
    help="Sherpa tokens.txt path. Defaults to the model directory or KAIVRA_SHERPA_TOKENS.",
)
@click.option(
    "--voice-data-dir",
    type=click.Path(exists=True, file_okay=False),
    help="Sherpa espeak-ng-data directory. Defaults to the model directory or KAIVRA_SHERPA_DATA_DIR.",
)
@click.option(
    "--voice-lexicon",
    type=click.Path(exists=True, dir_okay=False),
    help="Optional Sherpa lexicon path. Defaults to lexicon.txt beside the model when present.",
)
@click.option(
    "--voice-rule-fsts",
    help="Optional Sherpa text normalization rule FSTs, passed through as a comma-separated list.",
)
@click.option(
    "--voice-speaker",
    type=int,
    default=None,
    help="Optional Sherpa speaker ID override. Falls back to KAIVRA_SHERPA_SPEAKER or 0.",
)
@click.option(
    "--voice-speed",
    type=float,
    default=None,
    help="Optional Sherpa speaking speed. Falls back to KAIVRA_SHERPA_SPEED or 1.0.",
)
@click.option(
    "--voice-pad",
    type=float,
    default=None,
    help="Silence padding to append after spoken narration per scene. Falls back to KAIVRA_SHERPA_PAD or 0.8 seconds.",
)
@click.option(
    "--voice-binary",
    default=None,
    help="Sherpa offline TTS executable name or absolute path. Defaults to KAIVRA_SHERPA_BIN or sherpa-onnx-offline-tts.",
)
@click.option(
    "--voice-artifacts-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Optional directory to keep generated local voice WAV and timing artifacts.",
)
@theme_file_option
def render(
    input_file: str,
    output: str,
    fps: int,
    audio: str | None,
    audio_timings: str | None,
    voice_mode: str,
    voice_model: str | None,
    voice_tokens: str | None,
    voice_data_dir: str | None,
    voice_lexicon: str | None,
    voice_rule_fsts: str | None,
    voice_speaker: int | None,
    voice_speed: float | None,
    voice_pad: float | None,
    voice_binary: str | None,
    voice_artifacts_dir: str | None,
    theme_file: str | None,
):
    """Render an animation to video or image."""
    from kaivra.render.cairo_renderer import CairoRenderer

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _validate_voice_inputs(
        voice_mode=voice_mode,
        audio=audio,
        audio_timings=audio_timings,
        voice_model=voice_model,
        voice_tokens=voice_tokens,
        voice_data_dir=voice_data_dir,
        voice_lexicon=voice_lexicon,
        voice_rule_fsts=voice_rule_fsts,
        voice_speaker=voice_speaker,
        voice_speed=voice_speed,
        voice_pad=voice_pad,
        voice_binary=voice_binary,
        voice_artifacts_dir=voice_artifacts_dir,
    )

    if output_path.suffix == ".png":
        if audio or audio_timings or voice_mode != "none":
            raise click.ClickException(
                "Audio and local voice options are only supported for video outputs (.mp4 or .webm)."
            )
        graph, theme = _build_render_graph(input_file, audio_timings, theme_file)
        renderer = CairoRenderer(theme)
        renderer.render_frame_to_file(graph, 0.0, output)
        click.echo(f"Rendered frame to {output}")
        return

    if output_path.suffix not in {".mp4", ".webm"}:
        raise click.ClickException(f"Unsupported output format: {output}")

    active_audio = audio
    active_audio_timings = audio_timings
    voice_assets_dir = None
    temp_voice_dir = None

    if voice_mode == "local":
        from kaivra.audio.local_voice import LocalVoiceConfig, synthesize_local_voice_assets
        from kaivra.dsl.parser import parse_file

        doc = parse_file(input_file)
        if voice_artifacts_dir:
            voice_assets_dir = Path(voice_artifacts_dir)
            voice_assets_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_voice_dir = tempfile.TemporaryDirectory(prefix=f"{output_path.stem}_local_voice_", dir=output_path.parent)
            voice_assets_dir = Path(temp_voice_dir.name)

        try:
            config = LocalVoiceConfig.from_sources(
                model_path=voice_model,
                tokens_path=voice_tokens,
                data_dir=voice_data_dir,
                lexicon_path=voice_lexicon,
                rule_fsts=voice_rule_fsts,
                speaker_id=voice_speaker,
                speed=voice_speed,
                pad_seconds=voice_pad,
                binary_name=voice_binary,
            )
            voice_assets = synthesize_local_voice_assets(doc, voice_assets_dir, config, stem=output_path.stem)
            active_audio = str(voice_assets.audio_path)
            active_audio_timings = str(voice_assets.timings_path)
        except Exception as exc:
            if temp_voice_dir is not None:
                temp_voice_dir.cleanup()
            raise click.ClickException(str(exc)) from exc

    try:
        graph, theme = _build_render_graph(input_file, active_audio_timings, theme_file)
        _render_video(graph, theme, output, fps=fps, audio=active_audio)
    finally:
        if temp_voice_dir is not None:
            temp_voice_dir.cleanup()
    click.echo(f"Rendered video to {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--serve", is_flag=True, help="Start live reload server")
@click.option("--port", default=8080, help="Server port")
@theme_file_option
def preview(input_file: str, serve: bool, port: int, theme_file: str | None):
    """Open web preview of an animation."""
    from kaivra.dsl.parser import parse_file
    from kaivra.render.web.exporter import export_web_preview
    from kaivra.themes.loader import resolve_theme

    doc = parse_file(input_file)
    theme = resolve_theme(doc.meta.theme, theme_file)
    export_web_preview(doc, theme=theme, serve=serve, port=port)


@main.command()
def schema():
    """Output JSON Schema for the DSL (for LLM prompting)."""
    from kaivra.dsl.schema import DocumentSpec

    json_schema = DocumentSpec.model_json_schema()
    click.echo(json.dumps(json_schema, indent=2))


@main.command()
def theme_schema():
    """Output JSON Schema for external theme files."""
    from kaivra.themes.loader import theme_schema as build_theme_schema

    click.echo(json.dumps(build_theme_schema(), indent=2))


@main.command("validate-theme")
@click.argument("theme_file", type=click.Path(exists=True, dir_okay=False))
def validate_theme(theme_file: str):
    """Validate an external JSON theme file."""
    from kaivra.themes.file_schema import load_theme_file

    try:
        theme = load_theme_file(theme_file)
        click.echo(f"Valid theme: {theme.name}")
    except Exception as exc:
        raise click.ClickException(f"Theme validation error: {exc}") from exc


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--outdir", default="frames", help="Output directory for PNG frames")
@click.option("-n", "--count", default=6, help="Number of random frames to render")
@click.option("--seed", default=None, type=int, help="Random seed for reproducible sampling")
@theme_file_option
def sample(input_file: str, outdir: str, count: int, seed: int | None, theme_file: str | None):
    """Render a few random frames to PNG for quick iteration."""
    import os
    import random

    from kaivra.dsl.parser import parse_file
    from kaivra.scene_graph.builder import build_scene_graph
    from kaivra.render.cairo_renderer import CairoRenderer
    from kaivra.themes.loader import resolve_theme

    doc = parse_file(input_file)
    theme = resolve_theme(doc.meta.theme, theme_file)
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
@theme_file_option
def audit(input_file: str, samples: int, theme_file: str | None):
    """Audit an animation for overlap and clipping issues."""
    from kaivra.dsl.parser import parse_file
    from kaivra.scene_graph.builder import build_scene_graph
    from kaivra.qa.audit import audit_scene_graph
    from kaivra.themes.loader import resolve_theme

    doc = parse_file(input_file)
    theme = resolve_theme(doc.meta.theme, theme_file)
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


def _build_render_graph(input_file: str, audio_timings: str | None, theme_file: str | None):
    from kaivra.audio.timings import load_audio_timing_data
    from kaivra.dsl.parser import parse_file, parse_string
    from kaivra.dsl.retime import retime_document_to_audio_timings
    from kaivra.scene_graph.builder import build_scene_graph
    from kaivra.themes.loader import resolve_theme

    doc = parse_file(input_file)
    if audio_timings:
        raw_doc = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
        timing_data = load_audio_timing_data(audio_timings)
        retimed = retime_document_to_audio_timings(raw_doc, timing_data)
        doc = parse_string(json.dumps(retimed), format="json")

    theme = resolve_theme(doc.meta.theme, theme_file)
    graph = build_scene_graph(doc, theme)
    return graph, theme


def _render_video(graph, theme, output: str, fps: int, audio: str | None):
    from kaivra.audio.mux import mux_audio
    from kaivra.render.video.exporter import export_video

    output_path = Path(output)
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
        return

    export_video(graph, theme, output, fps=fps)


def _validate_voice_inputs(
    *,
    voice_mode: str,
    audio: str | None,
    audio_timings: str | None,
    voice_model: str | None,
    voice_tokens: str | None,
    voice_data_dir: str | None,
    voice_lexicon: str | None,
    voice_rule_fsts: str | None,
    voice_speaker: int | None,
    voice_speed: float | None,
    voice_pad: float | None,
    voice_binary: str | None,
    voice_artifacts_dir: str | None,
) -> None:
    voice_configured = any(
        value is not None
        for value in (
            voice_model,
            voice_tokens,
            voice_data_dir,
            voice_lexicon,
            voice_rule_fsts,
            voice_speaker,
            voice_speed,
            voice_pad,
            voice_binary,
            voice_artifacts_dir,
        )
    )
    if voice_mode == "none":
        if voice_configured:
            raise click.ClickException(
                "Voice configuration flags require --voice-mode local."
            )
        return

    if audio or audio_timings:
        raise click.ClickException(
            "Use either manual --audio/--audio-timings inputs or --voice-mode local, not both."
        )


if __name__ == "__main__":
    main()
