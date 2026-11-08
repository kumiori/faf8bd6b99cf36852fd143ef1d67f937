"""Deterministic constellation portraits with a textual equivalent."""
from dataclasses import dataclass
from hashlib import sha256
from functools import lru_cache

PORTRAIT_VERSION = 'constellation/v1'
SIZES = {'small': (4, 1), 'medium': (6, 2), 'large': (9, 3)}


@dataclass(frozen=True)
class ParticipantPortrait:
    lines: tuple[str, ...]
    description: str


@lru_cache(maxsize=512)
def generate_portrait(participant_id, attributes, *, size='medium', plain=False):
    x_radius, y_radius = SIZES[size]
    width, height = 2*x_radius + 1, 2*y_radius + 1
    canvas = [[' '] * width for _ in range(height)]
    offers, needs = len(attributes.offers), len(attributes.needs)
    center = ('@' if plain else '●') if attributes.actor_type == 'person' else ('#' if plain else '■')
    canvas[y_radius][x_radius] = center
    spokes = [(x, y) for y in (-1, 0, 1) for x in (-1, 0, 1) if x or y]
    seed = sha256(f'{PORTRAIT_VERSION}:{participant_id}'.encode()).digest()
    spokes = sorted(spokes, key=lambda pair: seed[(pair[1]+1)*3 + pair[0]+1])
    domains = len(set(attributes.offers) | set(attributes.needs))
    # Interleave offers and needs so either remains visible when the glyph limit is reached.
    symbols = [glyph for i in range(min(8, max(offers, needs)))
               for count, glyph in ((offers, '+' if plain else '◆'), (needs, 'o' if plain else '○')) if i < count]
    for (dx, dy), symbol in zip(spokes, symbols):
        for step in range(1, x_radius if not dy else y_radius):
            x = x_radius + round(dx * step * (x_radius/y_radius if dy else 1))
            y = y_radius + dy * step
            canvas[y][x] = '-' if not dy else '|' if not dx else '/' if dx*dy < 0 else '\\'
        canvas[y_radius + dy*y_radius][x_radius + dx*x_radius] = symbol
    side, bar = ('|', '-') if plain else ('│', '─')
    tl, tr, bl, br = '+', '+', '+', '+'
    if not plain:
        tl, tr, bl, br = '╭', '╮', '╰', '╯'
    lines = (tl + bar*width + tr, *(side + ''.join(row) + side for row in canvas), bl + bar*width + br)
    description = f'{attributes.actor_type.title()} · {offers} recorded offers · {needs} recorded needs · {domains} recorded domains'
    if plain:
        description = description.replace(' · ', ' / ')
    return ParticipantPortrait(lines, description)
