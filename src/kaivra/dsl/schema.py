"""Pydantic v2 models defining the entire DSL schema.

This is THE core file — it defines what LLMs can generate.
JSON Schema is auto-exported via DocumentSpec.model_json_schema().
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ObjectType(str, Enum):
    TEXT = "text"
    BOX = "box"
    CIRCLE = "circle"
    GROUP = "group"
    CONNECTOR = "connector"
    TOKEN = "token"
    CALLOUT = "callout"


class LayoutType(str, Enum):
    CENTER = "center"
    GRID = "grid"
    FLOW = "flow"
    STACK = "stack"
    SPLIT = "split"
    ABSOLUTE = "absolute"
    CAROUSEL = "carousel"


class AnimAction(str, Enum):
    # Visibility
    APPEAR = "appear"
    DISAPPEAR = "disappear"
    FADE_IN = "fade-in"
    FADE_OUT = "fade-out"
    # Motion
    MOVE = "move"
    MOVE_TO = "move-to"
    SWAP = "swap"
    SCALE = "scale"
    # Drawing
    DRAW = "draw"
    TYPE = "type"
    # Emphasis
    HIGHLIGHT = "highlight"
    PULSE = "pulse"
    # Complex
    BUILD = "build"


class EasingType(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease-in"
    EASE_OUT = "ease-out"
    EASE_IN_OUT = "ease-in-out"
    SPRING = "spring"
    BOUNCE = "bounce"


class TransitionType(str, Enum):
    FADE = "fade"


class CameraAction(str, Enum):
    ZOOM = "zoom"
    PAN = "pan"


class GapSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(s|ms)$")


def parse_duration(value: str) -> float:
    """Parse a duration string like '2s' or '500ms' into seconds."""
    if value == "auto":
        return -1.0  # sentinel for auto-duration
    m = _DURATION_RE.match(value.strip())
    if not m:
        raise ValueError(f"Invalid duration: {value!r}. Use e.g. '2s' or '500ms'.")
    num, unit = float(m.group(1)), m.group(2)
    return num if unit == "s" else num / 1000.0


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class GridRegionSpec(BaseModel):
    """A named grid region (Bootstrap-style column span)."""

    row: int = Field(1, description="1-based row index")
    row_span: int = Field(1, description="Number of rows to span")
    col: int = Field(1, description="1-based column index")
    span: int = Field(1, description="Number of columns to span")


class GridPositionSpec(BaseModel):
    """Explicit grid placement for an object."""

    row: int | None = Field(None, description="1-based row index")
    col: int | None = Field(None, description="1-based column index")
    span: int | None = Field(None, description="Number of columns to span")
    row_span: int | None = Field(None, description="Number of rows to span")
    region: str | None = Field(None, description="Named region defined in layout.regions (e.g. 'main', 'sidebar')")


class LayoutSpec(BaseModel):
    """Full layout specification for arranging child objects."""

    type: LayoutType = Field(LayoutType.CENTER, description="Layout algorithm: center, grid, flow, stack, split, absolute")
    columns: int | None = Field(None, description="Number of grid columns (for grid layout)")
    rows: int | None = Field(None, description="Number of grid rows (for grid layout)")
    gap: GapSize | str = Field(GapSize.MEDIUM, description="Spacing between objects: 'small', 'medium', or 'large'")
    direction: Literal["horizontal", "vertical"] = Field("horizontal", description="Flow direction for flow/stack layouts")
    align: Literal["center", "top", "bottom", "left", "right"] = Field("center", description="Alignment of objects within the layout")
    ratio: str | None = Field(None, description="Size ratio for split layouts, e.g. '1:1', '1:3'")
    regions: dict[str, GridRegionSpec] | None = Field(None, description="Named grid regions for Bootstrap-style placement")
    # Carousel-specific options
    curve: float | None = Field(None, description="Carousel arc height in pixels (positive = upward arc)")
    active: str | None = Field(None, description="Active item ID for carousel emphasis")
    active_scale: float | None = Field(None, description="Scale for active carousel item")
    inactive_scale: float | None = Field(None, description="Scale for inactive carousel items")

    model_config = {"extra": "allow"}


# Union type: layout can be a string shorthand or full spec
Layout = LayoutSpec | str


# ---------------------------------------------------------------------------
# Motion presets
# ---------------------------------------------------------------------------


class MotionSpec(BaseModel):
    """High-level motion preset for enter/exit/idle."""

    preset: str = Field(..., description="Motion preset name (e.g. 'fade', 'pop', 'slide-up', 'breathe')")
    at: str | None = Field(None, description="Start time for the motion (optional)")
    duration: str = Field("0.6s", description="Motion duration")
    easing: EasingType = Field(EasingType.EASE_OUT, description="Easing function")

    # Optional overrides
    offset_x: float | None = Field(None, description="Target horizontal offset (pixels)")
    offset_y: float | None = Field(None, description="Target vertical offset (pixels)")
    from_offset_x: float | None = Field(None, description="Starting horizontal offset (pixels)")
    from_offset_y: float | None = Field(None, description="Starting vertical offset (pixels)")
    scale: float | None = Field(None, description="Target scale for pop/scale presets")
    from_scale: float | None = Field(None, description="Starting scale for pop/scale presets")
    intensity: float | None = Field(None, description="Idle intensity (pixels or scale delta)")
    speed: float | None = Field(None, description="Idle speed")
    axis: Literal["x", "y", "both"] | None = Field("both", description="Idle motion axis")

    @field_validator("at", "duration", mode="before")
    @classmethod
    def validate_motion_durations(cls, v: str | None) -> str | None:
        if v is not None:
            parse_duration(v)
        return v


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------


class ObjectSpec(BaseModel):
    """Specification for any visual object in a scene."""

    type: ObjectType = Field(description="Object type: text, box, circle, group, connector, token, callout")
    id: str | None = Field(None, description="Unique identifier for this object (auto-generated if omitted)")
    content: str | None = Field(None, description="Text content displayed inside the object")
    style: str | None = Field(None, description="Visual style preset: 'display', 'heading', 'section-heading', 'body', 'caption', 'code'")
    position: Literal["top", "bottom", "left", "right", "above-layout"] | None = Field(None, description="Pin object to a canvas edge instead of participating in layout")
    grid: GridPositionSpec | None = Field(None, description="Explicit grid placement (row, col, span, or named region)")
    label: str | None = Field(None, description="Small label displayed on the object (e.g. badge text)")
    visible: bool | None = Field(None, description="Default visibility for this object (overrides scene auto_visible)")
    scale_text: bool | None = Field(
        None,
        description="Whether content text should scale with the object transform. Defaults to false for boxes/tokens and true otherwise.",
    )
    # Motion presets
    enter: "MotionSpec | None" = Field(None, description="Enter animation preset for this object")
    exit: "MotionSpec | None" = Field(None, description="Exit animation preset for this object")
    idle: "MotionSpec | None" = Field(None, description="Idle motion preset for this object")

    # Group children
    children: list[ObjectSpec] | None = Field(None, description="Child objects (only for type='group')")
    layout: Layout | None = Field(None, description="Layout for arranging children (only for type='group')")

    # Connector
    from_id: str | None = Field(None, alias="from", description="Source object ID (for connectors)")
    to_id: str | None = Field(None, alias="to", description="Destination object ID (for connectors)")
    target: str | None = Field(None, description="Target object ID that this callout points to (for callouts)")

    # Token
    token_id: int | None = Field(None, description="Numeric token ID displayed as a badge (for tokens)")

    # Callout
    callout_side: Literal["left", "right", "top", "bottom"] | None = Field(None, description="Which side of the target to place the callout")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------


class BuildPhase(BaseModel):
    """A phase in a multi-step build animation."""

    step: str = Field(description="Description of this build phase")
    at: str = Field(description="Start time for this phase, e.g. '2s'")
    duration: str = Field("1s", description="Duration of this phase")
    stagger: str | None = Field(None, description="Delay between targets in this phase")


class AnimSpec(BaseModel):
    """Specification for an animation action."""

    action: AnimAction = Field(description="Animation type: appear, disappear, fade-in, fade-out, move, move-to, swap, scale, draw, type, highlight, pulse, build")
    target: str | list[str] | None = Field(None, description="Object ID(s) to animate")
    to_id: str | None = Field(None, description="Destination object ID (for move-to)")

    # Timing
    at: str | None = Field(None, description="Start time, e.g. '0.5s' or '200ms'")
    after: str | None = Field(None, description="Start after another animation completes")
    duration: str = Field("0.5s", description="Animation duration, e.g. '1s' or '500ms'")
    stagger: str | None = Field(None, description="Delay between targets when animating multiple objects")
    easing: EasingType = Field(EasingType.EASE_IN_OUT, description="Easing function: linear, ease-in, ease-out, ease-in-out, spring, bounce")

    # Action-specific
    scale_factor: float | None = Field(None, description="Target scale multiplier (for scale action, e.g. 1.5 = 150%)")
    from_scale: float | None = Field(None, description="Starting scale for scale action (defaults to 1.0)")
    style: Literal["glow", "outline"] | None = Field(None, description="Highlight visual style (for highlight/pulse)")
    color: str | None = Field(None, description="Color name for emphasis animations (e.g. 'accent', 'success', 'error')")
    phases: list[BuildPhase] | None = Field(None, description="Build phases (for build action)")
    offset_x: float | None = Field(None, description="Horizontal offset in pixels (for move/move-to)")
    offset_y: float | None = Field(None, description="Vertical offset in pixels (for move/move-to)")
    from_offset_x: float | None = Field(None, description="Starting horizontal offset for move action (animates to offset_x)")
    from_offset_y: float | None = Field(None, description="Starting vertical offset for move action (animates to offset_y)")

    model_config = {"extra": "allow"}

    @field_validator("at", "duration", "stagger", mode="before")
    @classmethod
    def validate_duration_format(cls, v: str | None) -> str | None:
        if v is not None:
            parse_duration(v)  # validates format
        return v


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------


class CameraInitial(BaseModel):
    """Initial camera state for a scene."""

    zoom: float = Field(1.0, description="Initial zoom level (1.0 = 100%)")
    focus: str = Field("center", description="Initial focus point: object ID or 'center'")


class CameraSpec(BaseModel):
    """Camera configuration for a scene."""

    initial: CameraInitial | None = None


class CameraAnimSpec(BaseModel):
    """A camera animation (viewport-level, not object-level)."""

    action: CameraAction = Field(description="Camera action: zoom or pan")
    to: float | None = Field(None, description="Target zoom level (for zoom action)")
    focus: str | None = Field(None, description="Target focus point: object ID or 'center' (for pan)")
    at: str = Field(description="Start time, e.g. '1s'")
    duration: str = Field("1s", description="Animation duration")
    easing: EasingType = Field(EasingType.EASE_IN_OUT, description="Easing function")


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


class TransitionSpec(BaseModel):
    """Transition between scenes."""

    type: TransitionType = Field(description="Transition type: fade")
    duration: str = Field("0.5s", description="Transition duration")


# ---------------------------------------------------------------------------
# Focus helpers
# ---------------------------------------------------------------------------


class FocusStyleSpec(BaseModel):
    """Auto-focus styling for a scene (scale + highlight)."""

    at: str = Field("0s", description="Start time for focus animation")
    duration: str = Field("1.2s", description="Duration for focus animation")
    scale: float = Field(1.15, description="Scale applied to focused targets")
    color: str = Field("accent", description="Highlight color")
    style: Literal["glow", "outline"] = Field("glow", description="Highlight style")

    @field_validator("at", "duration", mode="before")
    @classmethod
    def validate_focus_durations(cls, v: str | None) -> str | None:
        if v is not None:
            parse_duration(v)
        return v


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


class SceneSpec(BaseModel):
    """A single scene in the animation."""

    id: str | None = Field(None, description="Unique scene identifier (auto-generated if omitted)")
    duration: str = Field("auto", description="Scene duration, e.g. '5s'. Use 'auto' to infer from animations")
    layout: Layout = "center"
    template: str | None = Field(
        None,
        description="Layout template: 'two-column', 'one-column', or 'title-opener'",
    )
    narration: str | None = Field(None, description="Narration text displayed at the bottom of the scene")

    objects: list[ObjectSpec] = Field(default_factory=list, description="Visual objects in this scene")
    animations: list[AnimSpec] = Field(default_factory=list, description="Animations to play during this scene")
    auto_visible: bool = Field(False, description="If true, objects are visible by default without appear animations")
    include_document_objects: bool | None = Field(
        None,
        description="Whether persistent document-level objects should be included in this scene. Defaults to false for title-opener scenes.",
    )
    show_progress: bool | None = Field(
        None,
        description="Whether to show the thin scene progress bar in rendered video outputs.",
    )
    focus: str | list[str] | None = Field(None, description="Auto-focus target(s) for this scene")
    focus_style: FocusStyleSpec | None = Field(None, description="Focus styling options")
    continuity: bool | None = Field(None, description="If true, inherit positions from previous scene for shared IDs")

    camera: CameraSpec | None = Field(None, description="Camera configuration")
    camera_animations: list[CameraAnimSpec] = Field(default_factory=list, description="Camera animations")
    transition: TransitionSpec | None = Field(None, description="Transition to next scene")

    @field_validator("layout", mode="before")
    @classmethod
    def parse_layout_shorthand(cls, v: Any) -> Any:
        if isinstance(v, str):
            return LayoutSpec(type=LayoutType(v))
        return v


# ---------------------------------------------------------------------------
# Document (top-level)
# ---------------------------------------------------------------------------


class MetaSpec(BaseModel):
    """Top-level metadata."""

    title: str = Field("Untitled Animation", description="Animation title")
    resolution: tuple[int, int] = Field((1920, 1080), description="Canvas resolution [width, height]")
    fps: int = Field(30, description="Frames per second")
    theme: str = Field("whiteboard", description="Visual theme name")
    show_narration: bool = Field(True, description="Whether to render narration captions")
    continuity: bool = Field(True, description="Inherit positions between scenes for shared IDs")
    continuity_duration: str = Field("0.6s", description="Duration for continuity moves between scenes")
    glow_release_padding: str = Field(
        "0.6s",
        description="Minimum tail time at scene end after highlight/pulse effects",
    )


class DocumentSpec(BaseModel):
    """The top-level document — this is what the LLM generates."""

    version: str = Field("1.0", description="Schema version")
    meta: MetaSpec = Field(default_factory=MetaSpec, description="Animation metadata")
    objects: list[ObjectSpec] = Field(default_factory=list, description="Persistent objects visible in every scene")
    scenes: list[SceneSpec] = Field(default_factory=list, description="Ordered list of scenes")
