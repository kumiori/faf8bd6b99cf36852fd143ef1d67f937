"""Clipped integer line rasterisation on the 2 × 4 Braille dot grid."""

DOTS = ((1, 8), (2, 16), (4, 32), (64, 128))


def _clip(a, b, width, height):
    """Liang–Barsky bounds as fractions of the original line."""
    start, end = 0.0, 1.0
    for origin, delta, maximum in zip(a, (b[0]-a[0], b[1]-a[1]), (width-1, height-1)):
        if delta == 0:
            if not 0 <= origin <= maximum:
                return None
            continue
        lo, hi = sorted((-origin/delta, (maximum-origin)/delta))
        start, end = max(start, lo), min(end, hi)
        if start > end:
            return None
    return start, end


def _line(x, y, end_x, end_y):
    dx, dy = abs(end_x-x), -abs(end_y-y)
    sx, sy = (1 if x < end_x else -1), (1 if y < end_y else -1)
    error = dx + dy
    while True:
        yield x, y
        if (x, y) == (end_x, end_y):
            return
        twice = 2 * error
        if twice >= dy:
            error += dy
            x += sx
        if twice <= dx:
            error += dx
            y += sy


def draw_edges(edges, points, width, height, *, colour_for, progress, put):
    pixels = {}
    marks = []
    for edge in edges:
        a, b = points.get(edge['visual_source']), points.get(edge['visual_target'])
        if a is None or b is None:
            continue
        # Cell-centre coordinates align the four vertical dots with node glyphs.
        start = (2*a[0]+.5, 4*a[1]+1.5)
        finish = (2*b[0]+.5, 4*b[1]+1.5)
        interval = _clip(start, finish, width*2, height*4)
        if interval is None:
            continue
        lo, hi = interval
        limit, bold = progress(edge)
        hi = min(hi, limit)
        if hi < lo:
            continue
        delta = tuple(end-begin for begin, end in zip(start, finish))
        first, last = (tuple(round(v+t*d) for v, d in zip(start, delta)) for t in (lo, hi))
        steps = max(abs(last[0]-first[0]), abs(last[1]-first[1]), 1)
        colour = colour_for(edge)
        pattern = edge.get('pattern')
        distance = max(abs(delta[0]), abs(delta[1]))
        for index, (x, y) in enumerate(_line(*first, *last)):
            fraction = lo + (hi-lo)*index/steps
            phase = int(fraction*distance)
            if pattern == 'dotted' and phase % 5 != 0 or pattern == 'dashed' and phase % 12 >= 8:
                continue
            if edge.get('fading') and phase % 4 != 0:
                continue
            depth = a[2] + fraction*(b[2]-a[2]) + .2
            cell = pixels.setdefault((x//2, y//4), {})
            dot = DOTS[y % 4][x % 2]
            if dot not in cell or depth < cell[dot][0]:
                cell[dot] = (depth, colour, bold)
        if hi > lo and (edge.get('directed') or edge.get('unknown_marker')):
            fraction = lo + (hi-lo)*.65
            dx, dy = b[0]-a[0], b[1]-a[1]
            arrow = ('→' if dx >= 0 else '←') if abs(dx) >= abs(dy) else ('↓' if dy >= 0 else '↑')
            x, y, depth = (a[k]+fraction*(b[k]-a[k]) for k in range(3))
            marks.append((x, y, depth+.2, '?' if edge.get('unknown_marker') else arrow, colour, bold))

    for (x, y), dots in pixels.items():
        depth, colour, bold = min(dots.values())
        # A terminal cell has one foreground. Keep the front colour's dots only.
        mask = sum(dot for dot, value in dots.items() if value[1] == colour)
        put(x, y, depth, chr(0x2800+mask), colour, bold, priority=2)
    for marker in marks:
        put(*marker, priority=1)
