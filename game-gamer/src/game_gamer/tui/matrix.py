"""Terminal matrix geometry over a caller-supplied directional projection."""
from dataclasses import dataclass
from enum import IntEnum
import unicodedata
from typing import Sequence

from .bands import band
from .text import display_width, pad


@dataclass(frozen=True)
class MatrixCell:
    row_id: str
    column_id: str
    value: int | None
    status: str = 'observed'


@dataclass(frozen=True)
class AxisLabel:
    id: str
    label: str


@dataclass(frozen=True)
class MatrixView:
    rows: Sequence[AxisLabel]
    columns: Sequence[AxisLabel]
    values: Sequence[Sequence[int | None]]
    exclude_self: bool = False

    def cell(self, row, column):
        row_id, column_id = self.rows[row].id, self.columns[column].id
        value = self.values[row][column]
        status = 'self' if self.exclude_self and row_id == column_id else 'unknown' if value is None else 'observed'
        return MatrixCell(row_id, column_id, value, status)


class Detail(IntEnum):
    COMPACT = 0
    STANDARD = 1
    DETAILED = 2


@dataclass
class MatrixViewport:
    row_offset: int = 0
    column_offset: int = 0
    detail: Detail = Detail.COMPACT
    fit: bool = False

    def handle(self, key):
        if key in {'+', '-'}:
            self.detail = Detail(min(2, max(0, self.detail + (1 if key == '+' else -1))))
        elif key == 'f':
            self.fit = True
        elif key == 'home':
            self.row_offset = self.column_offset = 0
        else:
            return False
        return True

    def window(self, rows, columns, row, column, row_capacity, column_capacity):
        def start(count, selected, capacity, offset):
            if self.fit:
                return min(max(0, count - capacity), max(0, selected - capacity // 2))
            if offset <= selected < offset + capacity:
                return min(offset, max(0, count - capacity))
            return selected // capacity * capacity

        self.row_offset = start(rows, row, row_capacity, self.row_offset)
        self.column_offset = start(columns, column, column_capacity, self.column_offset)
        self.fit = False
        return (range(self.row_offset, min(rows, self.row_offset + row_capacity)),
                range(self.column_offset, min(columns, self.column_offset + column_capacity)))


@dataclass(frozen=True)
class MatrixGrid:
    lines: list[str]
    styles: list[tuple]
    highlights: set[int]
    rows: range
    columns: range
    cell_width: int


def format_cell(cell, width=2, *, numeric=False, plain=False, selected=False, own=False):
    """Keep every cell at the chosen width. '+' means inspect for the full score."""
    if width < 2:
        raise ValueError('matrix_cell_width')
    marker = '>' if selected else '*' if own else ' '
    if cell.status == 'self':
        glyph = '-'
    elif cell.value is None:
        glyph = '?'
    elif numeric:
        glyph = str(cell.value)
        if display_width(glyph) > width - 1:
            glyph = '+'
    else:
        category = band(cell.value)
        glyph = category.ascii if plain else category.glyph
    return marker + pad(glyph, width - 1)


def render_matrix(view, viewport, *, row, column, width, height, own_id=None,
                  numeric=False, plain=False, incidence=False):
    if not view.rows or not view.columns:
        return MatrixGrid([], [], set(), range(0), range(0), 2)
    gutter = min(20, max(4, width - 8))
    selected = view.cell(row, column)
    if viewport.detail == Detail.COMPACT:
        cell_width = 2
    elif viewport.detail == Detail.STANDARD:
        cell_width = 3
    else:
        cell_width = min(12, max(5, len(str(selected.value)) + 2, display_width(view.columns[column].label) + 1))
        numeric = True
    row_count = max(1, height)
    column_count = max(1, (width - gutter) // cell_width)
    rows, columns = viewport.window(len(view.rows), len(view.columns), row, column, row_count, column_count)

    def caption(value):
        return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode() if plain else value

    headings = ''.join(pad(str(j + 1) if len(str(j + 1)) <= cell_width else '+', cell_width, centred=True)
                       for j in columns)
    labels = ''.join(pad(caption(view.columns[j].label), cell_width, centred=True) for j in columns)
    lines = [' ' * gutter + headings, ' ' * gutter + labels]
    styles, highlights = [], set()
    for i in rows:
        own_row = view.rows[i].id == own_id
        header = ('*' if own_row else ' ') + str(i + 1) + ' '
        line = pad(header + caption(view.rows[i].label), gutter)
        if own_row:
            highlights.add(len(lines))
        for j in columns:
            cell = view.cell(i, j)
            active = (i, j) == (row, column)
            line += format_cell(cell, cell_width, numeric=numeric or incidence, plain=plain, selected=active,
                                own=not incidence and cell.column_id == own_id)
            if cell.value is not None and cell.status != 'self' and not numeric:
                colour = ('#a3bd95' if cell.value else '#172331') if incidence else band(cell.value).colour
                styles.append((len(lines), gutter + (j - columns.start) * cell_width, cell_width,
                               '#111111' if cell.value >= (1 if incidence else 7) else '#eee8d5', colour, active))
        lines.append(line)
    return MatrixGrid(lines, styles, highlights, rows, columns, cell_width)
