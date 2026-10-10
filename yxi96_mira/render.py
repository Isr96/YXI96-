"""Dibuja la mira en un cuadro RGBA, sin depender del sistema."""

from __future__ import annotations

import math

from .settings import MiraSettings

_AA = 0.8


def parse_color(value: str) -> tuple[int, int, int]:
    hexes = value.lstrip("#")
    return int(hexes[0:2], 16), int(hexes[2:4], 16), int(hexes[4:6], 16)


def render(settings: MiraSettings) -> tuple[int, int, bytes]:
    """Devuelve lado, lado y bytes RGBA rectos (no premultiplicados)."""
    shape = settings.clamped()
    reach = _reach(shape)
    side = max(3, int(math.ceil(reach * 2)) + 1)
    if side % 2 == 0:
        side += 1
    red, green, blue = parse_color(shape.color)
    outline_px = 1.35 if shape.outline else 0.0
    opacity = shape.opacity
    buf = bytearray(side * side * 4)
    center = (side - 1) / 2.0
    for row in range(side):
        y = row - center
        base = row * side
        for col in range(side):
            margin = _margin(col - center, y, shape)
            fill = _coverage(margin)
            under = _coverage(margin + outline_px) if outline_px else 0.0
            if fill <= 0.0 and under <= 0.0:
                continue
            under_a = under * 0.92
            covered = fill + under_a * (1.0 - fill)
            if covered <= 0.004:
                continue
            # El contorno es negro y queda debajo del color. La transparencia
            # se aplica al final, para que el blanco siga siendo blanco.
            out_r = red * fill / covered
            out_g = green * fill / covered
            out_b = blue * fill / covered
            index = (base + col) * 4
            buf[index] = _byte(out_r)
            buf[index + 1] = _byte(out_g)
            buf[index + 2] = _byte(out_b)
            buf[index + 3] = _byte(covered * opacity * 255.0)
    return side, side, bytes(buf)


def premultiply_bgra(rgba: bytes) -> bytes:
    """BGRA premultiplicado, orden de fila de arriba a abajo, para Windows."""
    out = bytearray(len(rgba))
    for index in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[index : index + 4]
        out[index] = blue * alpha // 255
        out[index + 1] = green * alpha // 255
        out[index + 2] = red * alpha // 255
        out[index + 3] = alpha
    return bytes(out)


def composite(width: int, height: int, rgba: bytes, background) -> list[list[tuple[int, int, int]]]:
    """Funde la mira sobre un fondo. `background(x, y)` devuelve RGB."""
    rows: list[list[tuple[int, int, int]]] = []
    for y in range(height):
        row: list[tuple[int, int, int]] = []
        for x in range(width):
            index = (y * width + x) * 4
            red, green, blue, alpha = rgba[index : index + 4]
            back_r, back_g, back_b = background(x, y)
            factor = alpha / 255.0
            row.append(
                (
                    _byte(red * factor + back_r * (1.0 - factor)),
                    _byte(green * factor + back_g * (1.0 - factor)),
                    _byte(blue * factor + back_b * (1.0 - factor)),
                )
            )
        rows.append(row)
    return rows


def checker(light: tuple[int, int, int], dark: tuple[int, int, int], cell: int = 8):
    def sample(x: int, y: int) -> tuple[int, int, int]:
        return light if ((x // cell) + (y // cell)) % 2 == 0 else dark
    return sample


def pixel(settings: MiraSettings, dx: int, dy: int) -> tuple[int, int, int, int]:
    width, height, rgba = render(settings)
    x = width // 2 + dx
    y = height // 2 + dy
    if not (0 <= x < width and 0 <= y < height):
        return (0, 0, 0, 0)
    index = (y * width + x) * 4
    return tuple(rgba[index : index + 4])  # type: ignore[return-value]


def _reach(shape: MiraSettings) -> float:
    pad = shape.thickness / 2.0 + (2.4 if shape.outline else 1.4)
    if shape.style == "punto":
        return _punto_radius(shape) + pad
    if shape.style == "cruz_abierta":
        start, arm = _open_geom(shape)
        return start + arm + pad
    if shape.style == "marcas":
        start, arm = _mark_geom(shape)
        return start + arm + pad
    return float(shape.size) + pad


def _margin(x: float, y: float, shape: MiraSettings) -> float:
    half = shape.thickness / 2.0
    if shape.style == "punto":
        return _punto_radius(shape) - math.hypot(x, y)
    if shape.style == "cruz":
        return half - _dist_cross(x, y, float(shape.size))
    if shape.style == "cruz_abierta":
        start, arm = _open_geom(shape)
        return half - _dist_arms(x, y, start, arm)
    if shape.style == "circulo":
        return half - abs(math.hypot(x, y) - float(shape.size))
    if shape.style == "circulo_punto":
        ring = half - abs(math.hypot(x, y) - float(shape.size))
        dot = _dot_radius(shape) - math.hypot(x, y)
        return ring if ring > dot else dot
    if shape.style == "cruz_circulo":
        cross = half - _dist_cross(x, y, float(shape.size))
        ring = half - abs(math.hypot(x, y) - float(shape.size))
        return cross if cross > ring else ring
    if shape.style == "marcas":
        start, arm = _mark_geom(shape)
        return half - _dist_arms(x, y, start, arm)
    if shape.style == "cuadrado":
        return half - _dist_square(x, y, float(shape.size))
    return _punto_radius(shape) - math.hypot(x, y)


def _punto_radius(shape: MiraSettings) -> float:
    return max(1.2, shape.size * 0.55 + shape.thickness * 0.35)


def _dot_radius(shape: MiraSettings) -> float:
    natural = max(1.3, shape.thickness * 0.9)
    cap = max(1.3, shape.size * 0.34)
    return natural if natural < cap else cap


def _open_geom(shape: MiraSettings) -> tuple[float, float]:
    hole = max(3.0, shape.size * 0.30)
    start = hole + shape.thickness / 2.0
    arm = max(4.0, float(shape.size))
    return start, arm


def _mark_geom(shape: MiraSettings) -> tuple[float, float]:
    hole = max(4.0, shape.size * 0.70)
    start = hole + shape.thickness / 2.0
    arm = max(3.0, shape.size * 0.42)
    return start, arm


def _dist_cross(x: float, y: float, length: float) -> float:
    ax = abs(x)
    ay = abs(y)
    horizontal = math.hypot(max(ax - length, 0.0), ay)
    vertical = math.hypot(ax, max(ay - length, 0.0))
    return horizontal if horizontal < vertical else vertical


def _dist_arms(x: float, y: float, start: float, arm: float) -> float:
    outer = start + arm
    horizontal = _dist_arm(abs(x), abs(y), start, outer)
    vertical = _dist_arm(abs(y), abs(x), start, outer)
    return horizontal if horizontal < vertical else vertical


def _dist_arm(along: float, across: float, start: float, outer: float) -> float:
    if along < start:
        return math.hypot(start - along, across)
    if along > outer:
        return math.hypot(along - outer, across)
    return across


def _dist_square(x: float, y: float, half: float) -> float:
    ax = abs(x)
    ay = abs(y)
    if ax <= half and ay <= half:
        left = half - ax
        return left if left < (half - ay) else (half - ay)
    nearest_x = half if ax > half else ax
    nearest_y = half if ay > half else ay
    return math.hypot(ax - nearest_x, ay - nearest_y)


def _coverage(margin: float) -> float:
    amount = (margin + _AA) / (2.0 * _AA)
    if amount <= 0.0:
        return 0.0
    if amount >= 1.0:
        return 1.0
    return amount * amount * (3.0 - 2.0 * amount)


def _byte(value: float) -> int:
    if value <= 0.0:
        return 0
    if value >= 255.0:
        return 255
    return int(value + 0.5)
