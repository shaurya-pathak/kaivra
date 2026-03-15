"""Easing functions for animation interpolation."""

import math


def linear(t: float) -> float:
    return t


def ease_in(t: float) -> float:
    return t * t


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 2


def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def spring(t: float) -> float:
    """Spring easing — overshoots then settles."""
    c4 = (2 * math.pi) / 3
    if t <= 0:
        return 0
    if t >= 1:
        return 1
    return -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * c4) + 1


def bounce(t: float) -> float:
    """Bounce easing — bounces at the end."""
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


EASING_FUNCTIONS = {
    "linear": linear,
    "ease-in": ease_in,
    "ease-out": ease_out,
    "ease-in-out": ease_in_out,
    "spring": spring,
    "bounce": bounce,
}


def get_easing(name: str):
    """Get an easing function by name."""
    fn = EASING_FUNCTIONS.get(name)
    if fn is None:
        raise ValueError(f"Unknown easing: {name!r}. Available: {list(EASING_FUNCTIONS.keys())}")
    return fn
