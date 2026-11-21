from game_gamer.tui.network import draw_graph, focus_graph, layout_graph
from game_gamer.tui.renderers.hack_terminal import raster


def test_clipped_braille_lines_keep_layer_colour_arrow_and_node_glyphs():
    frame = {'changes': {'nodes_added': [], 'edges_added': []}}
    visual = {'nodes': [
        {'id': 'source', 'visual_id': 'source', 'position': [1, 2, 4], 'entity_type': 'participant', 'symbol': '●'},
        {'id': 'target', 'visual_id': 'target', 'position': [18, 2, 4], 'entity_type': 'mission', 'symbol': '◎'},
    ], 'edges': [
        {'id': 'horizontal', 'visual_source': 'left', 'visual_target': 'right',
         'layer': 'documented', 'pattern': 'solid', 'directed': True, 'weight': 1, 'colour': '#abc123'},
    ]}
    points = {'source': (1, 2, 4), 'target': (18, 2, 4), 'left': (-1e6, 2, 0), 'right': (1e6, 2, 0)}
    result = raster(frame, 20, 6, layers={'documented'}, visual=visual, projected=points, edge_renderer='braille')
    row = result.plain.splitlines()[2]
    assert len(row) == 20 and row[1] == '●' and row[18] == '◎'
    assert '→' in row and sum(0x2800 < ord(cell) < 0x2900 for cell in row) == 17
    assert any('#abc123' in style for _, _, style in result.spans)


def test_renderers_share_layout_across_camera_changes_and_ascii_fallback():
    graph = {'nodes': [{'id': key, 'label': key, 'kind': 'person'} for key in ('a', 'b', 'c')],
             'edges': [{'id': 'record', 'source_id': 'a', 'target_id': 'b', 'kind': 'transcription',
                        'layer': 'montreal_2026_reconstructed', 'directed': True}]}
    visual = focus_graph(graph, 'a', scope='whole')
    for angle, zoom in ((0., 1.), (.4, 1.3), (.8, .7)):
        layout = layout_graph(visual, 60, 20, angle=angle, zoom=zoom)
        braille, _ = draw_graph(visual, 60, 20, angle=angle, zoom=zoom)
        legacy, _ = draw_graph(visual, 60, 20, angle=angle, zoom=zoom, edge_renderer='character')
        assert any(0x2800 < ord(cell) < 0x2900 for row in braille for cell in row)
        assert not any(0x2800 < ord(cell) < 0x2900 for row in legacy for cell in row)
        for x, y, _ in layout.points.values():
            column, row = round(x), round(y)
            if 0 <= row < 20 and 0 <= column < 60:
                assert braille[row][column] == legacy[row][column] == '●'
        ascii_rows, _ = draw_graph(visual, 60, 20, angle=angle, zoom=zoom, plain=True)
        assert all(row.isascii() for row in ascii_rows)


def test_labels_numbers_and_annotations_toggle_independently_and_keep_focus_visible():
    graph = {'nodes': [{'id': key, 'label': name, 'kind': 'person'}
                       for key, name in [('a', 'Aster'), ('b', 'Beryl'), ('c', 'Cedar')]],
             'edges': [{'source_id': source, 'target_id': target, 'kind': 'transcription',
                        'layer': 'montreal_2026_reconstructed', 'directed': True}
                       for source, target in [('a', 'b'), ('b', 'c')]]}
    visual = focus_graph(graph, 'a', scope='whole')
    lines, styles = draw_graph(visual, 60, 20, selected='a', show_labels=True, show_numbers=False,
                               edge_annotations=False, selected_only=True, emphasise=True)
    canvas = '\n'.join(lines)
    assert 'Aster' in canvas and '@' in canvas and 'Beryl' not in canvas
    assert not set('123→←↑↓') & set(canvas)
    assert {'#5fd7d7', '#465060'} <= {foreground for _, _, _, foreground, _, _ in styles}
    lines, _ = draw_graph(visual, 60, 20, selected='a', show_labels=False, show_numbers=True)
    canvas = '\n'.join(lines)
    assert 'Aster' not in canvas and '1' in canvas and set('→←↑↓') & set(canvas)
    assert all(edge['directed'] for edge in visual['edges'])
