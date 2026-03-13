"""Object size estimation without a rendering context.

Uses heuristics based on content length, font size, and theme settings.
When we have a Cairo context available, we can use actual text measurement.
"""

from __future__ import annotations

from dsa_anim.dsl.schema import LayoutSpec, LayoutType, ObjectSpec, ObjectType
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Size


def estimate_object_size(obj: ObjectSpec, theme: ThemeSpec) -> Size:
    """Estimate the rendered size of an object."""
    match obj.type:
        case ObjectType.TEXT:
            return _text_size(obj, theme)
        case ObjectType.BOX:
            return _box_size(obj, theme)
        case ObjectType.TOKEN:
            return _token_size(obj, theme)
        case ObjectType.CONNECTOR:
            return Size(0, 0)  # connectors don't occupy layout space
        case ObjectType.GROUP:
            return _group_size(obj, theme)
        case ObjectType.CIRCLE:
            return Size(theme.box_min_height, theme.box_min_height)
        case ObjectType.CALLOUT:
            text = obj.content or ""
            width = min(300, max(len(text) * 9, 150))
            lines = max(1, len(text) // 35 + 1)
            height = lines * 22 + 30
            return Size(width, height)
        case _:
            return Size(theme.box_min_width, theme.box_min_height)


def _text_size(obj: ObjectSpec, theme: ThemeSpec) -> Size:
    style = theme.resolve_style(obj.style)
    font_size = style.get("font_size", theme.font_size_body)
    text = obj.content or ""
    # Rough estimate: ~0.6 * font_size per character width
    char_width = font_size * 0.55
    width = max(len(text) * char_width, theme.box_min_width)
    height = font_size * 1.4
    return Size(width, height)


def _box_size(obj: ObjectSpec, theme: ThemeSpec) -> Size:
    text = obj.content or ""
    char_width = theme.font_size_body * 0.55
    text_width = len(text) * char_width
    shadow_extra = theme.shadow_offset if theme.shadow else 0
    width = max(text_width + theme.box_padding * 2, theme.box_min_width) + shadow_extra
    height = max(theme.font_size_body * 1.4 + theme.box_padding * 2, theme.box_min_height) + shadow_extra
    return Size(width, height)


def _token_size(obj: ObjectSpec, theme: ThemeSpec) -> Size:
    text = obj.content or ""
    char_width = theme.font_size_body * 0.55
    text_width = len(text) * char_width
    width = text_width + theme.token_padding * 2 + 8  # extra for badge
    height = theme.font_size_body * 1.4 + theme.token_padding * 2
    return Size(max(width, 50), height)


def _group_size(obj: ObjectSpec, theme: ThemeSpec) -> Size:
    """Estimate group size from its layout and children."""
    if not obj.children:
        return Size(theme.box_min_width, theme.box_min_height)
    child_sizes = [estimate_object_size(c, theme) for c in obj.children]
    child_layout = obj.layout if isinstance(obj.layout, LayoutSpec) else LayoutSpec(type=LayoutType.FLOW)
    gap = theme.resolve_gap(child_layout.gap if isinstance(child_layout.gap, str) else str(child_layout.gap))

    if child_layout.type == LayoutType.STACK or (
        child_layout.type == LayoutType.FLOW and child_layout.direction == "vertical"
    ):
        total_h = sum(s.height for s in child_sizes) + gap * (len(child_sizes) - 1)
        max_w = max(s.width for s in child_sizes)
        return Size(max_w, total_h)

    if child_layout.type == LayoutType.GRID:
        cols = child_layout.columns or len(child_sizes) or 1
        rows = child_layout.rows or ((len(child_sizes) + cols - 1) // cols)
        max_w = max(s.width for s in child_sizes)
        max_h = max(s.height for s in child_sizes)
        total_w = max_w * cols + gap * (cols - 1)
        total_h = max_h * rows + gap * (rows - 1)
        return Size(total_w, total_h)

    # Default: horizontal flow (including carousel)
    total_w = sum(s.width for s in child_sizes) + gap * (len(child_sizes) - 1)
    max_h = max(s.height for s in child_sizes)
    return Size(total_w, max_h)
