"""High-quality deterministic contour recolouring."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Iterable

from PIL import Image


@dataclass(frozen=True)
class ToneRamp:
    shadow: tuple[int, int, int]
    midtone: tuple[int, int, int]
    highlight: tuple[int, int, int]


def parse_hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError("Expected a six-digit RGB colour")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def ramp_from_config(config: dict[str, str]) -> ToneRamp:
    return ToneRamp(
        shadow=parse_hex(config["shadow"]),
        midtone=parse_hex(config["midtone"]),
        highlight=parse_hex(config["highlight"]),
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    amount = position - lower
    return ordered[lower] * (1.0 - amount) + ordered[upper] * amount


def _mix(left: Iterable[int], right: Iterable[int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * amount) for a, b in zip(left, right))


def recolor_contour(source: Image.Image, ramp: ToneRamp) -> Image.Image:
    """Colourise a contour while retaining its exact alpha and local structure."""
    image = source.convert("RGBA")
    pixels = list(image.get_flattened_data())
    luminance = [
        (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
        for red, green, blue, alpha in pixels
        if alpha >= 12
    ]
    low = _percentile(luminance, 0.02)
    high = _percentile(luminance, 0.985)
    span = max(0.08, high - low)

    output: list[tuple[int, int, int, int]] = []
    for red, green, blue, alpha in pixels:
        if alpha == 0:
            output.append((0, 0, 0, 0))
            continue
        value = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
        value = max(0.0, min(1.0, (value - low) / span))
        # A gentle S-curve exposes tracks, wheels and gun edges at icon scale.
        value = value * value * (3.0 - 2.0 * value)
        if value < 0.58:
            rgb = _mix(ramp.shadow, ramp.midtone, value / 0.58)
        else:
            rgb = _mix(ramp.midtone, ramp.highlight, (value - 0.58) / 0.42)
        output.append((*rgb, alpha))

    result = Image.new("RGBA", image.size)
    result.putdata(output)
    return result
