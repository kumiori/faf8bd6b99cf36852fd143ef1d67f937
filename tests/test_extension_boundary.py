"""Commons uses registered policy/projection hooks and the shared commit path."""
import ast
from copy import deepcopy
from pathlib import Path

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.extensions import COMMONS_EXTENSION
from commons_game.ecosystem_import import import_snapshot
from commons_game.scenario import demo_commands
from game_gamer import ActionSubmission, Collective, SimulationBinding
from game_gamer.runtime.engine import CollectiveEngine
from test_matrix_navigation import synthetic_snapshot


def test_commons_adapter_replays_legacy_logs_without_rewriting_prefixes(tmp_path):
    game = load_scenario('bilateral-logs')
    for command in demo_commands():
        assert game.submit(command)['ok']
    history, world = game.project('log'), game.get_world()
    restored = CommonsGame.from_log(deepcopy(history))
    assert restored.get_world() == world and restored.project('log') == history
    assert restored.extension is COMMONS_EXTENSION
    assert CommonsGame.submit is CollectiveEngine.submit
    assert CommonsGame.validate is CollectiveEngine.validate
    assert CommonsGame.project is CollectiveEngine.project
    tree = ast.parse((Path(__file__).parents[1]/'commons_game/engine.py').read_text())
    methods = [node.name for cls in tree.body if isinstance(cls, ast.ClassDef)
               for node in cls.body if isinstance(node, ast.FunctionDef)]
    assert methods == ['__init__']
    store = SQLiteStore(tmp_path/'legacy.sqlite', CommonsGame)
    store.initialise(restored)
    assert store.load().get_world() == world
    assert store.load().project('log') == history


def test_commons_extension_also_works_through_the_public_facade(tmp_path):
    definition = {'schema': 'game-gamer/world/v1', 'scope_id': 'commons-fiction', 'revision': 1,
                  'execution_mode': 'simulation', 'title': 'Fictional Commons application',
                  'world_time': '2030-01-01T00:00:00+00:00',
                  'actors': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}]}
    game = Collective.start(definition, path=tmp_path/'commons.sqlite', extension=COMMONS_EXTENSION)
    action = ActionSubmission(action_id='request', actor_id='a', scope_id=game.scope_id,
                               target_id='b', expected_revision=game.revision, action_type='request_curation',
                               payload={'target_id': 'b', 'request_type': 'profile_review', 'reason': 'Check source'})
    binding = SimulationBinding(actor_id='a', scope_id=game.scope_id)
    assert game.evaluate(action, binding=binding).status == 'allowed'
    assert game.submit(action, binding=binding)['ok']
    assert Collective.open(tmp_path/'commons.sqlite', scope_id=game.scope_id, extension=COMMONS_EXTENSION).project() == game.project()
    assert Collective.from_history(game.history(), extension=COMMONS_EXTENSION).project() == game.project()
    assert game.fork(at=game.revision, branch_id='alternative').project() == game.project()
