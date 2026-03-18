"""Grid layout — arrange objects in a columns x rows grid."""

from __future__ import annotations

import math

from kaivra.dsl.schema import LayoutSpec, ObjectSpec
from kaivra.layout.strategies._sizing import estimate_object_size
from kaivra.themes.base import ThemeSpec
from kaivra.utils.geometry import Rect


class GridStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
        cols = layout.columns or max(1, min(len(objects), 4))
        rows = layout.rows or math.ceil(len(objects) / cols)

        cell_w = (bounds.width - gap * (cols - 1)) / cols
        cell_h = (bounds.height - gap * (rows - 1)) / rows

        results: dict[str, Rect] = {}
        for i, obj in enumerate(objects):
            row, col = divmod(i, cols)
            size = estimate_object_size(obj, theme)
            # Center object within its cell
            cx = bounds.x + col * (cell_w + gap) + cell_w / 2
            cy = bounds.y + row * (cell_h + gap) + cell_h / 2
            w = min(size.width, cell_w)
            h = min(size.height, cell_h)
            obj_id = obj.id or f"obj_{id(obj)}"
            results[obj_id] = Rect(cx - w / 2, cy - h / 2, w, h)

        return results
