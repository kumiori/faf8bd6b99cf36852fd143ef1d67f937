"""Terminal display-column measurement, separate from styling."""
import re
import unicodedata

from wcwidth import wcwidth, wcswidth

_ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))')


def clean(value):
    return ''.join(c for c in _ANSI.sub('', value) if c.isprintable() or c in '\n\t\u200d')


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).casefold()) if not unicodedata.combining(c))


def display_width(value):
    return max(0, wcswidth(clean(value).expandtabs(4)))


def clip(value, width):
    value = clean(value).expandtabs(4)
    if display_width(value) <= width:
        return value
    # Use the full prefix measurement to handle combining sequences and emoji.
    for end in range(1, len(value) + 1):
        if wcswidth(value[:end]) > width:
            return value[:end - 1].rstrip('\u200d')
    return value


def pad(value, width, *, centred=False):
    value = clip(value, width)
    spare = width - display_width(value)
    left = spare // 2 if centred else 0
    return ' ' * left + value + ' ' * (spare - left)


def column_slice(value, start, width):
    if start == 0:
        return clip(value, width)
    for i, character in enumerate(value):
        if wcwidth(character) > 0 and display_width(value[:i]) >= start:
            return clip(value[i:], width)
    return ''


def label(record):
    return str(record.get('display_name') or record.get('label') or record.get('domain') or record.get('id', ''))
