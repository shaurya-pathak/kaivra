"""Center layout — place objects centered in bounds, stacked vertically."""

from __future__ import annotations

from kaivra.dsl.schema import LayoutSpec, ObjectSpec
from kaivra.layout.strategies._sizing import estimate_object_size
from kaivra.themes.base import ThemeSpec
from kaivra.utils.geometry import Rect


class CenterStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
        results: dict[str, Rect] = {}

        # Compute sizes for all objects
        sizes = [estimate_object_size(obj, theme) for obj in objects]
        total_height = sum(s.height for s in sizes) + gap * (len(sizes) - 1)

        # Start y so the group is vertically centered
        y = bounds.y + (bounds.height - total_height) / 2

        for obj, size in zip(objects, sizes):
            x = bounds.x + (bounds.width - size.width) / 2
            obj_id = obj.id or f"obj_{id(obj)}"
            results[obj_id] = Rect(x, y, size.width, size.height)
            y += size.height + gap

        return results
