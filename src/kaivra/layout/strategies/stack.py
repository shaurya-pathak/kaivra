"""Stack layout — vertical stack of objects (like a column)."""

from __future__ import annotations

from kaivra.dsl.schema import LayoutSpec, ObjectSpec
from kaivra.layout.strategies._sizing import estimate_object_size
from kaivra.themes.base import ThemeSpec
from kaivra.utils.geometry import Rect


class StackStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
        align = layout.align

        sizes = [estimate_object_size(obj, theme) for obj in objects]
        total_h = sum(s.height for s in sizes) + gap * (len(sizes) - 1)
        if align in {"top", "start"}:
            y = bounds.y
        elif align in {"bottom", "end"}:
            y = bounds.y + bounds.height - total_h
        else:
            y = bounds.y + (bounds.height - total_h) / 2

        results: dict[str, Rect] = {}
        for obj, size in zip(objects, sizes):
            if align == "left":
                x = bounds.x
            elif align == "right":
                x = bounds.x + bounds.width - size.width
            else:  # center
                x = bounds.x + (bounds.width - size.width) / 2

            obj_id = obj.id or f"obj_{id(obj)}"
            results[obj_id] = Rect(x, y, size.width, size.height)
            y += size.height + gap

        return results
