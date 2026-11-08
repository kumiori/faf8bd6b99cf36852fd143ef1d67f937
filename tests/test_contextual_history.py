from copy import deepcopy
from dataclasses import replace

from commons_game import load_scenario
from commons_game.fullscreen import FullScreenTerminal
from commons_game.curator_access import provision_curator
from game_gamer.projections.history import HistoryFilters, history_rows
from game_gamer.runtime.curation_requests import records
from test_matrix_navigation import app, FakeViewport
from test_network_reconstruction import enter_reconstruction


def choose_panel(ui, action):
    screen = ui.build_screen()
    ui.route.index = next(i for i, (_, value) in enumerate(screen.panel.entries) if value == action)
    ui.handle('enter', screen)


def test_panel_targets_the_inspected_person_and_preserves_the_underlying_screen():
    ui, _ = app()
    initial = deepcopy(ui.current().project('log'))
    ui.route.column = 1
    ui.handle('enter', ui.build_screen())
    pair = ui.focused_relation
    ui.route.index = 1
    ui.handle('enter', ui.build_screen())
    inspected = ui.route.target
    assert inspected != ui.playing_actor
    ui.handle('u', ui.build_screen())
    panel = ui.build_screen()
    assert panel.panel is not None
    assert ui.route.target == inspected
    assert 'Stable ID: '+inspected in panel.panel.lines
    assert any(action == ('request', 'correction') for _, action in panel.panel.entries)
    assert all(action not in {'correct', 'visibility', 'preview', 'reverse'} for _, action in panel.panel.entries
               if isinstance(action, str))
    ui.handle('u', panel)
    assert ui.route.target == inspected and ui.focused_relation == pair
    assert ui.current().project('log') == initial


def test_panel_follows_network_selection_and_preserves_type_layer_and_zoom():
    ui, _ = app(choices=[0])
    ui.open_network()
    ui.route.extra.update(scope='whole', object_type='person', categories=['Inferred complementarities'], zoom=1.2)
    screen = ui.build_screen()
    ui.handle('down', screen)
    selected = ui.build_screen().entries[ui.route.index][1]
    ui.handle('u', ui.build_screen())
    assert ui.build_screen().panel and ui.route.target == selected
    ui.handle('tab', ui.build_screen())
    ui.handle('down', ui.build_screen())
    updated = ui.build_screen()
    assert updated.panel and ui.route.target == updated.entries[ui.stack[-2].index][1]
    assert ui.route.target != selected
    ui.handle('u', ui.build_screen())
    assert ui.route.kind == 'network'
    assert ui.route.extra['object_type'] == 'person'
    assert ui.route.extra['categories'] == ['Inferred complementarities']
    assert ui.route.extra['zoom'] == 1.2


def test_request_lifecycle_is_available_to_player_and_curator_in_the_same_panel():
    ui, port = app(answers=['Please check the supplied name', 'y'])
    ui.route.column = 1
    ui.handle('enter', ui.build_screen())
    ui.route.index = 1
    ui.handle('enter', ui.build_screen())
    target = ui.route.target
    requester = ui.playing_actor
    ui.handle('u', ui.build_screen())
    choose_panel(ui, ('request', 'correction'))
    request = next(iter(records(ui.world()).values()))
    assert request['target_id'] == target and request['requester_id'] == requester
    assert request['status'] == 'submitted'
    ui.handle('u', ui.build_screen())
    provision_curator(ui.game, 'Alex', enabled=True, reference='Fixture operator')
    ui.refresh()
    ui.handle('u', ui.build_screen())
    choose_panel(ui, ('panel', 'queue'))
    choose_panel(ui, ('review', request['id']))
    port.answers = iter(['Need the source reference', 'y'])
    choose_panel(ui, ('decision', 'request_clarification'))
    assert records(ui.world())[request['id']]['status'] == 'needs_clarification'
    # Requester and curator happen to be the same local actor, but each engine permission is checked.
    port.answers = iter(['Participant statement page 1', 'y'])
    choose_panel(ui, ('clarify', request['id']))
    port.answers = iter(['Reviewed the source', 'y'])
    choose_panel(ui, ('decision', 'approve'))
    assert records(ui.world())[request['id']]['status'] == 'approved'
    assert ui.current().get_world() == ui.current().replay().get_world()


def test_global_history_levels_filters_and_return_to_event_and_list():
    ui, _ = app()
    ui.handle('H', ui.build_screen())
    screen = ui.build_screen()
    assert screen.title == 'HISTORY / COLLECTIVE / Overview' and screen.entries
    ui.route.index = len(screen.entries)-1
    original = ui.route
    ui.handle('+', screen)
    assert any('Detailed' in line for line in ui.build_screen().lines)
    ui.handle('+', ui.build_screen())
    assert any('"mutations"' in line for line in ui.build_screen().lines)
    ui.handle('enter', ui.build_screen())
    assert ui.route.kind == 'history_event'
    event_route = ui.route
    ui.handle('enter', ui.build_screen())
    assert ui.route.kind == 'history_object'
    ui.handle('b', ui.build_screen())
    assert ui.route is event_route
    ui.handle('b', ui.build_screen())
    assert ui.route is original and ui.route.index == len(screen.entries)-1
    ui.route.extra['history_filters'] = HistoryFilters(actor_id='missing')
    assert not ui.build_screen().entries
    ui.route.extra['history_filters'] = HistoryFilters()
    assert ui.build_screen().entries


def test_history_filters_match_actor_object_action_mission_and_time():
    from commons_game.scenario import demo_commands
    game = load_scenario('bilateral-logs')
    for command in demo_commands():
        assert game.submit(command)['ok']
    events = game.project('log')
    accepted = history_rows(events, HistoryFilters(action='accept'))
    assert accepted
    event = accepted[-1]['event']
    command = event['command']
    filters = HistoryFilters(actor_id=event['actor_id'], object_id=command['agreement_id'], action='accept',
                             since=event['occurred_at'], until=event['occurred_at'])
    assert [row['event']['id'] for row in history_rows(events, filters)] == [event['id']]
    objective = game.get_world()['agreements'][command['agreement_id']]['objective_id']
    assert history_rows(events, HistoryFilters(mission_id=objective))
    assert not history_rows(events, replace(filters, actor_id='other'))


def test_type_selection_and_history_filters_preserve_navigation_without_writes():
    ui, port = app(choices=[0])
    before = deepcopy(ui.current().project('log'))
    ui.open_network()
    route = ui.route
    centre = route.target
    route.extra.update(scope='whole', zoom=1.2)
    port.choices = iter([lambda value: value == 'People'])
    ui.handle('T', ui.build_screen())
    assert route.target == centre and route.extra['object_type'] == 'person'
    assert route.extra['zoom'] == 1.2
    assert all(ui.node(ident)['kind'] == 'person' or ident == centre for _, ident in ui.build_screen().entries)
    ui.handle('H', ui.build_screen())
    port.choices = iter([lambda value: value == 'action', lambda value: value == 'ecosystem.imported'])
    ui.handle('f', ui.build_screen())
    assert len(ui.build_screen().entries) == 1
    ui.handle('b', ui.build_screen())
    assert ui.route is route and route.extra['object_type'] == 'person'
    assert ui.current().project('log') == before


def test_context_without_focus_does_not_assume_player_and_main_scroll_is_independent():
    ui, _ = app()
    ui.push('scenarios')  # menu entries are not object identities
    source = ui.route
    ui.handle('u', ui.build_screen())
    screen = ui.build_screen()
    assert ui.route.target is None and 'SELECT OBJECT' in screen.panel.title
    assert ('My curation requests', ('panel', 'queue')) in screen.panel.entries
    ui.panel_drawn(screen, {'main': 12, 'panel': 3})
    assert source.scroll == 12 and ui.route.scroll == 3
    ui.width = 60
    screen = ui.build_screen()
    ui.panel_drawn(screen, {'panel': 5})
    assert source.scroll == 12 and ui.route.scroll == 5


def test_cancelled_curator_edit_keeps_explicit_target_and_changes_nothing():
    ui, port = app()
    provision_curator(ui.game, 'Alex', enabled=True, reference='Fixture operator')
    ui.refresh()
    ui.route.column = 1
    ui.handle('enter', ui.build_screen())
    ui.route.index = 1
    ui.handle('enter', ui.build_screen())
    target = ui.route.target
    assert target != ui.playing_actor
    ui.handle('u', ui.build_screen())
    ui.build_screen()
    before = deepcopy(ui.current().project('log'))
    port.answers = iter(['Changed', 'A source reference', 'n'])
    choose_panel(ui, 'correct')
    assert ui.route.target == target and ui.current().project('log') == before
    assert any(target in '\n'.join(lines) for _, lines, _ in port.drawn if isinstance(lines, list))


def test_historical_object_context_remains_read_only_even_for_curator():
    ui, _ = app()
    provision_curator(ui.game, 'Alex', enabled=True, reference='Fixture operator')
    ui.refresh()
    target = ui.playing_actor
    ui.push('history_object', target, sequence=2, at=2)
    ui.handle('u', ui.build_screen())
    screen = ui.build_screen()
    assert ui.route.target == target
    assert any('read-only' in line for line in screen.panel.lines)
    assert all(value not in {'correct', 'visibility', 'preview', 'reverse'} for _, value in screen.panel.entries
               if isinstance(value, str))
    assert not any(isinstance(value, tuple) and value[0] == 'request' for _, value in screen.panel.entries)


def test_global_history_includes_operator_events_without_a_player_command():
    ui, _ = app()
    provision_curator(ui.game, 'Alex', enabled=True, reference='Fixture operator')
    ui.refresh()
    ui.handle('H', ui.build_screen())
    screen = ui.build_screen()
    assert any('curator access granted' in text for text, _ in screen.entries)
    before = deepcopy(ui.current().project('log'))
    ui.route.index = len(screen.entries)-1
    ui.handle('+', screen)
    assert any('Actor:' in text for text in ui.build_screen().lines)
    assert ui.current().project('log') == before


def test_confirmed_correction_modifies_only_the_explicit_counterparty():
    from game_gamer.runtime.curation import profile
    ui, port = app()
    provision_curator(ui.game, 'Alex', enabled=True, reference='Fixture operator')
    ui.refresh()
    ui.route.column = 1
    ui.handle('enter', ui.build_screen())
    ui.route.index = 1
    ui.handle('enter', ui.build_screen())
    target, player = ui.route.target, ui.playing_actor
    original_player = deepcopy(profile(ui.world(), player))
    ui.handle('u', ui.build_screen())
    port.answers = iter(['Corrected participant', 'Participant supplied correction', 'y'])
    choose_panel(ui, 'correct')
    assert ui.current().project('log')[-1]['command']['target_id'] == target != player
    assert profile(ui.world(), player) == original_player
    assert profile(ui.world(), target)['label'] == 'Corrected participant'
    assert ui.route.extra['pinned_target'] == target
    ui.handle('tab', ui.build_screen())
    ui.handle('b', ui.build_screen())
    ui.build_screen()
    assert not ui.route.extra.get('pinned_target')
