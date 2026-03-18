"""Theme specification and base class."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ThemeSpec:
    """Complete theme specification for rendering."""

    name: str

    # Canvas
    background_color: str = "#FFFDF7"

    # Typography
    font_family: str = "sans-serif"
    font_size_heading: int = 48
    font_size_section_heading: int = 36
    font_size_body: int = 24
    font_size_caption: int = 18
    font_size_code: int = 20

    # Colors
    primary: str = "#2D3436"
    accent: str = "#0984E3"
    success: str = "#00B894"
    warning: str = "#FDCB6E"
    error: str = "#D63031"
    muted: str = "#B2BEC3"
    text_color: str = "#2D3436"
    text_light: str = "#636E72"

    # Box styling
    box_fill: str = "#FFFFFF"
    box_border: str = "#2D3436"
    box_border_width: float = 2.0
    box_corner_radius: float = 8.0
    box_padding: float = 16.0
    box_min_width: float = 120.0
    box_min_height: float = 50.0

    # Token styling
    token_fill: str = "#DFE6E9"
    token_border: str = "#636E72"
    token_padding: float = 8.0
    token_corner_radius: float = 4.0

    # Connector
    connector_color: str = "#636E72"
    connector_width: float = 2.0
    arrow_size: float = 10.0

    # Spacing / gaps
    gap_small: float = 12.0
    gap_medium: float = 24.0
    gap_large: float = 48.0

    # Layout margins
    margin: float = 60.0

    # Effects
    sketch_effect: bool = False
    sketch_roughness: float = 2.0
    shadow: bool = False
    shadow_offset: float = 4.0
    shadow_blur: float = 8.0
    shadow_color: str = "#00000033"

    def resolve_gap(self, gap: str) -> float:
        """Convert gap name to pixels."""
        gaps = {"small": self.gap_small, "medium": self.gap_medium, "large": self.gap_large}
        if gap in gaps:
            return gaps[gap]
        try:
            return float(gap)
        except ValueError:
            return self.gap_medium

    def resolve_style(self, style: str | None) -> dict:
        """Resolve a style name to rendering properties."""
        styles = {
            "heading": {
                "font_size": self.font_size_heading,
                "font_weight": "bold",
                "color": self.text_color,
            },
            "section-heading": {
                "font_size": self.font_size_section_heading,
                "font_weight": "bold",
                "color": self.text_color,
            },
            "body": {
                "font_size": self.font_size_body,
                "color": self.text_color,
            },
            "caption": {
                "font_size": self.font_size_caption,
                "color": self.text_light,
            },
            "code": {
                "font_size": self.font_size_code,
                "font_family": "monospace",
                "color": self.text_color,
            },
            "result": {
                "font_size": self.font_size_heading,
                "font_weight": "bold",
                "color": self.success,
            },
            "primary": {"fill": self.accent, "color": "#FFFFFF"},
            "accent": {"fill": self.accent, "border": self.accent},
            "muted": {"fill": self.muted, "color": self.text_light},
        }
        return styles.get(style, {"font_size": self.font_size_body, "color": self.text_color})

    def resolve_color(self, color_name: str | None) -> str:
        """Resolve a named color to hex."""
        if color_name is None:
            return self.text_color
        color_map = {
            "primary": self.primary,
            "accent": self.accent,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "muted": self.muted,
        }
        return color_map.get(color_name, color_name)

    def to_dict(self) -> dict:
        """Serialize the theme to a JSON-friendly dict."""
        return asdict(self)
