import csv
from copy import deepcopy

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.montreal_network import projection, scoped_graph
from commons_game.montreal_sources import LAYER, import_montreal_network, read_sources

from test_matrix_navigation import app, world


def source_files(tmp_path, *, include_isolate=False):
    topology = tmp_path/'connexions.csv'
    statements = tmp_path/'description_strings.txt'
    with topology.open('w', newline='') as stream:
        csv.writer(stream).writerows([
            ('source', 'cible', 'remarque'),
            ('Alex Example', 'Casey Example', 'Arrow partly obscured'),
            ('Alex Example', 'Casey Example', 'Second transcription'),
            ('Casey Example', 'Zoë Source', ''),
        ])
    with statements.open('w', newline='') as stream:
        csv.writer(stream, delimiter='\t').writerows([
            ('Nom', 'Titre / fonction', 'Organisation', 'Pourquoi suis-je ici ?', 'Remarque'),
            ('Alex Example', 'Researcher', 'Fictional Lab', 'Share data. [illegible]', 'Uncertain ending'),
            ('Casey Example', 'Archivist', 'Fictional Archive', 'Compare sources.', ''),
            ('Zoë Source', '', '', 'Map connections.', 'Source identity only'),
            *([('Morgan Example', '', '', 'Observe the forum.', '')] if include_isolate else []),
        ])
    return read_sources(topology, statements)


def test_import_preserves_rows_flags_ambiguity_and_replays_a_saved_world(tmp_path):
    game = world()
    before = game.get_world()
    casey = next(row for row in before['actors'].values() if row['label'] == 'Casey Example')
    after = deepcopy(before)
    after['actors']['casey-duplicate'] = {**casey, 'id': 'casey-duplicate'}
    game._commit(before, after, 'fixture.second_casey')
    store = SQLiteStore(tmp_path/'old.sqlite', CommonsGame)
    store.initialise(game)
    previous_events = game.project('log')
    sources = source_files(tmp_path)
    preview = import_montreal_network(game, sources, dry_run=True)
    assert (preview['nodes'], preview['edges'], preview['statements']) == (3, 3, 3)
    assert (preview['matched'], preview['ambiguous'], preview['unmatched'], preview['duplicate_edges']) == (1, 1, 1, 1)
    assert game.project('log') == previous_events
    report = store.transact(lambda engine: import_montreal_network(engine, sources))
    assert report['changed']
    restored = SQLiteStore(store.path, CommonsGame).load()
    assert restored.project('log')[:-1] == previous_events
    assert restored.world_at(event=len(previous_events)) == after
    assert restored.get_world()['actors'] == after['actors']
    assert restored.replay().get_world() == restored.get_world()
    edges = [edge for edge in restored.project('network')['edges'] if edge['layer'] == LAYER]
    assert len(edges) == 3
    assert edges[0]['remarks'] == 'Arrow partly obscured'
    assert edges[0]['source_name'] == 'Alex Example' and edges[0]['target_name'] == 'Casey Example'
    assert edges[0]['provenance']['file'] == 'connexions.csv' and edges[0]['provenance']['line'] == 2
    assert not store.transact(lambda engine: import_montreal_network(engine, sources))['changed']
    pending = next(row for row in report['review'] if row['status'] == 'ambiguous')
    assert pending['candidate_actor_ids'] == sorted((casey['id'], 'casey-duplicate'))
    reviewed = store.transact(lambda engine: import_montreal_network(
        engine, sources, identities={pending['source_id']: casey['id']}))
    assert reviewed['ambiguous'] == 0
    current = store.load()
    assert current.get_world()['configuration'][LAYER]['statements'] == sources['statements']
    assert any(edge['target_id'] == casey['id'] for edge in current.project('network')['edges'] if edge['layer'] == LAYER)
    assert current.get_world() == current.replay().get_world()


def test_direct_workshop_explorer_keeps_layers_and_connection_inspection_separate(tmp_path):
    game = world()
    sources = source_files(tmp_path)
    assert import_montreal_network(game, sources)['ok']
    actors = {actor['label']: actor['id'] for actor in game.get_world()['actors'].values()}
    alex, casey = actors['Alex Example'], actors['Casey Example']
    assert game.submit({'key': 'recall', 'kind': 'recall_connection', 'actor': alex,
                        'target_id': casey, 'context_id': 'montreal-forum'})['ok']
    assert game.submit({'key': 'invite', 'kind': 'send_contact', 'actor': alex, 'recipient_id': casey,
                        'id': 'example-invitation', 'message': 'Compare sources?'})['ok']
    assert game.submit({'key': 'accept', 'kind': 'respond_contact', 'actor': casey,
                        'invitation_id': 'example-invitation', 'response': 'accept'})['ok']
    ui, viewport = app(game, choices=[4, 1, 2], answers=['Zoë'])
    before = game.project('log')
    ui.choose_mode()
    assert ui.route.kind == 'montreal_network'
    ui.width, ui.height = 144, 36
    screen = ui.build_screen()
    assert all(any(heading in line for line in screen.lines) for heading in ('DIRECTORY', 'PROFILE', 'NETWORK'))
    directory, graph, provenance, _ = projection(ui)
    assert directory.profiles[alex].motivation == 'Share data. [illegible]'
    assert provenance[alex][0]['statements'][0]['raw']['Remarque'] == 'Uncertain ending'
    assert {edge['display_group'] for edge in graph['edges']} == {'topology', 'recollections', 'connections'}
    ui.route.target = alex
    ui.handle('n', ui.build_screen())
    ui.handle('enter', ui.build_screen())
    assert ui.route.kind == 'montreal_connection'
    assert any('Arrow partly obscured' in line for line in ui.build_screen().lines)
    ui.handle('b', ui.build_screen())
    assert ui.route.target == alex
    ui.handle('L', ui.build_screen())
    assert 'Player recollections · 1 connections' in ui.build_screen().lines[1]
    ui.handle('L', ui.build_screen())
    assert 'Newly established connections · 1 connections' in ui.build_screen().lines[1]
    ui.handle('G', ui.build_screen())
    assert ui.route.kind == 'montreal_network_graph'
    ui.handle('+', ui.build_screen())
    ui.handle('b', ui.build_screen())
    assert ui.route.extra['zoom'] == 1.2 and ui.route.extra['graph_groups'] == ('connections',)
    ui.handle('/', ui.build_screen())
    assert [name for name, _ in ui.build_screen().entries] == ['Zoë Source']
    assert game.project('log') == before


def test_scope_keys_expand_membership_and_focus_without_world_writes(tmp_path):
    game = world()
    assert import_montreal_network(game, source_files(tmp_path, include_isolate=True))['ok']
    ui, _ = app(game, choices=[4, 1, 0, lambda item: item == ui.playing_actor])
    before = game.project('log')
    ui.choose_mode()
    ui.width, ui.height = 132, 30
    _, graph, _, _ = projection(ui)

    def names():
        return {node['display_name'] for node in scoped_graph(graph, ui.route).nodes.values()}

    screen = ui.build_screen()
    assert names() == {'Alex Example', 'Casey Example'}
    text = '\n'.join(screen.lines)
    assert 'MOTIVATION' in text and 'Share data.' in text
    assert 'Data stewardship' not in text
    ui.handle('D', screen)
    assert 'Data stewardship' in '\n'.join(ui.build_screen().lines)
    ui.handle('S', ui.build_screen())
    assert names() == {'Alex Example', 'Casey Example', 'Zoë Source'}
    ui.handle('S', ui.build_screen())
    assert names() == {'Alex Example', 'Casey Example', 'Zoë Source', 'Morgan Example'}
    ui.handle('T', ui.build_screen())  # Organisation filter in a person-only layer.
    assert not names()
    ui.handle('T', ui.build_screen())
    assert len(names()) == 4
    ui.width, ui.height = 52, 18
    narrow = ui.build_screen()
    assert '[GLOBAL]' in narrow.lines[0]
    assert any('NETWORK' in line for line in narrow.lines)
    assert not any('DIRECTORY' in line for line in narrow.lines)
    assert len(narrow.lines) <= ui.height - 7
    ui.handle('F', narrow)
    assert names() == {'Alex Example', 'Casey Example'}
    assert game.project('log') == before


def test_connection_source_is_opt_in(tmp_path):
    game = world()
    assert import_montreal_network(game, source_files(tmp_path))['ok']
    ui, _ = app(game, choices=[4])
    ui.choose_mode()
    ui.handle('n', ui.build_screen())
    ui.handle('enter', ui.build_screen())
    text = '\n'.join(ui.build_screen().lines)
    assert 'Arrow partly obscured' in text
    assert '"provenance"' not in text
    ui.handle('d', ui.build_screen())
    assert '"provenance"' in '\n'.join(ui.build_screen().lines)
