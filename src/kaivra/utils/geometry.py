"""Basic geometry primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float

    def lerp(self, other: Point, t: float) -> Point:
        return Point(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)


@dataclass
class Size:
    width: float
    height: float


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def top_center(self) -> Point:
        return Point(self.x + self.width / 2, self.y)

    @property
    def bottom_center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height)

    @property
    def left_center(self) -> Point:
        return Point(self.x, self.y + self.height / 2)

    @property
    def right_center(self) -> Point:
        return Point(self.x + self.width, self.y + self.height / 2)

    def inset(self, padding: float) -> Rect:
        return Rect(
            self.x + padding,
            self.y + padding,
            self.width - 2 * padding,
            self.height - 2 * padding,
        )

    def translated(self, dx: float = 0.0, dy: float = 0.0) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def scaled_about_center(self, sx: float = 1.0, sy: float | None = None) -> Rect:
        sy = sx if sy is None else sy
        center = self.center
        width = self.width * sx
        height = self.height * sy
        return Rect(center.x - width / 2, center.y - height / 2, width, height)

    def intersects(self, other: Rect) -> bool:
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )

    def intersection(self, other: Rect) -> Rect | None:
        if not self.intersects(other):
            return None
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.right, other.right)
        y2 = min(self.bottom, other.bottom)
        return Rect(x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1))

    def subdivide_vertical(self, ratios: list[float], gap: float = 0) -> list[Rect]:
        """Split into vertical sections according to ratios."""
        total = sum(ratios)
        total_gap = gap * (len(ratios) - 1)
        available = self.height - total_gap
        rects = []
        y = self.y
        for r in ratios:
            h = available * (r / total)
            rects.append(Rect(self.x, y, self.width, h))
            y += h + gap
        return rects

    def subdivide_horizontal(self, ratios: list[float], gap: float = 0) -> list[Rect]:
        """Split into horizontal sections according to ratios."""
        total = sum(ratios)
        total_gap = gap * (len(ratios) - 1)
        available = self.width - total_gap
        rects = []
        x = self.x
        for r in ratios:
            w = available * (r / total)
            rects.append(Rect(x, self.y, w, self.height))
            x += w + gap
        return rects


def connector_endpoints(from_rect: Rect, to_rect: Rect) -> tuple[Point, Point]:
    """Choose connector anchors that follow stacked or side-by-side layout naturally."""
    horizontal_overlap = min(from_rect.right, to_rect.right) - max(from_rect.x, to_rect.x)
    vertical_overlap = min(from_rect.bottom, to_rect.bottom) - max(from_rect.y, to_rect.y)
    center_dx = to_rect.center.x - from_rect.center.x
    center_dy = to_rect.center.y - from_rect.center.y

    if horizontal_overlap > 0 and abs(center_dy) > 1e-6:
        if center_dy > 0:
            return from_rect.bottom_center, to_rect.top_center
        return from_rect.top_center, to_rect.bottom_center

    if vertical_overlap > 0 and abs(center_dx) > 1e-6:
        if center_dx > 0:
            return from_rect.right_center, to_rect.left_center
        return from_rect.left_center, to_rect.right_center

    if abs(center_dy) > abs(center_dx):
        if center_dy > 0:
            return from_rect.bottom_center, to_rect.top_center
        return from_rect.top_center, to_rect.bottom_center

    if center_dx > 0:
        return from_rect.right_center, to_rect.left_center
    return from_rect.left_center, to_rect.right_center
