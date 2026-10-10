"""Perfil visible de la mira y su archivo local."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

STYLES: tuple[tuple[str, str], ...] = (
    ("punto", "Punto"),
    ("cruz", "Cruz"),
    ("cruz_abierta", "Cruz abierta"),
    ("circulo", "Círculo"),
    ("circulo_punto", "Círculo y punto"),
    ("cruz_circulo", "Cruz y círculo"),
    ("marcas", "Marcas"),
    ("cuadrado", "Cuadrado"),
)

STYLE_IDS = {key for key, _label in STYLES}
STYLE_LABEL = {key: label for key, label in STYLES}

COLORS: tuple[tuple[str, str], ...] = (
    ("#FFFFFF", "Blanco"),
    ("#39FF6A", "Verde"),
    ("#FF4D4D", "Rojo"),
    ("#4DE2FF", "Cian"),
    ("#FFE14D", "Amarillo"),
    ("#FF4DFF", "Magenta"),
)


def config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "YXI96Mira"
    return Path.home() / ".config" / "yxi96-mira"


def settings_path() -> Path:
    return config_dir() / "mira.json"


@dataclass
class MiraSettings:
    style: str = "punto"
    size: int = 6
    thickness: int = 2
    opacity: float = 1.0
    color: str = "#FFFFFF"
    outline: bool = True
    offset_x: int = 0
    offset_y: int = 0
    visible: bool = True
    monitor: int = 0

    def clamped(self) -> MiraSettings:
        style = self.style if self.style in STYLE_IDS else "punto"
        color = _normalize_color(self.color)
        return MiraSettings(
            style=style,
            size=_clamp_int(self.size, 2, 64),
            thickness=_clamp_int(self.thickness, 1, 14),
            opacity=_clamp_float(self.opacity, 0.1, 1.0),
            color=color,
            outline=bool(self.outline),
            offset_x=_clamp_int(self.offset_x, -200, 200),
            offset_y=_clamp_int(self.offset_y, -200, 200),
            visible=bool(self.visible),
            monitor=max(0, _clamp_int(self.monitor, 0, 15)),
        )

    def to_dict(self) -> dict:
        data = asdict(self.clamped())
        data["version"] = 1
        return data

    @classmethod
    def from_dict(cls, raw: object) -> MiraSettings:
        if not isinstance(raw, dict):
            return cls()
        known = {name: raw[name] for name in cls.__dataclass_fields__ if name in raw}
        try:
            return cls(**known).clamped()
        except (TypeError, ValueError):
            return cls()


def load_settings(path: Path | None = None) -> MiraSettings:
    file = path or settings_path()
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MiraSettings()
    return MiraSettings.from_dict(raw)


def save_settings(settings: MiraSettings, path: Path | None = None) -> None:
    file = path or settings_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, file)


def _clamp_int(value: object, low: int, high: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _clamp_float(value: object, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    if number != number:  # NaN
        number = low
    return max(low, min(high, number))


def _normalize_color(value: object) -> str:
    text = str(value or "").strip()
    if not text.startswith("#"):
        text = "#" + text
    hexes = text[1:]
    if len(hexes) == 3:
        hexes = "".join(ch * 2 for ch in hexes)
    if len(hexes) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in hexes):
        return "#FFFFFF"
    return "#" + hexes.upper()
