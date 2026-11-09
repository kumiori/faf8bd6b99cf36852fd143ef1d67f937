from game_gamer.tui.network import draw_graph
from game_gamer.tui.overview import overview, select_scope


def test_overview_fits_disconnected_layers_and_aggregates_the_complete_roster():
    graph = {
        'nodes': [{'id': str(i), 'kind': 'person' if i < 39 else 'organisation'} for i in range(40)],
        'edges': [{'source_id': str(i), 'target_id': str(i+1), 'layer': 'connection'}
                  for i in range(35) if i != 30],
    }
    local = select_scope(graph, '0', 'local')
    community = select_scope(graph, '0', 'community')
    whole = select_scope(graph, '0', 'global')
    assert set(local.nodes) == {'0', '1'}
    assert set(community.nodes) == {str(i) for i in range(31)}
    assert len(whole.nodes) == 40 and len(whole.edges) == 34
    assert sorted(map(len, whole.components)) == [5, 31]
    assert whole.isolates == ['36', '37', '38', '39']
    assert set(select_scope(graph, '0', 'global', actor_type='organisation').nodes) == {'39'}

    visual = overview(whole, 32, 9, selected='39')
    assert len(visual['nodes']) <= 12
    assert sum(node['member_count'] for node in visual['nodes']) == 40
    assert visual['centre'] in {node['id'] for node in visual['nodes']}
    assert 0 < sum(edge['weight'] for edge in visual['edges']) < len(whole.edges)
    lines, _ = draw_graph(visual, 32, 9, plain=True, selected=visual['centre'], show_labels=False)
    assert len(lines) == 9 and all(len(line) == 32 for line in lines)
    assert any('@' in line for line in lines)
