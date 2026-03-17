"""Video exporter — renders frames and pipes to ffmpeg for MP4/WebM output."""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from kaivra.render.cairo_renderer import CairoRenderer
from kaivra.scene_graph.models import SceneGraph
from kaivra.themes.base import ThemeSpec

ProgressCallback = Callable[[int, int], None]


def export_video(
    graph: SceneGraph,
    theme: ThemeSpec,
    output_path: str,
    fps: int = 30,
    *,
    log_progress: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> None:
    """Render all frames and encode to video via ffmpeg."""
    renderer = CairoRenderer(theme)
    total_frames = max(1, int(graph.total_duration * fps))
    width, height = graph.width, graph.height

    # Determine codec from extension
    if output_path.endswith(".webm"):
        codec_args = ["-c:v", "libvpx-vp9", "-b:v", "2M", "-crf", "30"]
    else:
        codec_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"]

    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgra",  # Cairo ARGB32 is BGRA in memory on little-endian
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",  # read from stdin
        *codec_args,
        output_path,
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        for frame_idx in range(total_frames):
            t = frame_idx / fps
            raw_bytes = renderer.render_frame_to_bytes(graph, t)
            proc.stdin.write(raw_bytes)

            # Progress
            if frame_idx % fps == 0:
                if progress_callback is not None:
                    progress_callback(frame_idx, total_frames)
                if log_progress:
                    pct = int(frame_idx / total_frames * 100)
                    print(
                        f"\r  Rendering: {pct}% ({frame_idx}/{total_frames} frames)",
                        end="",
                        flush=True,
                    )

        proc.stdin.close()
        proc.wait()
        if progress_callback is not None:
            progress_callback(total_frames, total_frames)
        if log_progress:
            print(f"\r  Rendering: 100% ({total_frames}/{total_frames} frames)")

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode()
            raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}):\n{stderr}")

    except BrokenPipeError:
        proc.kill()
        stderr = proc.stderr.read().decode()
        raise RuntimeError(f"ffmpeg pipe broken:\n{stderr}")
