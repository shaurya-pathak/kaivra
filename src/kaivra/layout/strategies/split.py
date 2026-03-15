"""Split layout — divide space into two regions (horizontal or vertical)."""

from __future__ import annotations

from kaivra.dsl.schema import LayoutSpec, ObjectSpec
from kaivra.themes.base import ThemeSpec
from kaivra.utils.geometry import Rect
from kaivra.layout.strategies._sizing import estimate_object_size


class SplitStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))

        # Parse ratio like "1:1" or "1:3"
        ratios = [1.0, 1.0]
        if layout.ratio:
            parts = layout.ratio.split(":")
            if len(parts) == 2:
                ratios = [float(parts[0]), float(parts[1])]

        horizontal = layout.direction != "vertical"

        if horizontal:
            regions = bounds.subdivide_horizontal(ratios, gap)
        else:
            regions = bounds.subdivide_vertical(ratios, gap)

        results: dict[str, Rect] = {}
        for i, obj in enumerate(objects):
            region = regions[min(i, len(regions) - 1)]
            size = estimate_object_size(obj, theme)
            # Center the object in its region
            x = region.x + (region.width - size.width) / 2
            y = region.y + (region.height - size.height) / 2
            obj_id = obj.id or f"obj_{id(obj)}"
            results[obj_id] = Rect(x, y, size.width, size.height)

        return results
