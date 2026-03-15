"""Validated JSON schema for external theme files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from dsa_anim.themes.base import REQUIRED_STYLE_KEYS, ThemeSpec


class ThemeStyleFileSpec(BaseModel):
    """Data-driven style entry for named style presets."""

    model_config = ConfigDict(extra="forbid")

    font_size: int | None = None
    font_weight: Literal["normal", "bold"] | None = None
    font_role: Literal["display", "body", "code"] | None = None
    color: str | None = None
    fill: str | None = None
    border: str | None = None


class TypographyFileSpec(BaseModel):
    """Theme typography tokens."""

    model_config = ConfigDict(extra="forbid")

    display_family: str
    display_fallbacks: list[str] = Field(default_factory=list)
    body_family: str
    body_fallbacks: list[str] = Field(default_factory=list)
    code_family: str
    code_fallbacks: list[str] = Field(default_factory=list)
    display_size: int
    heading_size: int
    section_heading_size: int
    body_size: int
    caption_size: int
    code_size: int


class PaletteFileSpec(BaseModel):
    """Theme color palette tokens."""

    model_config = ConfigDict(extra="forbid")

    background: str
    primary: str
    accent: str
    success: str
    warning: str
    error: str
    muted: str
    text: str
    text_light: str


class BoxThemeFileSpec(BaseModel):
    """Theme tokens for box primitives."""

    model_config = ConfigDict(extra="forbid")

    fill: str
    border: str
    border_width: float
    corner_radius: float
    padding: float
    min_width: float
    min_height: float


class TokenThemeFileSpec(BaseModel):
    """Theme tokens for token primitives."""

    model_config = ConfigDict(extra="forbid")

    fill: str
    border: str
    padding: float
    corner_radius: float


class ConnectorThemeFileSpec(BaseModel):
    """Theme tokens for connectors."""

    model_config = ConfigDict(extra="forbid")

    color: str
    width: float
    arrow_size: float


class TokenBadgeThemeFileSpec(BaseModel):
    """Theme tokens for token ID badges."""

    model_config = ConfigDict(extra="forbid")

    font_size: float
    color: str
    opacity: float
    offset_y: float


class ObjectsThemeFileSpec(BaseModel):
    """Theme tokens for scene object types."""

    model_config = ConfigDict(extra="forbid")

    box: BoxThemeFileSpec
    token: TokenThemeFileSpec
    connector: ConnectorThemeFileSpec
    token_badge: TokenBadgeThemeFileSpec


class LayoutThemeFileSpec(BaseModel):
    """Theme spacing tokens."""

    model_config = ConfigDict(extra="forbid")

    gap_small: float
    gap_medium: float
    gap_large: float
    margin: float


class ShadowThemeFileSpec(BaseModel):
    """Theme shadow tokens."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    offset: float
    blur: float
    color: str


class EffectsThemeFileSpec(BaseModel):
    """Theme effect tokens."""

    model_config = ConfigDict(extra="forbid")

    sketch_effect: bool
    sketch_roughness: float
    shadow: ShadowThemeFileSpec


class NarrationChromeFileSpec(BaseModel):
    """Theme tokens for narration bar rendering."""

    model_config = ConfigDict(extra="forbid")

    background_color: str
    text_color: str
    font_size: float
    bar_height: float
    bottom_offset: float
    horizontal_padding: float
    line_height: float


class CalloutChromeFileSpec(BaseModel):
    """Theme tokens for callout rendering."""

    model_config = ConfigDict(extra="forbid")

    background_color: str
    text_color: str
    border_color: str
    border_width: float
    corner_radius: float
    padding: float
    font_size: float
    max_width: float
    line_height: float
    pointer_color: str
    pointer_width: float
    pointer_dash: list[float] = Field(default_factory=list)


class ProgressBarChromeFileSpec(BaseModel):
    """Theme tokens for scene progress bars."""

    model_config = ConfigDict(extra="forbid")

    color: str
    height: float
    opacity: float


class PreviewChromeFileSpec(BaseModel):
    """Theme tokens for the HTML preview controls."""

    model_config = ConfigDict(extra="forbid")

    page_background: str
    controls_text_color: str
    canvas_corner_radius: float
    canvas_shadow: str
    button_fill: str
    button_hover_fill: str
    button_text_color: str
    button_corner_radius: float
    button_font_size: float
    timeline_accent: str
    narration_text_color: str


class ChromeThemeFileSpec(BaseModel):
    """Theme tokens for non-scene chrome."""

    model_config = ConfigDict(extra="forbid")

    narration: NarrationChromeFileSpec
    callout: CalloutChromeFileSpec
    progress_bar: ProgressBarChromeFileSpec
    preview: PreviewChromeFileSpec


class ThemeFileSpec(BaseModel):
    """Validated external theme file."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(description="Theme schema version")
    name: str = Field(description="Resolved theme name")
    typography: TypographyFileSpec
    palette: PaletteFileSpec
    objects: ObjectsThemeFileSpec
    layout: LayoutThemeFileSpec
    effects: EffectsThemeFileSpec
    styles: dict[str, ThemeStyleFileSpec]
    chrome: ChromeThemeFileSpec

    @field_validator("styles")
    @classmethod
    def validate_required_styles(cls, styles: dict[str, ThemeStyleFileSpec]) -> dict[str, ThemeStyleFileSpec]:
        missing = [key for key in REQUIRED_STYLE_KEYS if key not in styles]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"styles is missing required entries: {names}")
        return styles

    @model_validator(mode="after")
    def validate_version(self) -> "ThemeFileSpec":
        if self.version != "1.0":
            raise ValueError(f"Unsupported theme version: {self.version!r}. Expected '1.0'.")
        return self

    def to_theme_spec(self) -> ThemeSpec:
        """Convert the validated file model to the flattened runtime theme."""
        return ThemeSpec(
            name=self.name,
            version=self.version,
            background_color=self.palette.background,
            display_font_family=self.typography.display_family,
            display_font_fallbacks=tuple(self.typography.display_fallbacks),
            body_font_family=self.typography.body_family,
            body_font_fallbacks=tuple(self.typography.body_fallbacks),
            code_font_family=self.typography.code_family,
            code_font_fallbacks=tuple(self.typography.code_fallbacks),
            font_size_display=self.typography.display_size,
            font_size_heading=self.typography.heading_size,
            font_size_section_heading=self.typography.section_heading_size,
            font_size_body=self.typography.body_size,
            font_size_caption=self.typography.caption_size,
            font_size_code=self.typography.code_size,
            primary=self.palette.primary,
            accent=self.palette.accent,
            success=self.palette.success,
            warning=self.palette.warning,
            error=self.palette.error,
            muted=self.palette.muted,
            text_color=self.palette.text,
            text_light=self.palette.text_light,
            box_fill=self.objects.box.fill,
            box_border=self.objects.box.border,
            box_border_width=self.objects.box.border_width,
            box_corner_radius=self.objects.box.corner_radius,
            box_padding=self.objects.box.padding,
            box_min_width=self.objects.box.min_width,
            box_min_height=self.objects.box.min_height,
            token_fill=self.objects.token.fill,
            token_border=self.objects.token.border,
            token_padding=self.objects.token.padding,
            token_corner_radius=self.objects.token.corner_radius,
            token_badge_font_size=self.objects.token_badge.font_size,
            token_badge_color=self.objects.token_badge.color,
            token_badge_opacity=self.objects.token_badge.opacity,
            token_badge_offset_y=self.objects.token_badge.offset_y,
            connector_color=self.objects.connector.color,
            connector_width=self.objects.connector.width,
            arrow_size=self.objects.connector.arrow_size,
            gap_small=self.layout.gap_small,
            gap_medium=self.layout.gap_medium,
            gap_large=self.layout.gap_large,
            margin=self.layout.margin,
            sketch_effect=self.effects.sketch_effect,
            sketch_roughness=self.effects.sketch_roughness,
            shadow=self.effects.shadow.enabled,
            shadow_offset=self.effects.shadow.offset,
            shadow_blur=self.effects.shadow.blur,
            shadow_color=self.effects.shadow.color,
            narration_background_color=self.chrome.narration.background_color,
            narration_text_color=self.chrome.narration.text_color,
            narration_font_size=self.chrome.narration.font_size,
            narration_bar_height=self.chrome.narration.bar_height,
            narration_bottom_offset=self.chrome.narration.bottom_offset,
            narration_horizontal_padding=self.chrome.narration.horizontal_padding,
            narration_line_height=self.chrome.narration.line_height,
            callout_background_color=self.chrome.callout.background_color,
            callout_text_color=self.chrome.callout.text_color,
            callout_border_color=self.chrome.callout.border_color,
            callout_border_width=self.chrome.callout.border_width,
            callout_corner_radius=self.chrome.callout.corner_radius,
            callout_padding=self.chrome.callout.padding,
            callout_font_size=self.chrome.callout.font_size,
            callout_max_width=self.chrome.callout.max_width,
            callout_line_height=self.chrome.callout.line_height,
            callout_pointer_color=self.chrome.callout.pointer_color,
            callout_pointer_width=self.chrome.callout.pointer_width,
            callout_pointer_dash=tuple(self.chrome.callout.pointer_dash),
            progress_bar_color=self.chrome.progress_bar.color,
            progress_bar_height=self.chrome.progress_bar.height,
            progress_bar_opacity=self.chrome.progress_bar.opacity,
            preview_page_background=self.chrome.preview.page_background,
            preview_controls_text_color=self.chrome.preview.controls_text_color,
            preview_canvas_corner_radius=self.chrome.preview.canvas_corner_radius,
            preview_canvas_shadow=self.chrome.preview.canvas_shadow,
            preview_button_fill=self.chrome.preview.button_fill,
            preview_button_hover_fill=self.chrome.preview.button_hover_fill,
            preview_button_text_color=self.chrome.preview.button_text_color,
            preview_button_corner_radius=self.chrome.preview.button_corner_radius,
            preview_button_font_size=self.chrome.preview.button_font_size,
            preview_timeline_accent=self.chrome.preview.timeline_accent,
            preview_narration_text_color=self.chrome.preview.narration_text_color,
            styles={name: style.model_dump(exclude_none=True) for name, style in self.styles.items()},
        )


def load_theme_file(path: str | Path) -> ThemeSpec:
    """Load and validate an external JSON theme file."""
    raw = load_theme_file_raw(path)
    try:
        spec = ThemeFileSpec.model_validate(raw)
    except ValidationError as exc:
        raise format_theme_validation_error(exc, str(path)) from exc
    return spec.to_theme_spec()


def load_theme_file_raw(path: str | Path) -> dict:
    """Load raw JSON from a theme file path."""
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError(f"Theme files must use a .json extension: {path}")
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object at top level, got {type(raw).__name__}")
    return raw


def format_theme_validation_error(exc: ValidationError, source: str) -> ValueError:
    """Format Pydantic theme validation errors into clear CLI messages."""
    lines = [f"Theme validation failed for {source}:"]
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        lines.append(f"  [{loc}] {err['msg']}")
        if err.get("ctx"):
            lines.append(f"    context: {err['ctx']}")
    return ValueError("\n".join(lines))
