"""Carousel layout — horizontal row with optional arc."""

from __future__ import annotations

import math

from dsa_anim.dsl.schema import LayoutSpec, ObjectSpec
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Rect
from dsa_anim.layout.strategies._sizing import estimate_object_size


def carousel_scale_profile(
    count: int,
    active_index: int | None,
    active_scale: float,
    inactive_scale: float,
) -> list[float]:
    """Compute the base scale for each carousel item."""
    scales: list[float] = []
    if count <= 0:
        return scales

    for idx in range(count):
        if active_index is None or count == 1:
            distance = 0.0
        else:
            max_distance = max(active_index, count - 1 - active_index, 1)
            distance = abs(idx - active_index) / max_distance
        scale = active_scale + (inactive_scale - active_scale) * (distance ** 0.85)
        scales.append(scale)
    return scales


class CarouselStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        if not objects:
            return {}
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
        sizes = [estimate_object_size(obj, theme) for obj in objects]
        center_y = bounds.y + bounds.height / 2
        curve = layout.curve or 0.0
        active_index = None
        if layout.active:
            for idx, obj in enumerate(objects):
                if obj.id == layout.active:
                    active_index = idx
                    break
        active_scale = layout.active_scale if layout.active_scale is not None else 1.16
        inactive_scale = layout.inactive_scale if layout.inactive_scale is not None else 0.86
        scales = carousel_scale_profile(len(objects), active_index, active_scale, inactive_scale)

        scaled_widths = [size.width * scales[idx] for idx, size in enumerate(sizes)]
        centers = [0.0 for _ in objects]
        if objects:
            centers[0] = scaled_widths[0] / 2
        for idx in range(1, len(objects)):
            centers[idx] = (
                centers[idx - 1]
                + scaled_widths[idx - 1] / 2
                + gap
                + scaled_widths[idx] / 2
            )

        total_w = centers[-1] + scaled_widths[-1] / 2 if centers else 0.0
        start_x = bounds.x + (bounds.width - total_w) / 2

        shift_x = 0.0
        if active_index is not None:
            active_center_x = start_x + centers[active_index]
            shift_x = bounds.center.x - active_center_x

        results: dict[str, Rect] = {}
        n = len(objects)
        for idx, (obj, size) in enumerate(zip(objects, sizes)):
            if active_index is None or n == 1:
                reference = (n - 1) / 2 if n > 1 else 0.0
                max_distance = max(reference, 1.0)
            else:
                reference = float(active_index)
                max_distance = max(reference, n - 1 - reference, 1.0)
            normalized_distance = abs(idx - reference) / max_distance if max_distance else 0.0
            y_offset = (1.0 - math.cos(min(1.0, normalized_distance) * math.pi / 2.0)) * curve
            obj_id = obj.id or f"obj_{id(obj)}"
            center_x = start_x + centers[idx] + shift_x
            results[obj_id] = Rect(
                center_x - size.width / 2,
                center_y - size.height / 2 + y_offset,
                size.width,
                size.height,
            )
        return results
