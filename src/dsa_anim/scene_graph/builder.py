"""Build a SceneGraph from a validated DocumentSpec."""

from __future__ import annotations

from dsa_anim.dsl.schema import (
    DocumentSpec, SceneSpec, ObjectSpec, LayoutSpec, LayoutType, GridPositionSpec,
    AnimSpec, CameraAnimSpec, MotionSpec, FocusStyleSpec, parse_duration,
)
from dsa_anim.dsl.schema import ObjectType, AnimAction
from dsa_anim.scene_graph.models import (
    SceneGraph, ResolvedScene, SceneNode, AnimationKeyframe,
    CameraState, CameraKeyframe, TransitionInfo,
)
from dsa_anim.layout.engine import LayoutEngine
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Rect


def build_scene_graph(doc: DocumentSpec, theme: ThemeSpec) -> SceneGraph:
    """Convert a DocumentSpec into a fully resolved SceneGraph."""
    width, height = doc.meta.resolution
    layout_engine = LayoutEngine(theme)
    canvas = Rect(theme.margin, theme.margin, width - theme.margin * 2, height - theme.margin * 2)
    glow_release_padding = parse_duration(doc.meta.glow_release_padding)

    # Collect IDs of persistent (document-level) objects
    persistent_ids: set[str] = set()
    for obj in doc.objects:
        _collect_ids(obj, persistent_ids)

    scenes = []
    prev_scene: ResolvedScene | None = None
    for scene_spec in doc.scenes:
        # Prepend persistent objects so they appear in every scene
        if doc.objects:
            merged_objects = list(doc.objects) + list(scene_spec.objects)
            merged_spec = scene_spec.model_copy(update={"objects": merged_objects})
        else:
            merged_spec = scene_spec
        resolved = _build_scene(
            merged_spec,
            layout_engine,
            theme,
            canvas,
            persistent_ids,
            glow_release_padding,
        )
        # Continuity: inherit positions from previous scene for shared IDs
        continuity = scene_spec.continuity if scene_spec.continuity is not None else doc.meta.continuity
        if continuity and prev_scene is not None:
            _apply_continuity(prev_scene, resolved, parse_duration(doc.meta.continuity_duration))
        scenes.append(resolved)
        prev_scene = resolved

    return SceneGraph(
        width=width,
        height=height,
        fps=doc.meta.fps,
        theme_name=doc.meta.theme,
        show_narration=doc.meta.show_narration,
        scenes=scenes,
    )


def _collect_ids(obj: ObjectSpec, ids: set[str]) -> None:
    """Recursively collect all object IDs."""
    if obj.id:
        ids.add(obj.id)
    if obj.children:
        for child in obj.children:
            _collect_ids(child, ids)


def _build_scene(
    spec: SceneSpec,
    layout_engine: LayoutEngine,
    theme: ThemeSpec,
    canvas: Rect,
    persistent_ids: set[str] | None = None,
    glow_release_padding: float = 0.0,
) -> ResolvedScene:
    # Apply scene template (if any)
    spec = _apply_scene_template(spec, persistent_ids)

    # Resolve layout
    layout = spec.layout if isinstance(spec.layout, LayoutSpec) else LayoutSpec(type=LayoutType.CENTER)

    # Filter out objects with special positions (they're placed separately)
    layout_objects = [o for o in spec.objects if not o.position and not o.grid]
    grid_objects = [o for o in spec.objects if o.grid]
    special_objects = [o for o in spec.objects if o.position]

    # Place special-position objects and compute how much space they consume
    # so the main layout can avoid overlapping them.
    from dsa_anim.layout.strategies._sizing import estimate_object_size
    positions = {}
    top_used = 0.0
    bottom_used = 0.0
    right_used = 0.0
    left_used = 0.0
    for obj in special_objects:
        pos = _resolve_special_position(obj, canvas, theme)
        positions[obj.id or f"special_{id(obj)}"] = pos
        size = estimate_object_size(obj, theme)
        if obj.position == "top":
            top_used = max(top_used, pos.y - canvas.y + size.height + theme.resolve_gap("medium"))
        elif obj.position == "bottom":
            bottom_used = max(bottom_used, canvas.bottom - pos.y + theme.resolve_gap("medium"))
        elif obj.position == "right":
            right_used = max(right_used, size.width + theme.resolve_gap("large"))
        elif obj.position == "left":
            left_used = max(left_used, size.width + theme.resolve_gap("large"))

    # Shrink the layout canvas so centered content doesn't overlap pinned objects
    layout_canvas = Rect(
        canvas.x + left_used,
        canvas.y + top_used,
        canvas.width - left_used - right_used,
        canvas.height - top_used - bottom_used,
    )

    # Compute layout positions within the adjusted bounds
    layout_positions = layout_engine.compute(layout_objects, layout, layout_canvas)
    positions.update(layout_positions)

    # Compute explicit grid placements (Bootstrap-style columns)
    if grid_objects:
        grid_positions = _compute_grid_positions(grid_objects, layout, layout_canvas, theme)
        positions.update(grid_positions)

    # Recursively compute positions for group children
    for obj in spec.objects:
        _compute_group_children(obj, positions, layout_engine, theme)

    # Position callouts next to their targets (if any)
    _position_callouts(spec.objects, positions, canvas, theme)

    # Bounds clamping — ensure all objects fit within the full canvas
    _clamp_to_canvas(positions, canvas)

    # Build scene nodes
    nodes = []
    node_map = {}
    for obj in spec.objects:
        node = _build_node(obj, positions, theme, auto_visible=spec.auto_visible)
        nodes.append(node)
        node_map[node.id] = node
        # Also register children
        _register_children(node, node_map)

    # Mark persistent objects so timeline doesn't reset them
    if persistent_ids:
        for node_id in persistent_ids:
            if node_id in node_map:
                node_map[node_id].persistent = True

    # Expand motion presets and focus into animations
    expanded_anims = list(spec.animations)
    expanded_anims.extend(_expand_motion_presets(spec))
    expanded_anims.extend(_expand_focus_presets(spec))

    # Resolve timeline
    duration = parse_duration(spec.duration) if spec.duration != "auto" else _auto_duration(
        spec.model_copy(update={"animations": expanded_anims})
    )
    timeline = _resolve_animations(expanded_anims, duration)
    timeline = _normalize_timeline(timeline, duration, glow_release_padding)

    # Camera
    camera_initial = CameraState()
    if spec.camera and spec.camera.initial:
        focus_id = spec.camera.initial.focus
        if focus_id and focus_id != "center" and focus_id in node_map:
            focus_rect = node_map[focus_id].rect
            camera_initial = CameraState(
                zoom=spec.camera.initial.zoom,
                center_x=focus_rect.center.x,
                center_y=focus_rect.center.y,
            )
        else:
            camera_initial = CameraState(
                zoom=spec.camera.initial.zoom,
                center_x=canvas.center.x,
                center_y=canvas.center.y,
            )

    camera_keyframes = [
        CameraKeyframe(
            action=ca.action.value,
            start_time=parse_duration(ca.at),
            duration=parse_duration(ca.duration),
            easing=ca.easing.value,
            to_zoom=ca.to,
            focus_id=ca.focus,
        )
        for ca in spec.camera_animations
    ]

    # Transition
    transition = None
    if spec.transition:
        transition = TransitionInfo(
            type=spec.transition.type.value,
            duration=parse_duration(spec.transition.duration),
        )

    return ResolvedScene(
        id=spec.id or "scene",
        duration=duration,
        nodes=nodes,
        node_map=node_map,
        timeline=timeline,
        camera_initial=camera_initial,
        camera_keyframes=camera_keyframes,
        transition=transition,
        narration=spec.narration,
    )


def _normalize_timeline(
    keyframes: list[AnimationKeyframe],
    scene_duration: float,
    glow_release_padding: float,
) -> list[AnimationKeyframe]:
    """Smooth out common inconsistencies (duplicate glows, scale-return)."""
    keyframes = _merge_highlights(keyframes)
    keyframes = _trim_glows(keyframes, scene_duration, glow_release_padding)
    keyframes = _auto_return_scales(keyframes, scene_duration)
    keyframes.sort(key=lambda k: k.start_time)
    return keyframes


def _trim_glows(
    keyframes: list[AnimationKeyframe],
    scene_duration: float,
    glow_release_padding: float,
) -> list[AnimationKeyframe]:
    """Ensure highlight/pulse effects fade out before the scene ends."""
    if glow_release_padding <= 0:
        return keyframes

    cutoff = max(0.0, scene_duration - glow_release_padding)
    for kf in keyframes:
        if kf.action not in {AnimAction.HIGHLIGHT, AnimAction.PULSE}:
            continue
        end_time = kf.start_time + kf.duration
        if end_time <= cutoff:
            continue
        new_duration = cutoff - kf.start_time
        if new_duration < 0.05:
            # If we're already past the cutoff, allow a tiny pulse if there's room.
            new_duration = max(0.0, min(0.15, scene_duration - kf.start_time))
        kf.duration = max(0.0, new_duration)

    return keyframes


def _apply_continuity(prev: ResolvedScene, curr: ResolvedScene, duration: float) -> None:
    """Ensure scene-to-scene continuity by animating shared nodes from previous positions."""
    if duration <= 0:
        return
    existing_moves: set[str] = set()
    for kf in curr.timeline:
        if kf.action in {AnimAction.MOVE, AnimAction.MOVE_TO} and kf.start_time <= 0.2:
            existing_moves.add(kf.target_id)

    for node_id, node in curr.node_map.items():
        if node_id in existing_moves:
            continue
        prev_node = prev.node_map.get(node_id)
        if prev_node is None:
            continue
        # Skip connectors; they follow endpoints
        if node.obj_type == ObjectType.CONNECTOR:
            continue
        # Skip if content changed (e.g., titles) or size changed significantly
        if prev_node.content != node.content:
            continue
        if abs(prev_node.rect.width - node.rect.width) > 1.0 or abs(prev_node.rect.height - node.rect.height) > 1.0:
            continue

        dx = prev_node.rect.x - node.rect.x
        dy = prev_node.rect.y - node.rect.y
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            continue
        # Start at previous position via offset, animate to zero
        curr.timeline.append(AnimationKeyframe(
            target_id=node_id,
            action=AnimAction.MOVE,
            start_time=0.0,
            duration=duration,
            easing="ease-in-out",
            from_offset_x=dx,
            from_offset_y=dy,
            offset_x=0.0,
            offset_y=0.0,
        ))

    curr.timeline.sort(key=lambda k: k.start_time)


def _merge_highlights(keyframes: list[AnimationKeyframe]) -> list[AnimationKeyframe]:
    """Merge overlapping highlight/pulse keyframes for the same target/color."""
    merged: list[AnimationKeyframe] = []
    buckets: dict[tuple[str, str, str | None, str | None], list[AnimationKeyframe]] = {}
    for kf in keyframes:
        if kf.action not in {AnimAction.HIGHLIGHT, AnimAction.PULSE}:
            merged.append(kf)
            continue
        key = (kf.target_id, kf.action.value, kf.color, kf.style)
        buckets.setdefault(key, []).append(kf)

    gap = 0.12
    for _, lst in buckets.items():
        lst.sort(key=lambda k: k.start_time)
        cur = None
        for kf in lst:
            if cur is None:
                cur = kf
                continue
            cur_end = cur.start_time + cur.duration
            kf_end = kf.start_time + kf.duration
            if kf.start_time <= cur_end + gap:
                cur.duration = max(cur_end, kf_end) - cur.start_time
            else:
                merged.append(cur)
                cur = kf
        if cur is not None:
            merged.append(cur)

    return merged


def _auto_return_scales(keyframes: list[AnimationKeyframe], scene_duration: float) -> list[AnimationKeyframe]:
    """Auto-insert a smooth scale-back to 1.0 after scale-up emphasis."""
    result = list(keyframes)
    by_target: dict[str, list[AnimationKeyframe]] = {}
    for kf in keyframes:
        if kf.action == AnimAction.SCALE:
            by_target.setdefault(kf.target_id, []).append(kf)

    for target_id, lst in by_target.items():
        lst.sort(key=lambda k: k.start_time)
        for i, kf in enumerate(lst):
            to_val = kf.to_value if kf.to_value is not None else 1.0
            if to_val <= 1.001:
                continue
            end_time = kf.start_time + kf.duration
            next_start = lst[i + 1].start_time if i + 1 < len(lst) else None
            if next_start is not None and next_start <= end_time + 0.2:
                continue
            # Skip if a scale-back already exists soon after
            has_return = any(
                abs((s.to_value or 1.0) - 1.0) < 0.01 and end_time <= s.start_time <= end_time + 0.6
                for s in lst
            )
            if has_return:
                continue
            return_dur = min(0.6, max(0.2, kf.duration * 0.6))
            start_time = end_time + 0.1
            # Ensure the return happens before the scene ends
            if start_time + return_dur > scene_duration:
                start_time = max(0.0, scene_duration - return_dur)
            result.append(AnimationKeyframe(
                target_id=target_id,
                action=AnimAction.SCALE,
                start_time=start_time,
                duration=return_dur,
                easing="ease-in-out",
                from_value=to_val,
                to_value=1.0,
            ))

    return result


def _expand_motion_presets(spec: SceneSpec) -> list[AnimSpec]:
    """Convert object-level enter/exit/idle presets into animations."""
    anims: list[AnimSpec] = []

    def walk(obj: ObjectSpec) -> None:
        if obj.id and obj.enter:
            anims.extend(_motion_to_anims(obj.id, obj.enter, kind="enter"))
        if obj.id and obj.exit:
            anims.extend(_motion_to_anims(obj.id, obj.exit, kind="exit"))
        if obj.children:
            for child in obj.children:
                walk(child)

    for obj in spec.objects:
        walk(obj)

    return anims


def _expand_focus_presets(spec: SceneSpec) -> list[AnimSpec]:
    """Auto-generate highlight + scale for scene focus targets."""
    if not spec.focus:
        return []
    targets = spec.focus if isinstance(spec.focus, list) else [spec.focus]
    style = spec.focus_style or FocusStyleSpec()
    return [
        AnimSpec(
            action=AnimAction.HIGHLIGHT,
            target=targets,
            at=style.at,
            duration=style.duration,
            style=style.style,
            color=style.color,
        ),
        AnimSpec(
            action=AnimAction.SCALE,
            target=targets,
            at=style.at,
            duration=style.duration,
            scale_factor=style.scale,
        ),
    ]


def _motion_to_anims(target_id: str, motion: MotionSpec, *, kind: str) -> list[AnimSpec]:
    """Map a motion preset to one or more AnimSpec entries."""
    preset = motion.preset.lower()
    at = motion.at or "0s"
    duration = motion.duration
    easing = motion.easing

    def fade(action: str) -> AnimSpec:
        return AnimSpec(action=AnimAction.FADE_IN if action == "in" else AnimAction.FADE_OUT, target=target_id, at=at, duration=duration, easing=easing)

    def move(from_x: float | None, from_y: float | None, to_x: float | None, to_y: float | None) -> AnimSpec:
        return AnimSpec(
            action=AnimAction.MOVE,
            target=target_id,
            at=at,
            duration=duration,
            easing=easing,
            from_offset_x=from_x,
            from_offset_y=from_y,
            offset_x=to_x,
            offset_y=to_y,
        )

    def scale(from_s: float | None, to_s: float | None) -> AnimSpec:
        return AnimSpec(
            action=AnimAction.SCALE,
            target=target_id,
            at=at,
            duration=duration,
            easing=easing,
            from_scale=from_s,
            scale_factor=to_s,
        )

    anims: list[AnimSpec] = []

    if preset in {"fade", "fade-in"}:
        anims.append(fade("in"))
    elif preset in {"fade-out"}:
        anims.append(fade("out"))
    elif preset in {"pop"}:
        anims.append(fade("in"))
        anims.append(scale(motion.from_scale or 0.92, motion.scale or 1.0))
    elif preset in {"slide-up"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x, motion.from_offset_y or 40.0, motion.offset_x, motion.offset_y))
    elif preset in {"slide-down"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x, motion.from_offset_y or -40.0, motion.offset_x, motion.offset_y))
    elif preset in {"slide-left"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x or 40.0, motion.from_offset_y, motion.offset_x, motion.offset_y))
    elif preset in {"slide-right"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x or -40.0, motion.from_offset_y, motion.offset_x, motion.offset_y))
    elif preset in {"drop"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x, motion.from_offset_y or -60.0, motion.offset_x, motion.offset_y))
    elif preset in {"rise"}:
        anims.append(fade("in"))
        anims.append(move(motion.from_offset_x, motion.from_offset_y or 60.0, motion.offset_x, motion.offset_y))
    elif preset in {"scale"}:
        anims.append(scale(motion.from_scale or 0.9, motion.scale or 1.0))
    else:
        # Default to a gentle fade for unknown presets
        anims.append(fade("in"))

    return anims


def _compute_group_children(
    obj: ObjectSpec,
    positions: dict[str, Rect],
    layout_engine: LayoutEngine,
    theme: ThemeSpec,
) -> None:
    """Recursively lay out children of group objects using the group's computed rect as bounds."""
    if obj.type.value != "group" or not obj.children:
        return
    obj_id = obj.id or f"obj_{id(obj)}"
    group_rect = positions.get(obj_id)
    if group_rect is None:
        return
    child_layout = obj.layout if isinstance(obj.layout, LayoutSpec) else LayoutSpec(type=LayoutType.FLOW)
    child_positions = layout_engine.compute(obj.children, child_layout, group_rect)
    positions.update(child_positions)
    # Recurse into nested groups
    for child in obj.children:
        _compute_group_children(child, positions, layout_engine, theme)


def _build_node(obj: ObjectSpec, positions: dict[str, Rect], theme: ThemeSpec, *, auto_visible: bool) -> SceneNode:
    obj_id = obj.id or f"obj_{id(obj)}"
    rect = positions.get(obj_id, Rect(0, 0, 100, 50))

    children = []
    if obj.children:
        for child in obj.children:
            child_node = _build_node(child, positions, theme, auto_visible=auto_visible)
            children.append(child_node)

    from_id = obj.from_id
    if obj.type == ObjectType.CALLOUT and obj.target:
        from_id = obj.target

    node = SceneNode(
        id=obj_id,
        obj_type=obj.type,
        rect=rect,
        content=obj.content,
        style=obj.style,
        style_props=theme.resolve_style(obj.style),
        children=children,
        position=obj.position,
        label=obj.label,
        from_id=from_id,
        to_id=obj.to_id,
        token_id=obj.token_id,
        idle_preset=obj.idle.preset if obj.idle else None,
        idle_intensity=obj.idle.intensity if obj.idle else None,
        idle_speed=obj.idle.speed if obj.idle else None,
        idle_axis=obj.idle.axis if obj.idle else None,
        default_visible=obj.visible if obj.visible is not None else auto_visible,
    )
    return node


def _register_children(node: SceneNode, node_map: dict[str, SceneNode]) -> None:
    for child in node.children:
        node_map[child.id] = child
        _register_children(child, node_map)


def _resolve_animations(anims: list[AnimSpec], scene_duration: float) -> list[AnimationKeyframe]:
    keyframes = []
    for anim in anims:
        start = parse_duration(anim.at) if anim.at else 0.0
        duration = parse_duration(anim.duration)
        stagger = parse_duration(anim.stagger) if anim.stagger else 0.0

        targets = anim.target if isinstance(anim.target, list) else [anim.target] if anim.target else []

        if anim.action == AnimAction.SWAP:
            if len(targets) == 2:
                a, b = targets
                keyframes.append(AnimationKeyframe(
                    target_id=a,
                    action=AnimAction.MOVE_TO,
                    start_time=start,
                    duration=duration,
                    easing=anim.easing.value,
                    to_id=b,
                    offset_x=anim.offset_x,
                    offset_y=anim.offset_y,
                ))
                keyframes.append(AnimationKeyframe(
                    target_id=b,
                    action=AnimAction.MOVE_TO,
                    start_time=start,
                    duration=duration,
                    easing=anim.easing.value,
                    to_id=a,
                    offset_x=anim.offset_x,
                    offset_y=anim.offset_y,
                ))
            continue

        for i, target_id in enumerate(targets):
            kf = AnimationKeyframe(
                target_id=target_id,
                action=anim.action,
                start_time=start + i * stagger,
                duration=duration,
                easing=anim.easing.value,
                targets=targets if len(targets) > 1 else None,
                to_value=anim.scale_factor,
                from_value=anim.from_scale,
                style=anim.style,
                color=anim.color,
                stagger=stagger,
                phases=[p.model_dump() for p in anim.phases] if anim.phases else None,
                offset_x=anim.offset_x,
                offset_y=anim.offset_y,
                from_offset_x=anim.from_offset_x,
                from_offset_y=anim.from_offset_y,
                to_id=anim.to_id,
            )
            keyframes.append(kf)

    keyframes.sort(key=lambda k: k.start_time)
    return keyframes


def _clamp_to_canvas(positions: dict[str, Rect], canvas: Rect) -> None:
    """Clamp all object positions so they stay within the canvas bounds."""
    for obj_id, rect in positions.items():
        clamped_w = min(rect.width, canvas.width)
        clamped_h = min(rect.height, canvas.height)
        x = max(canvas.x, min(rect.x, canvas.right - clamped_w))
        y = max(canvas.y, min(rect.y, canvas.bottom - clamped_h))
        positions[obj_id] = Rect(x, y, clamped_w, clamped_h)


def _position_callouts(
    objects: list[ObjectSpec],
    positions: dict[str, Rect],
    canvas: Rect,
    theme: ThemeSpec,
) -> None:
    """Place callouts next to their target by default."""
    from dsa_anim.layout.strategies._sizing import estimate_object_size

    gap = theme.resolve_gap("medium")
    for obj in objects:
        if obj.type != ObjectType.CALLOUT:
            continue

        target_id = obj.target or obj.from_id
        if not target_id:
            continue

        target_rect = positions.get(target_id)
        if not target_rect:
            continue

        obj_id = obj.id or f"callout_{id(obj)}"
        size = estimate_object_size(obj, theme)
        w, h = size.width, size.height

        # Choose side
        side = obj.callout_side or obj.position
        if side not in {"right", "left", "top", "bottom"}:
            space_right = canvas.right - (target_rect.right + gap + w)
            space_left = target_rect.x - gap - w - canvas.x
            space_top = target_rect.y - gap - h - canvas.y
            space_bottom = canvas.bottom - (target_rect.bottom + gap + h)
            candidates = {
                "right": space_right,
                "left": space_left,
                "top": space_top,
                "bottom": space_bottom,
            }
            side = max(candidates, key=candidates.get)

        if side == "right":
            x = target_rect.right + gap
            y = target_rect.center.y - h / 2
        elif side == "left":
            x = target_rect.x - gap - w
            y = target_rect.center.y - h / 2
        elif side == "top":
            x = target_rect.center.x - w / 2
            y = target_rect.y - gap - h
        else:  # bottom
            x = target_rect.center.x - w / 2
            y = target_rect.bottom + gap

        positions[obj_id] = Rect(x, y, w, h)


def _compute_grid_positions(
    objects: list[ObjectSpec],
    layout: LayoutSpec,
    bounds: Rect,
    theme: ThemeSpec,
) -> dict[str, Rect]:
    """Place objects using an explicit grid (Bootstrap-style columns)."""
    from dsa_anim.layout.strategies._sizing import estimate_object_size

    gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
    cols = layout.columns or 12

    max_row = 1
    for obj in objects:
        if not obj.grid:
            continue
        row = obj.grid.row or 1
        row_span = obj.grid.row_span or 1
        max_row = max(max_row, row + row_span - 1)
    rows = layout.rows or max_row

    cell_w = (bounds.width - gap * (cols - 1)) / cols
    cell_h = (bounds.height - gap * (rows - 1)) / rows

    regions = layout.regions or {}
    results: dict[str, Rect] = {}

    for obj in objects:
        if not obj.grid:
            continue

        region = regions.get(obj.grid.region) if obj.grid.region else None
        col = obj.grid.col if obj.grid.col is not None else (region.col if region else 1)
        span = obj.grid.span if obj.grid.span is not None else (region.span if region else 1)
        row = obj.grid.row if obj.grid.row is not None else (region.row if region else 1)
        row_span = obj.grid.row_span if obj.grid.row_span is not None else (region.row_span if region else 1)

        col = max(1, min(cols, col))
        span = max(1, min(cols - col + 1, span))
        row = max(1, min(rows, row))
        row_span = max(1, min(rows - row + 1, row_span))

        region_x = bounds.x + (col - 1) * (cell_w + gap)
        region_y = bounds.y + (row - 1) * (cell_h + gap)
        region_w = cell_w * span + gap * (span - 1)
        region_h = cell_h * row_span + gap * (row_span - 1)

        size = estimate_object_size(obj, theme)
        w = min(size.width, region_w)
        h = min(size.height, region_h)
        x = region_x + (region_w - w) / 2
        if obj.grid.region in {"main", "sidebar", "header"}:
            y = region_y
        else:
            y = region_y + (region_h - h) / 2

        obj_id = obj.id or f"grid_{id(obj)}"
        results[obj_id] = Rect(x, y, w, h)

    return results


def _resolve_special_position(obj: ObjectSpec, canvas: Rect, theme: ThemeSpec) -> Rect:
    from dsa_anim.layout.strategies._sizing import estimate_object_size
    size = estimate_object_size(obj, theme)

    match obj.position:
        case "top":
            return Rect(canvas.x + (canvas.width - size.width) / 2, canvas.y, size.width, size.height)
        case "above-layout":
            return Rect(canvas.x + (canvas.width - size.width) / 2, canvas.y - size.height - 10, size.width, size.height)
        case "bottom":
            return Rect(canvas.x + (canvas.width - size.width) / 2, canvas.bottom - size.height, size.width, size.height)
        case "right":
            return Rect(canvas.right - size.width, canvas.y + (canvas.height - size.height) / 2, size.width, size.height)
        case "left":
            return Rect(canvas.x, canvas.y + (canvas.height - size.height) / 2, size.width, size.height)
        case _:
            return Rect(canvas.x, canvas.y, size.width, size.height)


def _apply_scene_template(spec: SceneSpec, persistent_ids: set[str] | None) -> SceneSpec:
    """Apply layout templates to simplify scene authoring."""
    if not spec.template:
        return spec

    template = spec.template
    if template == "two-column":
        layout = LayoutSpec(
            type=LayoutType.GRID,
            columns=12,
            rows=12,
            gap="large",
            regions={
                "header": {"row": 1, "row_span": 1, "col": 1, "span": 12},
                "sidebar": {"row": 2, "row_span": 11, "col": 1, "span": 3},
                "main": {"row": 2, "row_span": 11, "col": 4, "span": 9},
            },
        )
    elif template == "one-column":
        layout = LayoutSpec(
            type=LayoutType.GRID,
            columns=12,
            rows=12,
            gap="large",
            regions={
                "header": {"row": 1, "row_span": 1, "col": 1, "span": 12},
                "main": {"row": 2, "row_span": 11, "col": 1, "span": 12},
            },
        )
    else:
        return spec

    persistent_ids = persistent_ids or set()

    def is_title(obj: ObjectSpec) -> bool:
        return obj.style in {"heading", "section-heading"}

    new_objects: list[ObjectSpec] = []
    for obj in spec.objects:
        if obj.grid and obj.layout and isinstance(obj.layout, LayoutSpec):
            if obj.grid.region in {"main", "sidebar"} and obj.layout.align == "center":
                if obj.layout.type in {LayoutType.STACK, LayoutType.FLOW} and (
                    obj.layout.type == LayoutType.STACK or obj.layout.direction == "vertical"
                ):
                    new_layout = obj.layout.model_copy(update={"align": "top"})
                    obj = obj.model_copy(update={"layout": new_layout})

        if obj.id in persistent_ids or obj.position or obj.grid:
            new_objects.append(obj)
            continue
        if is_title(obj):
            new_objects.append(obj.model_copy(update={"grid": GridPositionSpec(region="header")}))
        else:
            new_objects.append(obj.model_copy(update={"grid": GridPositionSpec(region="main")}))

    return spec.model_copy(update={"layout": layout, "objects": new_objects})


def _auto_duration(spec: SceneSpec) -> float:
    """Estimate duration from animations."""
    max_end = 5.0  # default
    for anim in spec.animations:
        start = parse_duration(anim.at) if anim.at else 0.0
        dur = parse_duration(anim.duration)
        stagger = parse_duration(anim.stagger) if anim.stagger else 0.0
        n_targets = len(anim.target) if isinstance(anim.target, list) else 1
        end = start + dur + stagger * (n_targets - 1)
        max_end = max(max_end, end + 1.0)  # 1s buffer
    return max_end
