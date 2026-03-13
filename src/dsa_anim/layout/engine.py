"""Layout engine — converts semantic layout descriptions into coordinates."""

from __future__ import annotations

from dsa_anim.dsl.schema import LayoutSpec, LayoutType, ObjectSpec
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.utils.geometry import Rect

from dsa_anim.layout.strategies.center import CenterStrategy
from dsa_anim.layout.strategies.grid import GridStrategy
from dsa_anim.layout.strategies.flow import FlowStrategy
from dsa_anim.layout.strategies.stack import StackStrategy
from dsa_anim.layout.strategies.split import SplitStrategy
from dsa_anim.layout.strategies.carousel import CarouselStrategy


class LayoutEngine:
    """Dispatches layout computation to the appropriate strategy."""

    def __init__(self, theme: ThemeSpec):
        self.theme = theme
        self._strategies = {
            LayoutType.CENTER: CenterStrategy(),
            LayoutType.GRID: GridStrategy(),
            LayoutType.FLOW: FlowStrategy(),
            LayoutType.STACK: StackStrategy(),
            LayoutType.SPLIT: SplitStrategy(),
            LayoutType.CAROUSEL: CarouselStrategy(),
        }

    def compute(
        self,
        objects: list[ObjectSpec],
        layout: LayoutSpec,
        bounds: Rect,
    ) -> dict[str, Rect]:
        """Compute positions for all objects. Returns {object_id: Rect}."""
        strategy = self._strategies.get(layout.type)
        if strategy is None:
            raise ValueError(f"No layout strategy for {layout.type}")
        return strategy.compute(objects, layout, bounds, self.theme)
