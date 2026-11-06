"""Fixed absolute matching-domain scale; colours never change matrix values."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    maximum: int | None
    label: str
    glyph: str
    ascii: str
    colour: str


BANDS = (
    Band(0, '0', '·', '.', '#172331'),
    Band(1, '1', '░', ':', '#26445e'),
    Band(3, '2–3', '▒', '=', '#296584'),
    Band(6, '4–6', '▓', '+', '#3c8c96'),
    Band(10, '7–10', '▉', '#', '#66b0a2'),
    Band(None, '11+', '█', '@', '#d4c98a'),
)


def band(value):
    if type(value) is not int or value < 0:
        raise ValueError('A heatmap band requires a known nonnegative match count')
    return next(item for item in BANDS if item.maximum is None or value <= item.maximum)


def mark(value, *, diagonal=False, numeric=False, plain=False):
    if diagonal: return '-'
    if value is None: return '?'
    return str(value) if numeric else band(value).ascii if plain else band(value).glyph
