"""Carousel layout — horizontal row with optional arc."""

from __future__ import annotations

import math

from dsa_anim.dsl.schema import LayoutSpec, ObjectSpec
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Rect
from dsa_anim.layout.strategies._sizing import estimate_object_size


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
        total_w = sum(s.width for s in sizes) + gap * (len(sizes) - 1)
        start_x = bounds.x + (bounds.width - total_w) / 2
        center_y = bounds.y + bounds.height / 2
        curve = layout.curve or 0.0

        results: dict[str, Rect] = {}
        x = start_x
        n = len(objects)
        for idx, (obj, size) in enumerate(zip(objects, sizes)):
            t = 0.5 if n == 1 else idx / (n - 1)
            y_offset = math.sin((t - 0.5) * math.pi) * curve
            obj_id = obj.id or f"obj_{id(obj)}"
            results[obj_id] = Rect(x, center_y - size.height / 2 + y_offset, size.width, size.height)
            x += size.width + gap
        return results
