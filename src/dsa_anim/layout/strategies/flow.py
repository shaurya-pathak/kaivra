"""Flow layout — arrange objects in a horizontal or vertical flow."""

from __future__ import annotations

from dsa_anim.dsl.schema import LayoutSpec, ObjectSpec
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Rect
from dsa_anim.layout.strategies._sizing import estimate_object_size


class FlowStrategy:
    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
        theme: ThemeSpec,
    ) -> dict[str, Rect]:
        gap = theme.resolve_gap(layout.gap if isinstance(layout.gap, str) else str(layout.gap))
        horizontal = layout.direction != "vertical"
        align = layout.align

        sizes = [estimate_object_size(obj, theme) for obj in objects]
        results: dict[str, Rect] = {}

        if horizontal:
            total_w = sum(s.width for s in sizes) + gap * (len(sizes) - 1)
            x = bounds.x + (bounds.width - total_w) / 2  # center the flow
            for obj, size in zip(objects, sizes):
                # Vertically align each object within bounds
                if align in {"top", "start"}:
                    y = bounds.y
                elif align in {"bottom", "end"}:
                    y = bounds.y + bounds.height - size.height
                else:
                    y = bounds.y + (bounds.height - size.height) / 2
                obj_id = obj.id or f"obj_{id(obj)}"
                results[obj_id] = Rect(x, y, size.width, size.height)
                x += size.width + gap
        else:
            total_h = sum(s.height for s in sizes) + gap * (len(sizes) - 1)
            if align in {"top", "start"}:
                y = bounds.y
            elif align in {"bottom", "end"}:
                y = bounds.y + bounds.height - total_h
            else:
                y = bounds.y + (bounds.height - total_h) / 2
            for obj, size in zip(objects, sizes):
                if align == "left":
                    x = bounds.x
                elif align == "right":
                    x = bounds.x + bounds.width - size.width
                else:
                    x = bounds.x + (bounds.width - size.width) / 2
                obj_id = obj.id or f"obj_{id(obj)}"
                results[obj_id] = Rect(x, y, size.width, size.height)
                y += size.height + gap

        return results
