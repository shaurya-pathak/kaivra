"""Timeline utilities for animation state computation."""

from __future__ import annotations

from kaivra.scene_graph.models import SceneNode, AnimationKeyframe, CameraState, CameraKeyframe
from kaivra.dsl.schema import AnimAction
from kaivra.utils.easing import get_easing


def apply_animations_at_time(
    nodes: dict[str, SceneNode],
    keyframes: list[AnimationKeyframe],
    t: float,
) -> None:
    """Mutate scene nodes to reflect animation state at time t."""
    # Reset all nodes to default state
    for node in nodes.values():
        if node.persistent:
            node.visible = True
            node.opacity = 1.0
            node.draw_progress = 1.0
        elif node.default_visible:
            node.visible = True
            node.opacity = 1.0
            node.draw_progress = 1.0
        else:
            node.visible = False
            node.opacity = 0.0
            node.draw_progress = 0.0
        node.scale_x = node.base_scale_x
        node.scale_y = node.base_scale_y
        node.translate_x = 0.0
        node.translate_y = 0.0
        node.highlight_intensity = 0.0
        node.highlight_color = None

    for kf in keyframes:
        node = nodes.get(kf.target_id)
        if node is None:
            continue

        progress = _get_progress(kf, t)

        match kf.action:
            case AnimAction.APPEAR:
                if t >= kf.start_time:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0

            case AnimAction.DISAPPEAR:
                if t < kf.start_time:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                else:
                    node.visible = False
                    node.opacity = 0.0

            case AnimAction.FADE_IN:
                if progress is not None:
                    node.visible = True
                    node.opacity = max(node.opacity, progress)
                    node.draw_progress = 1.0
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0

            case AnimAction.FADE_OUT:
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0 - progress
                    node.draw_progress = 1.0
                elif t >= kf.start_time + kf.duration:
                    node.visible = False
                    node.opacity = 0.0

            case AnimAction.TYPE | AnimAction.DRAW:
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = progress
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0

            case AnimAction.SCALE:
                to_val = kf.to_value or 1.0
                from_val = kf.from_value if kf.from_value is not None else 1.0
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    s = from_val + (to_val - from_val) * progress
                    node.scale_x = s
                    node.scale_y = s
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    node.scale_x = to_val
                    node.scale_y = to_val

            case AnimAction.MOVE:
                dx = kf.offset_x or 0.0
                dy = kf.offset_y or 0.0
                from_dx = kf.from_offset_x if kf.from_offset_x is not None else 0.0
                from_dy = kf.from_offset_y if kf.from_offset_y is not None else 0.0
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    node.translate_x = from_dx + (dx - from_dx) * progress
                    node.translate_y = from_dy + (dy - from_dy) * progress
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    node.translate_x = dx
                    node.translate_y = dy

            case AnimAction.MOVE_TO:
                target = nodes.get(kf.to_id) if kf.to_id else None
                if target:
                    dx = target.rect.center.x - node.rect.center.x + (kf.offset_x or 0.0)
                    dy = target.rect.center.y - node.rect.center.y + (kf.offset_y or 0.0)
                else:
                    dx = kf.offset_x or 0.0
                    dy = kf.offset_y or 0.0
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    node.translate_x = dx * progress
                    node.translate_y = dy * progress
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    node.translate_x = dx
                    node.translate_y = dy

            case AnimAction.HIGHLIGHT | AnimAction.PULSE:
                if progress is not None:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    # Envelope: fade-in (0-25%), hold (25-75%), fade-out (75-100%)
                    if progress < 0.25:
                        intensity = progress / 0.25
                    elif progress > 0.75:
                        intensity = (1.0 - progress) / 0.25
                    else:
                        intensity = 1.0
                    node.highlight_intensity = intensity
                    node.highlight_color = kf.color
                elif t >= kf.start_time + kf.duration:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0
                    # intensity stays at reset value (0) — glow has faded out

            case AnimAction.BUILD:
                # Multi-phase: treat overall as progressive reveal
                if kf.phases:
                    for phase in kf.phases:
                        phase_start = float(phase["at"].rstrip("s"))
                        phase_dur = float(phase["duration"].rstrip("s"))
                        if t >= phase_start:
                            node.visible = True
                            node.opacity = 1.0
                            phase_progress = min(1.0, (t - phase_start) / phase_dur) if phase_dur > 0 else 1.0
                            node.draw_progress = phase_progress

            case _:
                # Default: make visible if animation has started
                if t >= kf.start_time:
                    node.visible = True
                    node.opacity = 1.0
                    node.draw_progress = 1.0


def compute_camera_at_time(
    initial: CameraState,
    keyframes: list[CameraKeyframe],
    t: float,
    canvas_width: int,
    canvas_height: int,
    node_map: dict[str, SceneNode] | None = None,
) -> CameraState:
    """Compute camera state at time t."""
    state = CameraState(
        zoom=initial.zoom,
        center_x=initial.center_x or canvas_width / 2,
        center_y=initial.center_y or canvas_height / 2,
    )

    for kf in keyframes:
        if t < kf.start_time:
            continue

        raw_progress = (t - kf.start_time) / kf.duration if kf.duration > 0 else 1.0
        raw_progress = min(1.0, max(0.0, raw_progress))
        easing_fn = get_easing(kf.easing)
        progress = easing_fn(raw_progress)

        def resolve_focus(focus_id: str | None) -> tuple[float, float]:
            if not focus_id or focus_id == "center" or node_map is None:
                return (canvas_width / 2, canvas_height / 2)
            node = node_map.get(focus_id)
            if node is None:
                return (canvas_width / 2, canvas_height / 2)
            return (node.rect.center.x, node.rect.center.y)

        if kf.action == "zoom" and kf.to_zoom is not None:
            prev_zoom = state.zoom
            state.zoom = prev_zoom + (kf.to_zoom - prev_zoom) * progress
            if kf.focus_id:
                fx, fy = resolve_focus(kf.focus_id)
                state.center_x = state.center_x + (fx - state.center_x) * progress
                state.center_y = state.center_y + (fy - state.center_y) * progress
        elif kf.action == "pan":
            fx, fy = resolve_focus(kf.focus_id)
            state.center_x = state.center_x + (fx - state.center_x) * progress
            state.center_y = state.center_y + (fy - state.center_y) * progress

    return state


def _get_progress(kf: AnimationKeyframe, t: float) -> float | None:
    """Get eased progress for a keyframe at time t. Returns None if not active."""
    if t < kf.start_time:
        return None
    if kf.duration <= 0:
        return 1.0 if t >= kf.start_time else None

    raw = (t - kf.start_time) / kf.duration
    if raw > 1.0:
        return None  # animation complete, handled separately

    easing_fn = get_easing(kf.easing)
    return easing_fn(max(0.0, min(1.0, raw)))
