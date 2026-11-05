"""Regression seams: graph rendering, terminal navigation and authoritative restart."""
from commons_game.network_view import draw_graph, focus_graph


def test_focused_graph_keeps_actor_context_without_inventing_relationships():
    graph = {'nodes': [{'id': key, 'kind': kind, 'label': key}
                       for key, kind in [('Alex', 'person'), ('Casey', 'person'),
                                         ('Org', 'organisation'), ('Isolated', 'person'),
                                         ('Terms', 'agreement')]],
             'edges': [{'id': 'ac', 'source_id': 'Alex', 'target_id': 'Casey',
                        'kind': 'knows', 'layer': 'declared', 'directed': True},
                       {'id': 'ao', 'source_id': 'Alex', 'target_id': 'Org',
                        'kind': 'affiliated_with', 'layer': 'declared', 'directed': True}]}
    first = focus_graph(graph, 'Alex', related='Org', limit=1)
    second = focus_graph(graph, 'Casey', limit=1)
    assert set(first['context_actor_ids']) == {'Casey', 'Isolated'}
    assert set(second['context_actor_ids']) == {'Org', 'Isolated'}
    assert first['isolated_actor_ids'] == second['isolated_actor_ids'] == {'Isolated'}
    for visual in (first, second):
        _, spans = draw_graph(visual, 80, 18)
        assert len([style for style in spans if style[3] == '#465060']) == 2
        assert all(record in graph['edges'] for edge in visual['edges'] for record in edge['records'])
    # Isolated is the only ring marker; it stays in place when the foreground changes.
    locations = []
    for visual in (first, second):
        lines, _ = draw_graph(visual, 80, 18)
        locations.append([(row, line.index('∘')) for row, line in enumerate(lines) if '∘' in line])
    assert locations[0] == locations[1] and len(locations[0]) == 1


def test_global_navigation_restores_network_and_contract_decision_context():
    from test_relational_navigation import proposed

    ui, contract = proposed()
    ui.open_network()
    screen = ui.build_screen()
    ui.handle('down', screen)
    ui.handle('+', ui.build_screen())
    before = ui.route.target, ui.route.index, ui.route.extra.copy()
    ui.handle('g', ui.build_screen())
    ui.handle('e', ui.build_screen())
    assert ui.route.kind == 'network'
    assert (ui.route.target, ui.route.index, ui.route.extra) == before
    ui.handle('tab', ui.build_screen())
    assert ui.build_screen().show_entries
    ui.push('inspect', contract)
    screen = ui.build_screen()
    assert 'Proposing does not accept' in '\n'.join(screen.lines)
    assert any(action[1][1]['kind'] == 'accept' for action in screen.decisions)
    assert all(not (isinstance(target, tuple) and target[0] == 'decision') for _, target in screen.entries)
    before_world = ui.world(), ui.current().project('log')
    ui.handle('tab', screen)
    ui.handle('esc', ui.build_screen())
    assert ui.route.kind == 'network'
    assert (ui.route.target, ui.route.index, ui.route.extra) == before
    assert ui.build_screen().show_entries
    assert before_world == (ui.world(), ui.current().project('log'))


def test_planar_fit_keeps_edges_and_nodes_clear_of_long_labels():
    graph = {'nodes': [{'id': key, 'kind': 'person', 'label': key*30} for key in ('A', 'B')],
             'edges': [{'id': 'ab', 'source_id': 'A', 'target_id': 'B', 'kind': 'knows',
                        'layer': 'declared', 'directed': True}]}
    visual = focus_graph(graph, 'A')
    for width, height in ((52, 7), (132, 24)):
        lines, spans = draw_graph(visual, width, height, selected='A', plain=True, margin=(3, 2))
        assert len(lines) == height and all(len(line) == width for line in lines)
        assert any('~' in line for line in lines)
        assert any('@' in line for line in lines)
        edge_cols = []
        for row, col, length, colour, _, _ in spans:
            if colour == '#c4a7e7':  # recorded edge, not a node label
                assert set(lines[row][col:col+length]) <= {'-', '>', '<', '|', '/', '\\'}
                edge_cols.extend(range(col, col+length))
        assert max(edge_cols)-min(edge_cols) >= width-10


def test_invitation_and_versioned_contract_survive_process_restart_and_every_prefix(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame, load_scenario
    from commons_game.scenario import demo_commands

    store = SQLiteStore(tmp_path/'freeze.sqlite', CommonsGame)
    store.initialise(load_scenario('bilateral-logs'))

    def submit(kind, actor, *, error=None, **payload):
        before = store.load().project('log')
        result = store.submit({'key': f'freeze-{len(before)}-{kind}', 'kind': kind, 'actor': actor, **payload})
        if error:
            assert result['errors'] == [error]
            assert store.load().project('log') == before
        else:
            assert result['ok'], result
            assert len(store.load().project('log')) == len(before) + 1

    submit('draft_contact', 'researcher', id='contact', recipient_id='verifier', message='Discuss a synthetic case?')
    submit('publish_contact', 'researcher', invitation_id='contact')
    submit('respond_contact', 'researcher', invitation_id='contact', response='accept', error='recipient_required')
    submit('respond_contact', 'verifier', invitation_id='contact', response='accept')
    assert not store.load().project('agreements')
    submit('send_contact', 'researcher', id='declined', recipient_id='verifier', message='Another synthetic discussion?')
    submit('respond_contact', 'verifier', invitation_id='declined', response='decline')

    commands = demo_commands()
    for idx, command in enumerate(commands):
        result = store.submit(command)
        assert result['ok'], result
        if idx == 0:
            assert not store.load().project('agreements')[0]['versions'][0]['acceptances']
            submit('accept', 'researcher', agreement_id='agreement-main', version=1)
        if idx == 1:
            previous, current = store.load().project('agreements')[0]['versions']
            assert set(previous['acceptances']) == {'researcher'}
            assert not current['acceptances']
            submit('accept', 'custodian', agreement_id='agreement-main', version=1, error='agreement_version_conflict')
        if idx == len(commands)-2:
            assert store.load().project('agreements')[0]['outcome_status'] == 'unverified'

    # Rejection is a separate historical agreement, not a withdrawal of the verified one.
    rejectable = {**commands[0], 'key': 'rejectable', 'id': 'rejectable'}
    assert store.submit(rejectable)['ok']
    submit('reject', 'verifier', agreement_id='rejectable', version=1, reason='Observer', error='party_required')
    submit('reject', 'custodian', agreement_id='rejectable', version=1, reason='Declined on the terms')
    game = store.load()
    world, log = game.get_world(), game.project('log')
    assert world['agreements']['agreement-main']['outcome_status'] == 'verified'
    assert world['agreements']['rejectable']['status'] == 'rejected'
    assert world['relationships']['contact']['status'] == 'accepted'
    assert world['relationships']['declined']['status'] == 'declined'
    assert 'acknowledged:declined' not in world['relationships']
    for index in range(1, len(log)+1):
        prefix = CommonsGame.from_log(log[:index])
        assert prefix.get_world() == game.world_at(event=index)
        assert prefix.project('network') == game.project('network', at=index)
    graph = game.project('network')
    assert {edge['kind'] for edge in graph['edges']} >= {'contact_invitation', 'acknowledged_connection', 'party_to', 'has_evidence'}
    assert game.replay().get_world() == world

    before = store.path.read_bytes()
    cli = [sys.executable, '-B', '-m', 'commons_game', '--db', str(store.path)]
    cwd = Path(__file__).resolve().parents[1]
    restored = subprocess.run(cli+['show', 'network'], cwd=cwd, capture_output=True, text=True, check=True, timeout=10)
    assert json.loads(restored.stdout) == graph
    replay = subprocess.run(cli+['replay'], cwd=cwd, capture_output=True, text=True, check=True, timeout=10)
    assert json.loads(replay.stdout) == {'identical': True, 'version': len(log)}
    assert store.path.read_bytes() == before
