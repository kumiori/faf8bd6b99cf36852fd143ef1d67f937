from collections import deque
import curses

from game_gamer.exercises.tutorials import catalogue, TutorialSession
from game_gamer.runtime.runner import Collective
from game_gamer.tui.viewport import CursesViewport
from game_gamer.projections.participants import ParticipantDirectory, ParticipantFilters
from test_reconstruction import start


class Window:
    def __init__(self, keys):
        self.keys = deque(keys)

    def timeout(self, milliseconds):
        pass

    def get_wch(self):
        if not self.keys:
            raise curses.error('No queued input')
        return self.keys.popleft()


def viewport(keys):
    port = object.__new__(CursesViewport)
    port.window = Window(keys)
    port.curses = curses
    port.screens = []
    port.draw = lambda screen, context: port.screens.append(screen)
    return port


def test_confirmation_invalid_input_cancel_and_double_enter_are_unambiguous():
    port = viewport(['a', 'd', 's', 'down', 'enter', 'enter', 'c'])
    assert port.confirm('RECORD?', ['This records a claim'], 'Practice') is False
    assert all(screen.entries[0][0] == 'CONFIRM' for screen in port.screens)
    assert port.key() == 'c'
    for keys, expected in [(['esc'], False), (['n'], False), (['y', 'enter'], True),
                           (['enter', 'enter'], True)]:
        assert viewport(keys).confirm('RECORD?', [], 'Practice') is expected


def test_navigation_coalesces_repeats_and_preserves_the_following_command():
    port = viewport(['down']*100 + ['c'])
    # Curses maps native codes into the public key names.
    port.window.keys = deque([curses.KEY_DOWN]*100 + ['c'])
    assert port.navigation_key() == 'down'
    assert port.navigation_key() == 'down'
    assert port.key() == 'c'
    assert not port.window.keys


def test_each_configured_tutorial_completes_through_the_engine_with_exact_retries():
    main = start()
    before = main.history()
    for definition in catalogue():
        tutorial = TutorialSession(definition)
        while not tutorial.complete:
            index = tutorial.index
            result = tutorial.perform(index)
            assert tutorial.index == index+1, (definition['id'], index, result)
            version = tutorial.collective.project()['version']
            assert tutorial.perform(index) == result
            assert tutorial.collective.project()['version'] == version
        restored = Collective.from_history(tutorial.collective.history())
        assert restored.project() == tutorial.collective.project()
        if definition['id'] == 'connect':
            assert tutorial.collective.project('relationships')[-1]['kind'] == 'acknowledged_connection'
        elif definition['id'] == 'agreement':
            assert tutorial.collective.project('agreements')[0]['outcome_status'] == 'verified'
        else:
            assert tutorial.collective.project('agreements')[0]['status'] == 'active'
            assert tutorial.collective.project('commitments')
    assert main.history() == before


def test_facets_use_or_within_a_field_and_and_across_fields_with_counts():
    world = start().project('world')
    directory = ParticipantDirectory(world, questionnaire={
        'capacities': {'a': {'domains': ['Maps'], 'state': 'answered'},
                       'b': {'domains': ['Maps', 'Data'], 'state': 'answered'},
                       'c': {'domains': ['Data'], 'state': 'answered'}},
        'needs': {'a': {'domains': ['Data'], 'state': 'answered'},
                  'b': {'domains': ['Maps'], 'state': 'answered'}}})
    filters = ParticipantFilters(facets=(('offers', ('Maps', 'Data')), ('needs', ('Maps',))))
    assert [p.id for p in directory.browse(filters)] == ['b']
    assert directory.facet_values('offers', filters) == [('Data', 1), ('Maps', 1)]
    match = ParticipantFilters(facets=(('connections', ('complementarity',)),))
    assert [p.id for p in directory.browse(match, reference='a')] == ['b', 'c']


def test_cached_store_reads_are_detached_and_validate_changed_history(tmp_path):
    import json
    import sqlite3
    import pytest
    from game_gamer.runtime.engine import CollectiveEngine
    from game_gamer.persistence.sqlite import SQLiteStore
    game = start(tmp_path/'world.sqlite')
    store = SQLiteStore(tmp_path/'world.sqlite', CollectiveEngine)
    first = store.load()
    command = {'key': 'local-only', 'kind': 'recall_connection', 'actor': 'a', 'target_id': 'b', 'context_id': 'practice'}
    assert first.submit(command)['ok']
    assert store.load().revision == 1
    other = SQLiteStore(tmp_path/'world.sqlite', CollectiveEngine)
    assert other.submit(command)['ok']
    assert store.load().get_world() == other.load().get_world()
    assert store.load().revision == 2
    # An externally changed prefix must be validated again rather than accepted from cache.
    with sqlite3.connect(store.path) as connection:
        entry = json.loads(connection.execute('SELECT payload FROM events WHERE sequence=1').fetchone()[0])
        entry['mutations'][0]['after']['label'] = 'Corrupted'
        connection.execute('UPDATE events SET payload=? WHERE sequence=1', (json.dumps(entry),))
    with pytest.raises(ValueError):
        store.load()


def test_opening_is_nonblocking_timed_and_respects_reduced_motion(monkeypatch):
    from types import SimpleNamespace
    from game_gamer.tui import opening
    from game_gamer.tui.navigation import Route
    from game_gamer.tui.reconstruction import NetworkReconstructionExercise

    exercise = NetworkReconstructionExercise('demo', 'forum', 'Reconstruct', 'A fictional forum', ('Remember together',))
    port = SimpleNamespace(poll_key=lambda milliseconds: None)
    clock = [0.0]
    monkeypatch.delenv('COMMONS_REDUCED_MOTION', raising=False)
    monkeypatch.setattr(opening, 'monotonic', lambda: clock[0])
    route = Route('reconstruction_intro')
    first = opening.opening_screen(exercise, route, port)
    assert first.refresh_interval_ms == 80
    clock[0] = 2.6
    final = opening.opening_screen(exercise, route, port)
    assert final.entries == [('BEGIN RECONSTRUCTION', 'begin')]
    assert route.extra['opening_finished']
    monkeypatch.setenv('COMMONS_REDUCED_MOTION', '1')
    reduced = opening.opening_screen(exercise, Route('reconstruction_intro'), port)
    assert reduced.entries == [('BEGIN RECONSTRUCTION', 'begin')]


def test_store_cache_keeps_exact_retries_idempotent_after_a_new_commit(tmp_path):
    from game_gamer.persistence.sqlite import SQLiteStore
    from game_gamer.runtime.engine import CollectiveEngine
    game = start(tmp_path/'retry.sqlite')
    store = SQLiteStore(tmp_path/'retry.sqlite', CollectiveEngine)
    store.load()
    command = {'key': 'record-once', 'kind': 'recall_connection', 'actor': 'a',
               'target_id': 'b', 'context_id': 'forum'}
    first = store.submit(command, expected_version=1)
    assert first['ok']
    store.load()
    assert store.submit(command, expected_version=1)['action_id'] == first['action_id']
    assert store.revision() == 2
