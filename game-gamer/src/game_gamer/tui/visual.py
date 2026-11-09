"""Shared visual roles and layout for full-screen terminal views."""

from itertools import zip_longest
import os

from .text import display_width, pad

PRIMARY = '#f5f5f5'
SECONDARY = '#949494'
NAVIGATION = '#5fd7d7'
ACTION = '#f0c75e'
CONFIRMED = '#87d787'
ERROR = '#ff8787'


def text_span(row, column, value, colour, *, bold=False):
    return row, column, display_width(value), colour, None, bold


def panel_columns(panels, *, row_offset=0, gutter=3):
    """Align panels and translate each panel's spans into screen coordinates."""
    columns, spans, column = [], [], 0
    for width, lines, styles in panels:
        columns.append([pad(line, width) for line in lines])
        spans.extend((row+row_offset, x+column, min(length, width-x), fg, bg, bold)
                     for row, x, length, fg, bg, bold in styles if x < width)
        column += width+gutter
    lines = [(' '*gutter).join(part or ' '*panel[0] for part, panel in zip(row, panels))
             for row in zip_longest(*columns)]
    return lines, spans


def motion_enabled(viewport):
    return (callable(getattr(viewport, 'poll_key', None))
            and os.getenv('COMMONS_REDUCED_MOTION', '').strip().lower() not in {'1', 'true', 'yes'}
            and not getattr(viewport, 'plain', False))
