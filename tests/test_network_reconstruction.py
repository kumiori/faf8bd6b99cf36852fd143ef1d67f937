"""Montreal host exercises the shared directory, viewport, and actor session."""
from game_gamer.tui.text import display_width

from commons_game import load_scenario
from commons_game.fullscreen import FullScreenTerminal
from test_matrix_navigation import FakeViewport, app


def enter_reconstruction(ui):
    ui.choose_mode()
    assert ui.route.kind == 'exercises'
    ui.route.index = 3
    ui.handle('enter', ui.build_screen())
    intro = ui.build_screen()
    ui.handle('enter', intro)
    return intro


def test_fourth_path_preserves_selection_and_renders_narrow_intermediate_and_wide():
    ui, _ = app(choices=[3])
    intro = enter_reconstruction(ui)
    assert 'Can we reconstruct the network we created together?' in intro.lines
    ui.width, ui.height = 52, 20
    screen = ui.build_screen()
    assert any('DIRECTORY' in line for line in screen.lines)
    assert not any('PROFILE' in line for line in screen.lines)
    ui.handle('down', screen)
    ui.handle('enter', ui.build_screen())
    selected = ui.route.target
    profile = ui.build_screen()
    assert any('Motivation: Not yet recorded' in line for line in profile.lines)
    assert any('Offers: Coalition building' in line for line in profile.lines)
    ui.handle('tab', profile)
    assert any('NETWORK' in line for line in ui.build_screen().lines)
    ui.width, ui.height = 93, 27
    assert any('DIRECTORY' in line and 'NETWORK' in line for line in ui.build_screen().lines)
    ui.width, ui.height = 141, 34
    wide = ui.build_screen()
    assert any(all(region in line for region in ('DIRECTORY', 'PROFILE', 'NETWORK')) for line in wide.lines)
    assert all(display_width(line) <= 139 for line in wide.lines)
    ui.handle('i', wide)
    ui.handle('b', ui.build_screen())
    assert ui.route.target == selected and ui.route.region == 'network'


def test_connect_recollects_without_creating_an_invitation_or_contract():
    ui, port = app(choices=[3, 0], answers=['y'])
    enter_reconstruction(ui)
    ui.handle('down', ui.build_screen())
    target, actor = ui.route.target, ui.playing_actor
    ui.handle('c', ui.build_screen())
    menu = port.drawn[-2][1]
    assert menu[:3] == ['We connected in Montréal', 'I would like to connect now',
                        'We already knew each other before Montréal']
    claim, = [row for row in ui.world()['relationships'].values() if row['kind'] == 'recollection_claim']
    assert (claim['source_id'], claim['target_id']) == (actor, target)
    assert not ui.world()['agreements']
    assert not any(row['kind'] == 'contact_invitation' for row in ui.world()['relationships'].values())
    assert ui.build_screen().title == 'RECOLLECTION RECORDED'
    ui.handle('enter', ui.build_screen())
    assert any('1 directed claims' in line for line in ui.build_screen().lines)


def test_other_commons_scenarios_keep_their_original_paths():
    viewport = FakeViewport(choices=[0])
    ui = FullScreenTerminal(load_scenario('bilateral-logs'), viewport=viewport)
    ui.choose_mode()
    assert len(viewport.drawn[-1][1]) == 5


def test_optional_source_import_is_atomic_idempotent_and_restored_by_a_new_process(tmp_path):
    import json
    import subprocess
    import sys

    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame
    from commons_game.ecosystem_import import import_reconstruction_sources
    from test_matrix_navigation import world
    import pytest

    store = SQLiteStore(tmp_path/'sources.sqlite', CommonsGame)
    store.initialise(world())
    actors = [actor['id'] for actor in store.load().get_world()['actors'].values() if actor['kind'] == 'person'][:2]
    document = {'schema': 'game-gamer/reconstruction-sources/v1', 'records': [
        {'id': 'source-photo', 'kind': 'whiteboard_photo', 'context_id': 'montreal-forum', 'reference': 'photo:one'},
        {'id': 'source-link', 'kind': 'whiteboard_connection', 'context_id': 'montreal-forum',
         'reference': 'transcription:one', 'source_id': actors[0], 'target_id': actors[1],
         'directed': None, 'observation': 'possible'},
    ]}
    result = store.transact(lambda game: import_reconstruction_sources(game, document))
    assert result['ok'] and len(result['imported']) == 2
    before = store.load().project()
    assert store.transact(lambda game: import_reconstruction_sources(game, document))['unchanged'] == 2
    changed = json.loads(json.dumps(document))
    changed['records'][0]['reference'] = 'different'
    with pytest.raises(ValueError, match='reconstruction_source_conflict'):
        store.transact(lambda game: import_reconstruction_sources(game, changed))
    assert store.load().project() == before
    snapshot = tmp_path/'sources.json'
    snapshot.write_text(json.dumps(document))
    response = subprocess.run([sys.executable, '-B', '-m', 'commons_game', '--db', str(store.path),
                               'import-reconstruction-sources', str(snapshot)], capture_output=True, text=True, check=True)
    assert json.loads(response.stdout)['unchanged'] == 2
    restored = store.load()
    edge = next(edge for edge in restored.project('network')['edges'] if edge['layer'] == 'historical_whiteboard')
    assert edge['directed'] is None and edge['observation'] == 'possible'
    assert restored.get_world() == restored.replay().get_world()


def test_inviting_from_the_exercise_uses_the_existing_recipient_inbox():
    ui, _ = app(choices=[3, 1, 0], answers=['Would you like to reconnect?', '', 'y'])
    enter_reconstruction(ui)
    ui.handle('down', ui.build_screen())
    selected, actor = ui.route.target, ui.playing_actor
    ui.handle('c', ui.build_screen())
    invitations = [r for r in ui.world()['relationships'].values() if r['kind'] == 'contact_invitation']
    invitation, = invitations
    assert invitation['status'] == 'sent'
    assert (invitation['source_id'], invitation['target_id']) == (actor, selected)
    assert not any(r['kind'] == 'recollection_claim' for r in ui.world()['relationships'].values())
    ui.handle('b', ui.build_screen())
    assert ui.route.kind == 'reconstruction' and ui.route.target == selected
    from commons_game.player import ActorSession
    session = ActorSession(ui.game, selected)
    assert any(item['id'] == invitation['id'] for item in session.inbox_records())


def test_cancel_and_discard_do_not_add_a_claim_or_change_player():
    ui, _ = app(choices=[3, 0], answers=['n'])
    enter_reconstruction(ui)
    ui.handle('down', ui.build_screen())
    actor, before = ui.playing_actor, ui.current().project('log')
    ui.handle('c', ui.build_screen())
    assert before == ui.current().project('log')
    assert ui.playing_actor == actor


def test_facet_apply_clear_preserves_selection_and_does_not_mutate_the_world():
    ui, _ = app(choices=[3])
    enter_reconstruction(ui)
    ui.handle('down', ui.build_screen())
    selected = ui.route.target
    before = ui.current().project('log')
    ui.handle('f', ui.build_screen())
    assert 'People matching: 3' in ui.build_screen().lines
    ui.route.index = 2  # Offers
    ui.handle('enter', ui.build_screen())
    facet = ui.build_screen()
    assert all('(' in title and ')' in title for title, _ in facet.entries)
    ui.route.index = next(i for i, (_, value) in enumerate(facet.entries) if value.payload == 'Data stewardship')
    ui.handle('enter', facet)
    ui.handle('b', ui.build_screen())
    assert 'People matching: 1' in ui.build_screen().lines
    ui.route.index = 5  # Apply
    ui.handle('enter', ui.build_screen())
    assert len(ui.build_screen().entries) == 1
    ui.handle('f', ui.build_screen())
    ui.route.index = 6  # Clear, then Apply
    ui.handle('enter', ui.build_screen())
    ui.route.index = 5
    ui.handle('enter', ui.build_screen())
    assert ui.build_screen().entries and ui.route.target == selected
    assert ui.current().project('log') == before


def test_exercise_directory_is_people_only_and_graph_provenance_is_available():
    ui, _ = app(choices=[3])
    enter_reconstruction(ui)
    screen = ui.build_screen()
    assert all(ui.world()['actors'][target]['kind'] == 'person' for _, target in screen.entries)
    selected = ui.route.target
    ui.handle('G', screen)
    assert ui.route.kind == 'reconstruction_graph'
    ui.handle('v', ui.build_screen())
    assert ui.route.extra['graph_view'] == 'collective'
    ui.handle('L', ui.build_screen())
    assert any('Montréal reconstruction' in title for title, _ in ui.build_screen().entries)
    ui.handle('b', ui.build_screen())
    ui.handle('d', ui.build_screen())
    assert ui.build_screen().title == 'CONNECTION / PROVENANCE'
    ui.handle('b', ui.build_screen())
    ui.handle('b', ui.build_screen())
    assert ui.route.target == selected


def test_external_commit_is_reflected_while_inspecting_a_filter(tmp_path):
    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame
    from test_matrix_navigation import world
    store = SQLiteStore(tmp_path/'shared.sqlite', CommonsGame)
    store.initialise(world())
    ui, _ = app(store.load(), choices=[3])
    ui.store = store
    ui.refresh()
    enter_reconstruction(ui)
    ui.build_screen()
    ui.handle('f', ui.build_screen())
    # A second client records a recollection while this player is in the filter inspector.
    from commons_game.catalogue import people
    roster = [actor['id'] for actor in people(ui.world())][:2]
    assert store.submit({'key': 'remote', 'kind': 'recall_connection', 'actor': roster[0],
                         'target_id': roster[1], 'context_id': 'montreal-forum'})['ok']
    ui.refresh()
    assert ui.build_screen().title == 'FILTER PEOPLE'
    ui.handle('b', ui.build_screen())
    assert any('1 directed claims' in line for line in ui.build_screen().lines)


def test_tutorials_use_practice_roles_while_the_main_player_and_world_are_preserved():
    from commons_game.exercises import session
    for index in range(3):
        ui, _ = app(choices=[3], answers=['y']*20)
        initial_history, actor = ui.current().project('log'), ui.playing_actor
        ui.choose_mode()
        ui.route.index = index
        ui.handle('enter', ui.build_screen())
        practice = session(ui)
        while not practice.complete:
            ui.handle('enter', ui.build_screen())
        assert 'TUTORIAL COMPLETE' in ui.build_screen().lines
        assert ui.current().project('log') == initial_history
        assert ui.playing_actor == actor


def test_curator_indicator_and_controls_follow_actual_permissions():
    from commons_game import CommonsGame
    from game_gamer.schema.definitions import initialise_legacy
    from commons_game.fullscreen import Screen
    from commons_game.curator import allowed
    # An ordinary player's shortcut cannot enable a curator role.
    ui, _ = app()
    before = ui.current().project('log')
    ui.handle('u', ui.build_screen())
    assert not allowed(ui) and ui.current().project('log') == before
    screen = ui.build_screen()
    ui.decorate_screen(screen)
    assert not screen.header_indicator
    # Provisioning occurs in a trusted world definition, outside player commands.
    import json
    from pathlib import Path
    spec = json.loads((Path(__file__).parents[1]/'commons_game/scenarios/bilateral-logs.json').read_text())
    spec['actors'][0]['roles'].append('curator')
    game = initialise_legacy(CommonsGame(), spec, 'curator-fixture')
    ui, _ = app(game)
    ui.assume_actor(game.get_world()['actors'][spec['actors'][0]['id']])
    screen = Screen('World')
    ui.decorate_screen(screen)
    assert screen.header_indicator == '◆ CURATOR' and screen.header_colour == '#f0c75e'
    ui.handle('u', screen)
    assert ui.route.kind == 'curator'
    assert any('Preview' in label for label, _ in ui.build_screen().panel.entries)


def test_an_open_inspector_survives_a_recorded_visibility_correction():
    from commons_game import CommonsGame
    from game_gamer.schema.definitions import initialise_legacy
    from pathlib import Path
    import json
    spec = json.loads((Path(__file__).parents[1]/'commons_game/scenarios/bilateral-logs.json').read_text())
    spec['actors'][0]['roles'].append('curator')
    game = initialise_legacy(CommonsGame(), spec, 'curator-inspector')
    ui, _ = app(game)
    actor = spec['actors'][0]['id']
    target = spec['actors'][-1]['id']
    ui.push('inspect', target)
    assert game.submit({'key': 'hide', 'kind': 'set_profile_visibility', 'actor': actor,
                        'target_id': target, 'visibility': 'hidden', 'reference': 'Pending correction'})['ok']
    ui.refresh()
    assert ui.build_screen().title == 'PROFILE / DISCOVERY UPDATED'
    ui.handle('h', ui.build_screen())
    assert any('changed profile visibility' in label for label, _ in ui.build_screen().entries)
