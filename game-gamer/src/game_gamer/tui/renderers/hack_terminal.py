# Extracted from PROTOCOL Hack, temporal_graph/renderers/terminal/projection.py.
# Upstream source and adaptations: docs/TUI.md.
# Camera, clipping, raster stepping, depth arbitration and arrow placement retained.
"""3D camera projection and clipped, depth-ordered terminal rasterisation."""
import math
from .raster_text import Text

STYLES = {}

def view(*args, **kwargs):
    raise ValueError("Supply an explicit read-only visual projection")


def project(coordinates, width, height, *, angle=0., axis='y', zoom=1., perspective=True):
    ids = list(coordinates)
    if not ids:
        return {}
    c, s = math.cos(angle), math.sin(angle)
    rotation = {'x': [[1, 0, 0], [0, c, -s], [0, s, c]],
                'y': [[c, 0, s], [0, 1, 0], [-s, 0, c]],
                'z': [[c, -s, 0], [s, c, 0], [0, 0, 1]]}[axis]
    x = [[sum(float(point[j]) * row[j] for j in range(3)) for row in rotation]
         for point in (coordinates[key] for key in ids)]
    scale = min(width / 20, height / 9) * zoom
    result = {}
    for key, (a, b, depth) in zip(ids, x):
        camera_distance = 18 + depth
        if perspective and camera_distance <= .5:
            continue
        factor = 18 / camera_distance if perspective else 1.
        result[key] = (width / 2 + a * scale * 2 * factor, height / 2 - b * scale * factor, depth)
    return result


def raster(frame, width, height, *, layers, mode='structural', selected=None, ascii_only=False,
           angle=0., axis='y', zoom=1., perspective=True, separation='superposed', backbone=False,
           phase=1., positions=None, removed=None, visual=None, projected=None):
    width, height = max(8, width), max(3, height)
    visual = view(frame, layers=layers, separation=separation, backbone=backbone) if visual is None else visual
    coords = {n['visual_id']: n['position'] for n in visual['nodes']}
    if positions and separation != 'exploded':
        coords = {key: value['position'] for key, value in positions.items() if value['opacity'] > .05}
    points = (project(coords, width, height, angle=angle, axis=axis, zoom=zoom, perspective=perspective)
              if projected is None else projected)
    cells = {}
    def put(x, y, z, character, color, bold=False):
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < width and 0 <= iy < height:
            if (ix, iy) not in cells or z <= cells[ix, iy][0]:
                cells[ix, iy] = (z, character, color, bold)
    edges = visual['edges']
    if removed and phase < 1:
        edges = edges + [{**e, 'visual_source': e['source'], 'visual_target': e['target'], 'fading': True} for e in removed]
    added = {e['id'] for e in frame['changes']['edges_added']}
    for edge in edges:
        a, b = points.get(edge['visual_source']), points.get(edge['visual_target'])
        if a is None or b is None:
            continue
        color = edge.get('colour', STYLES.get(edge['layer'], {'color': '#aaaaaa'})['color'])
        steps = min(4 * (width + height), max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])))))
        forming = mode == 'crystal' and edge['id'] in added
        limit = phase if forming else 1.
        for step in range(steps + 1):
            fraction = step / steps
            if fraction > limit or edge.get('fading') and (step % 4 != 0 or phase > .8):
                continue
            x, y, z = [a[k] + fraction * (b[k] - a[k]) for k in range(3)]
            if edge['layer'] == 'organizational' or edge.get('pattern') == 'solid':
                dx, dy = b[0]-a[0], b[1]-a[1]
                character = ('-' if ascii_only else '─') if abs(dy) < .4*abs(dx) else ('|' if ascii_only else '│') if abs(dx) < .4*abs(dy) else ('/' if dx*dy<0 else '\\') if ascii_only else ('╱' if dx*dy<0 else '╲')
            else:
                character = '.' if ascii_only else ('⠂' if edge['layer'] == 'shared_sectors' else '·')
            if edge['directed'] is True and abs(fraction - .65) < 1 / steps:
                character = ('>' if b[0] >= a[0] else '<') if abs(b[0] - a[0]) > abs(b[1] - a[1]) else ('v' if b[1] > a[1] else '^')
            if edge.get('unknown_marker') and abs(fraction - .5) < 1 / steps:
                character = '?'
            put(x, y, z + .2, character, color, forming or edge['weight'] >= 3)
    born = {n['id'] for n in frame['changes']['nodes_added']}
    node_index = {n['visual_id']: n for n in visual['nodes']}
    for key, point in sorted(points.items(), key=lambda item: -item[1][2]):
        node = node_index.get(key)
        if node is None:
            if phase < 1:
                put(*point, '.' if ascii_only else '◌', '#6f7781')
            continue
        participant = node['entity_type'] == 'participant'
        char = ('o' if participant else '?') if ascii_only else ('●' if participant else '◇' if node['entity_type'] == 'unknown' else '◆')
        char = node.get('ascii_symbol' if ascii_only else 'symbol', char)
        active = node['id'] == selected
        color = '#ffffff' if active else node.get('colour', '#ffc890' if participant else '#c7b9ef')
        if mode == 'crystal' and node['id'] in born and phase < .85:
            put(point[0] - 1, point[1], point[2], '(' if ascii_only else '◌', color)
            put(point[0] + 1, point[1], point[2], ')' if ascii_only else '◌', color)
        put(*point, '@' if active else char, color, active or node['id'] in born and phase < 1)
    result = Text()
    for y in range(height):
        for x in range(width):
            cell = cells.get((x, y))
            result.append(cell[1] if cell else ' ', style=(('bold ' if cell[3] else '') + cell[2]) if cell else '')
        if y + 1 < height:
            result.append('\n')
    return result
