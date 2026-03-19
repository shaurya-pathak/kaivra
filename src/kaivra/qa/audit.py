"""Scene graph quality audits for sampled layout issues."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from kaivra.dsl.schema import ObjectType
from kaivra.scene_graph.models import SceneGraph, SceneNode
from kaivra.scene_graph.timeline import apply_animations_at_time
from kaivra.utils.geometry import Point, Rect, connector_endpoints


@dataclass
class AuditFinding:
    severity: str
    kind: str
    scene_id: str
    time_seconds: float
    message: str
    node_ids: tuple[str, ...] = ()


def audit_scene_graph(
    graph: SceneGraph,
    *,
    samples_per_scene: int = 5,
) -> list[AuditFinding]:
    """Audit a resolved scene graph for sampled layout issues."""
    findings: list[AuditFinding] = []
    canvas = Rect(0, 0, graph.width, graph.height)

    for scene in graph.scenes:
        sample_times = _sample_times(scene.duration, samples_per_scene)
        for t in sample_times:
            nodes = deepcopy(scene.node_map)
            apply_animations_at_time(nodes, scene.timeline, t)

            visible_nodes = [node for node in nodes.values() if _should_audit_node(node)]
            visible_connectors = [node for node in nodes.values() if _should_audit_connector(node)]

            effective_rects = {node.id: _effective_rect(node) for node in visible_nodes}

            findings.extend(_audit_clipping(scene.id, t, visible_nodes, effective_rects, canvas))
            findings.extend(_audit_overlaps(scene.id, t, visible_nodes, effective_rects))
            findings.extend(_audit_callout_overlaps(scene.id, t, visible_nodes, effective_rects))
            findings.extend(
                _audit_connector_obstructions(
                    scene.id,
                    t,
                    visible_connectors,
                    visible_nodes,
                    effective_rects,
                )
            )

    return _dedupe_findings(findings)


def _sample_times(duration: float, count: int) -> list[float]:
    duration = max(0.01, duration)
    count = max(1, count)
    # Midpoint sampling avoids treating deliberate continuity crossfades at the
    # exact scene boundary as hard layout regressions.
    return [min(duration - 0.001, duration * (idx + 0.5) / count) for idx in range(count)]


def _should_audit_node(node: SceneNode) -> bool:
    if not node.visible or node.opacity <= 0.05:
        return False
    if node.obj_type in {ObjectType.GROUP, ObjectType.CONNECTOR}:
        return False
    return True


def _should_audit_connector(node: SceneNode) -> bool:
    return (
        node.visible
        and node.opacity > 0.05
        and node.obj_type == ObjectType.CONNECTOR
        and bool(node.from_id)
        and bool(node.to_id)
    )


def _effective_rect(node: SceneNode) -> Rect:
    return node.rect.scaled_about_center(node.scale_x, node.scale_y).translated(
        node.translate_x, node.translate_y
    )


def _audit_clipping(
    scene_id: str,
    time_seconds: float,
    nodes: list[SceneNode],
    rects: dict[str, Rect],
    canvas: Rect,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for node in nodes:
        rect = rects[node.id]
        overflow_left = max(0.0, canvas.x - rect.x)
        overflow_top = max(0.0, canvas.y - rect.y)
        overflow_right = max(0.0, rect.right - canvas.right)
        overflow_bottom = max(0.0, rect.bottom - canvas.bottom)
        overflow = max(overflow_left, overflow_top, overflow_right, overflow_bottom)
        if overflow <= 2.0:
            continue

        if node.layout_role == "carousel-item":
            continue

        severity = "warning"

        findings.append(
            AuditFinding(
                severity=severity,
                kind="clipping",
                scene_id=scene_id,
                time_seconds=time_seconds,
                message=(f"{node.id} extends outside the canvas by up to {overflow:.1f}px"),
                node_ids=(node.id,),
            )
        )
    return findings


def _audit_overlaps(
    scene_id: str,
    time_seconds: float,
    nodes: list[SceneNode],
    rects: dict[str, Rect],
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for idx, left in enumerate(nodes):
        if _is_transitional_node(left):
            continue
        left_rect = rects[left.id]
        for right in nodes[idx + 1 :]:
            if _is_transitional_node(right):
                continue
            right_rect = rects[right.id]
            intersection = left_rect.intersection(right_rect)
            if not intersection or intersection.area <= 80.0:
                continue
            overlap_ratio = intersection.area / max(1.0, min(left_rect.area, right_rect.area))
            if overlap_ratio <= 0.04:
                continue
            findings.append(
                AuditFinding(
                    severity="error",
                    kind="overlap",
                    scene_id=scene_id,
                    time_seconds=time_seconds,
                    message=(
                        f"{left.id} overlaps {right.id} "
                        f"({intersection.width:.1f}px x {intersection.height:.1f}px)"
                    ),
                    node_ids=(left.id, right.id),
                )
            )
    return findings


def _audit_callout_overlaps(
    scene_id: str,
    time_seconds: float,
    nodes: list[SceneNode],
    rects: dict[str, Rect],
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for node in nodes:
        if node.obj_type != ObjectType.CALLOUT or _is_transitional_node(node):
            continue
        node_rect = rects[node.id]
        for other in nodes:
            if other.id == node.id or _is_transitional_node(other):
                continue
            if other.id == node.from_id or other.obj_type in {
                ObjectType.GROUP,
                ObjectType.CONNECTOR,
            }:
                continue
            intersection = node_rect.intersection(rects[other.id])
            if not intersection or intersection.area <= 20.0:
                continue
            findings.append(
                AuditFinding(
                    severity="warning",
                    kind="callout_overlap",
                    scene_id=scene_id,
                    time_seconds=time_seconds,
                    message=(f"{node.id} overlaps {other.id} and may obscure nearby content"),
                    node_ids=(node.id, other.id),
                )
            )
    return findings


def _audit_connector_obstructions(
    scene_id: str,
    time_seconds: float,
    connectors: list[SceneNode],
    nodes: list[SceneNode],
    rects: dict[str, Rect],
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for connector in connectors:
        segment = _connector_segment(connector, rects)
        if segment is None:
            continue
        start, end = segment
        for other in nodes:
            if other.id in {connector.from_id, connector.to_id}:
                continue
            if _is_transitional_node(other):
                continue
            if not _segment_intersects_rect(start, end, rects[other.id].inset(-2.0)):
                continue
            findings.append(
                AuditFinding(
                    severity="warning",
                    kind="connector_overlap",
                    scene_id=scene_id,
                    time_seconds=time_seconds,
                    message=(
                        f"{connector.id} crosses over {other.id}; reroute or reposition "
                        "the nodes so the arrow stays clear"
                    ),
                    node_ids=(connector.id, other.id),
                )
            )
    return findings


def _connector_segment(connector: SceneNode, rects: dict[str, Rect]) -> tuple[Point, Point] | None:
    if not connector.from_id or not connector.to_id:
        return None
    from_rect = rects.get(connector.from_id)
    to_rect = rects.get(connector.to_id)
    if from_rect is None or to_rect is None:
        return None
    return connector_endpoints(from_rect, to_rect)


def _segment_intersects_rect(start: Point, end: Point, rect: Rect) -> bool:
    if _point_in_rect(start, rect) or _point_in_rect(end, rect):
        return True

    top_left = Point(rect.x, rect.y)
    top_right = Point(rect.right, rect.y)
    bottom_left = Point(rect.x, rect.bottom)
    bottom_right = Point(rect.right, rect.bottom)
    edges = (
        (top_left, top_right),
        (top_right, bottom_right),
        (bottom_right, bottom_left),
        (bottom_left, top_left),
    )
    return any(
        _segments_intersect(start, end, edge_start, edge_end) for edge_start, edge_end in edges
    )


def _point_in_rect(point: Point, rect: Rect) -> bool:
    return rect.x <= point.x <= rect.right and rect.y <= point.y <= rect.bottom


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(a1, b1, a2):
        return True
    if o2 == 0 and _on_segment(a1, b2, a2):
        return True
    if o3 == 0 and _on_segment(b1, a1, b2):
        return True
    if o4 == 0 and _on_segment(b1, a2, b2):
        return True
    return False


def _orientation(a: Point, b: Point, c: Point) -> int:
    cross = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y)
    if abs(cross) <= 1e-6:
        return 0
    return 1 if cross > 0 else 2


def _on_segment(start: Point, point: Point, end: Point) -> bool:
    return (
        min(start.x, end.x) - 1e-6 <= point.x <= max(start.x, end.x) + 1e-6
        and min(start.y, end.y) - 1e-6 <= point.y <= max(start.y, end.y) + 1e-6
    )


def _is_transitional_node(node: SceneNode) -> bool:
    return (
        abs(node.translate_x) > 2.0
        or abs(node.translate_y) > 2.0
        or abs(node.scale_x - node.base_scale_x) > 0.03
        or abs(node.scale_y - node.base_scale_y) > 0.03
        or node.opacity < 0.98
    )


def _dedupe_findings(findings: list[AuditFinding]) -> list[AuditFinding]:
    deduped: dict[tuple[str, str, tuple[str, ...]], AuditFinding] = {}
    for finding in findings:
        key = (finding.scene_id, finding.kind, tuple(sorted(finding.node_ids)))
        existing = deduped.get(key)
        if existing is None or finding.time_seconds < existing.time_seconds:
            deduped[key] = finding
    return sorted(
        deduped.values(),
        key=lambda f: (f.severity != "error", f.scene_id, f.time_seconds, f.kind, f.node_ids),
    )
