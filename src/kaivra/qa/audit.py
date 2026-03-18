"""Scene graph quality audits for overlap and clipping issues."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from kaivra.dsl.schema import ObjectType
from kaivra.scene_graph.models import SceneGraph, SceneNode
from kaivra.scene_graph.timeline import apply_animations_at_time
from kaivra.utils.geometry import Rect


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
    """Audit a resolved scene graph for clipping and overlap issues."""
    findings: list[AuditFinding] = []
    canvas = Rect(0, 0, graph.width, graph.height)

    for scene in graph.scenes:
        sample_times = _sample_times(scene.duration, samples_per_scene)
        for t in sample_times:
            nodes = deepcopy(scene.node_map)
            apply_animations_at_time(nodes, scene.timeline, t)

            visible_nodes = [node for node in nodes.values() if _should_audit_node(node)]

            effective_rects = {node.id: _effective_rect(node) for node in visible_nodes}

            findings.extend(_audit_clipping(scene.id, t, visible_nodes, effective_rects, canvas))
            findings.extend(_audit_overlaps(scene.id, t, visible_nodes, effective_rects))

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
            clipped_fraction = _clipped_area_fraction(rect, canvas)
            if clipped_fraction <= 0.22:
                continue
            severity = "info" if clipped_fraction <= 0.40 else "warning"
        else:
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


def _clipped_area_fraction(rect: Rect, canvas: Rect) -> float:
    intersection = rect.intersection(canvas)
    visible_area = intersection.area if intersection else 0.0
    if rect.area <= 0:
        return 0.0
    return max(0.0, 1.0 - (visible_area / rect.area))


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
