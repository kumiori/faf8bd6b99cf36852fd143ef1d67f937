"""Operator provisioning and the role indicator at the player-picker boundary."""
import json
import subprocess
import sys

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.curator_access import provision_curator
from commons_game.ecosystem_import import import_snapshot
from commons_game.fullscreen import FullScreenTerminal
from game_gamer.tui.viewport import CursesViewport
from test_matrix_navigation import FakeViewport, synthetic_snapshot, world


def cli(path, decision):
    result = subprocess.run([sys.executable, '-B', '-m', 'commons_game', '--db', str(path),
                             'curator-access', decision, 'Alex', '--reference', 'Fictional operator role setup'],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_operator_grant_revoke_and_exact_repeated_setup_are_recorded(tmp_path):
    store = SQLiteStore(tmp_path/'world.sqlite', CommonsGame)
    store.initialise(world())
    initial = store.revision()
    result = cli(store.path, 'grant')
    actor = result['actor_id']
    game = store.load()
    assert 'curator' in game.get_world()['actors'][actor]['roles']
    assert game.project('log')[-1]['kind'] == 'curator.access_granted'
    assert game.project('log')[-1]['commit']['authorization']['rule'] == 'trusted_local_curator_provisioning'
    assert not cli(store.path, 'grant')['changed']
    assert store.revision() == initial+1
    assert game.replay().get_world() == game.get_world()
    assert not game.submit({'key': 'player-grant', 'kind': 'curator_access', 'actor': actor})['ok']
    assert cli(store.path, 'revoke')['changed']
    restored = store.load()
    assert 'curator' not in restored.get_world()['actors'][actor]['roles']
    assert restored.project('log')[-1]['kind'] == 'curator.access_revoked'
    assert restored.get_world() == restored.replay().get_world()


def test_source_metadata_refresh_preserves_operator_roles():
    game = world()
    result = provision_curator(game, 'Alex', enabled=True, reference='Fictional local operator')
    snapshot = synthetic_snapshot()
    actor = next(record for record in snapshot['records'] if record['kind'] == 'person'
                 and record['fields']['label'].startswith('Alex'))
    actor['fields']['label'] = 'Alex Corrected'
    report = import_snapshot(game, snapshot)
    assert not report['rejected']
    assert 'curator' in game.get_world()['actors'][result['actor_id']]['roles']


def test_authorised_picker_carries_badge_with_a_names_only_directory():
    game = world()
    result = provision_curator(game, 'Alex', enabled=True, reference='Fictional local operator')

    class Port(FakeViewport):
        def choose(self, title, items, label, context, **options):
            self.options = options
            return super().choose(title, items, label, context, **options)

    port = Port()
    ui = FullScreenTerminal(game, viewport=port)
    ui.assume_actor(game.get_world()['actors'][result['actor_id']])
    ui.select_actor()
    assert port.options['header_indicator'] == '◆ CURATOR'
    assert port.options['directory'] is True
    assert port.drawn[-1][1][:3] == ['Alex Example', 'Casey Example', 'Morgan Example']
    native = object.__new__(CursesViewport)
    shown = []
    native.draw = lambda screen, context: shown.append(screen)
    native.key = lambda: 'enter'
    assert native.choose('WHO WILL YOU PLAY?', ['Alex'], str, 'Playing Alex',
                         header_indicator='◆ CURATOR') == 'Alex'
    assert shown[0].header_indicator == '◆ CURATOR'
