"""Theme runtime specification."""

from __future__ import annotations

from dataclasses import dataclass, field


REQUIRED_STYLE_KEYS = (
    "display",
    "heading",
    "section-heading",
    "body",
    "caption",
    "code",
    "result",
    "primary",
    "accent",
    "muted",
)


@dataclass
class ThemeSpec:
    """Complete theme specification for rendering."""

    name: str
    version: str = "1.0"

    # Canvas
    background_color: str = "#FFFDF7"

    # Typography
    display_font_family: str = "Sans"
    display_font_fallbacks: tuple[str, ...] = ("sans-serif",)
    body_font_family: str = "Sans"
    body_font_fallbacks: tuple[str, ...] = ("sans-serif",)
    code_font_family: str = "monospace"
    code_font_fallbacks: tuple[str, ...] = ("monospace",)
    font_size_display: int = 72
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

    # Token badge styling
    token_badge_font_size: float = 12.0
    token_badge_color: str = "#636E72"
    token_badge_opacity: float = 0.8
    token_badge_offset_y: float = 14.0

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

    # Narration chrome
    narration_background_color: str = "#0000008C"
    narration_text_color: str = "#FFFFFF"
    narration_font_size: float = 22.0
    narration_bar_height: float = 80.0
    narration_bottom_offset: float = 30.0
    narration_horizontal_padding: float = 80.0
    narration_line_height: float = 28.0

    # Callout chrome
    callout_background_color: str = "#0D0D26D9"
    callout_text_color: str = "#FFFFFF"
    callout_border_color: str = "#0984E3"
    callout_border_width: float = 1.5
    callout_corner_radius: float = 8.0
    callout_padding: float = 12.0
    callout_font_size: float = 16.0
    callout_max_width: float = 280.0
    callout_line_height: float = 22.0
    callout_pointer_color: str = "#0984E3"
    callout_pointer_width: float = 1.5
    callout_pointer_dash: tuple[float, ...] = (4.0, 4.0)

    # Progress bar chrome
    progress_bar_color: str = "#0984E3"
    progress_bar_height: float = 3.0
    progress_bar_opacity: float = 0.6

    # Web preview chrome
    preview_page_background: str = "#1A1A2E"
    preview_controls_text_color: str = "#EEEEEE"
    preview_canvas_corner_radius: float = 8.0
    preview_canvas_shadow: str = "0 4px 24px rgba(0,0,0,0.3)"
    preview_button_fill: str = "#0984E3"
    preview_button_hover_fill: str = "#0770C2"
    preview_button_text_color: str = "#FFFFFF"
    preview_button_corner_radius: float = 6.0
    preview_button_font_size: float = 14.0
    preview_timeline_accent: str = "#0984E3"
    preview_narration_text_color: str = "#CCCCCC"

    # Data-driven named styles
    styles: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        defaults = self._default_styles()
        if not self.styles:
            self.styles = defaults
            return

        merged: dict[str, dict] = {}
        for key, value in defaults.items():
            merged[key] = {**value, **self.styles.get(key, {})}
        for key, value in self.styles.items():
            if key not in merged:
                merged[key] = value.copy()
        self.styles = merged

    @property
    def font_family(self) -> str:
        """Backwards-compatible body font alias."""
        return self.body_font_family

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
        style_name = style or "body"
        props = self.styles.get(style_name, self.styles["body"]).copy()
        font_role = props.pop("font_role", None)
        if font_role is not None:
            props["font_family"] = self.font_family_for_role(font_role)
            props["font_css"] = self.font_stack_for_css(font_role)
        else:
            props.setdefault("font_family", self.font_family_for_role("body"))
            props.setdefault("font_css", self.font_stack_for_css("body"))
        props.setdefault("font_size", self.font_size_body)
        props.setdefault("color", self.text_color)
        return props

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
            "text": self.text_color,
            "text-light": self.text_light,
        }
        return color_map.get(color_name, color_name)

    def font_family_for_role(self, role: str | None) -> str:
        """Resolve a typography role to the primary installed font name."""
        if role == "display":
            return self.display_font_family
        if role == "code":
            return self.code_font_family
        return self.body_font_family

    def font_stack_for_css(self, role: str | None) -> str:
        """Resolve a typography role to a CSS font-family stack."""
        if role == "display":
            families = (self.display_font_family, *self.display_font_fallbacks)
        elif role == "code":
            families = (self.code_font_family, *self.code_font_fallbacks)
        else:
            families = (self.body_font_family, *self.body_font_fallbacks)
        return ", ".join(self._quote_css_font_family(name) for name in families)

    @staticmethod
    def _quote_css_font_family(name: str) -> str:
        generic = {
            "serif",
            "sans-serif",
            "monospace",
            "cursive",
            "fantasy",
            "system-ui",
            "ui-sans-serif",
            "ui-serif",
            "ui-monospace",
        }
        if name in generic:
            return name
        if " " in name or "-" in name:
            return f'"{name}"'
        return name

    def _default_styles(self) -> dict[str, dict]:
        return {
            "display": {
                "font_size": self.font_size_display,
                "font_weight": "bold",
                "font_role": "display",
                "color": self.text_color,
            },
            "heading": {
                "font_size": self.font_size_heading,
                "font_weight": "bold",
                "font_role": "display",
                "color": self.text_color,
            },
            "section-heading": {
                "font_size": self.font_size_section_heading,
                "font_weight": "bold",
                "font_role": "display",
                "color": self.text_color,
            },
            "body": {
                "font_size": self.font_size_body,
                "font_role": "body",
                "color": self.text_color,
            },
            "caption": {
                "font_size": self.font_size_caption,
                "font_role": "body",
                "color": self.text_light,
            },
            "code": {
                "font_size": self.font_size_code,
                "font_role": "code",
                "color": self.text_color,
            },
            "result": {
                "font_size": self.font_size_heading,
                "font_weight": "bold",
                "font_role": "display",
                "color": self.success,
            },
            "primary": {
                "font_role": "body",
                "fill": self.accent,
                "color": "#FFFFFF",
            },
            "accent": {
                "font_role": "body",
                "fill": self.accent,
                "border": self.accent,
            },
            "muted": {
                "font_role": "body",
                "fill": self.muted,
                "color": self.text_light,
            },
        }
