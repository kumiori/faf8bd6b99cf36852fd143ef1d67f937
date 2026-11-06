"""Minimal neutral text/span sink for the extracted Hack raster (no Rich runtime)."""
class Text:
    def __init__(self):
        self.parts = []
        self.spans = []
        self.length = 0

    def append(self, value, style=''):
        self.parts.append(value)
        if style:
            self.spans.append((self.length, len(value), style))
        self.length += len(value)

    @property
    def plain(self):
        return ''.join(self.parts)
