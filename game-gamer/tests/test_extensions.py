from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game_gamer import Collective, DomainError, Extension, SimulationBinding, register_extension

APP = Path(__file__).parents[1] / 'examples/lantern-club/lantern_club/__init__.py'
spec = importlib.util.spec_from_file_location('lantern_fixture', APP)
lantern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lantern)


def binding(game, actor='lee'):
    return SimulationBinding(scope_id=game.scope_id, actor_id=actor)


def test_registered_extension_propagates_across_every_public_boundary(tmp_path):
    path = tmp_path/'club.sqlite'
    game = Collective.start(lantern.definition(), path=path, extension=lantern.EXTENSION)
    initial = game.history()
    action = lantern.visit(game)
    assert game.evaluate(action, binding=binding(game)).status == 'allowed'
    denied = lantern.visit(game, actor='kim', key='guest')
    assert game.evaluate(denied, binding=binding(game, 'kim')).reasons == ('club_member_required',)
    assert game.submit(denied, binding=binding(game, 'kim'))['errors'] == ['club_member_required']
    assert game.history() == initial
    assert game.submit(action, binding=binding(game, 'kim'))['errors'] == ['actor_mismatch']
    for payload, reason in [({}, 'missing_field'), ({'shelf_id': 'reading-room', 'extra': 1}, 'unsupported_field')]:
        assert game.submit(replace(action, payload=payload), binding=binding(game))['errors'] == [reason]
    result = game.submit(action, binding=binding(game))
    assert result['ok']
    saved = game.history()
    assert game.submit(action, binding=binding(game))['ok']
    assert game.history() == saved
    assert game.project('visit_count') == 1 and game.project('visit_count', at=1) == 0
    with pytest.raises(DomainError, match='extension_unavailable'):
        Collective.open(path, scope_id='lantern-club')
    with pytest.raises(DomainError, match='extension_version_mismatch'):
        Collective.open(path, scope_id='lantern-club', extension=replace(lantern.EXTENSION, version='2.0.0'))
    reopened = Collective.open(path, scope_id='lantern-club', extension=lantern.EXTENSION)
    assert reopened.submit(action, binding=binding(reopened))['ok']
    assert reopened.history() == saved
    restored = Collective.from_history(json.loads(json.dumps(saved)), extension=lantern.EXTENSION)
    assert restored.project() == game.project()
    fork = reopened.fork(at=1, branch_id='alternative')
    assert fork.submit(lantern.visit(fork, key='forked'), binding=binding(fork))['ok']
    assert fork.project('visit_count') == 1
    assert game.history() == saved
    assert Collective.from_history(fork.history(), extension=lantern.EXTENSION).project() == fork.project()
    program = '''
import importlib.util,sys
from game_gamer import Collective,SimulationBinding
spec=importlib.util.spec_from_file_location('fixture',sys.argv[1]); app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
game=Collective.open(sys.argv[2],scope_id='lantern-club',extension=app.EXTENSION)
assert game.project('visit_count')==1
assert game.submit(app.visit(game,key='second'),binding=SimulationBinding(scope_id=game.scope_id,actor_id='lee'))['ok']
assert game.project('visit_count')==2
'''
    check = subprocess.run([sys.executable, '-B', '-c', program, str(APP), str(path)], cwd=tmp_path,
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stderr


def test_policy_failure_is_atomic_even_after_candidate_mutation():
    from game_gamer import PolicyHook
    def reject_after(world, command, **context):
        raise DomainError('postcondition_rejected')
    extension = replace(lantern.EXTENSION, policies=(*lantern.EXTENSION.policies, PolicyHook(after=reject_after)))
    game = Collective.start(lantern.definition(), extension=extension)
    before = game.history()
    assert game.submit(lantern.visit(game), binding=binding(game))['errors'] == ['postcondition_rejected']
    assert game.project('visit_count') == 0 and game.history() == before


def test_extension_state_must_round_trip_through_the_existing_event_schema():
    from game_gamer import PolicyHook
    def invalid_table(world, command, **context):
        world['parallel_state'] = {'counter': 1}
    extension = replace(lantern.EXTENSION, policies=(PolicyHook(after=invalid_table),))
    game = Collective.start(lantern.definition(), extension=extension)
    before = game.history()
    assert game.submit(lantern.visit(game), binding=binding(game))['errors'] == ['invalid_world_tables']
    assert game.history() == before

    def invalid_deletion(world, command, **context):
        del world['actors']['kim']
    extension = replace(lantern.EXTENSION, policies=(PolicyHook(after=invalid_deletion),))
    game = Collective.start(lantern.definition(), extension=extension)
    before = game.history()
    assert game.submit(lantern.visit(game), binding=binding(game))['errors'] == ['state_deletion_unsupported']
    assert game.history() == before


def test_extension_unknown_version_and_competing_submissions(tmp_path):
    game = Collective.start(lantern.definition(), path=tmp_path/'concurrent.sqlite', extension=lantern.EXTENSION)
    initial = game.history()
    with pytest.raises(DomainError, match='extension_unavailable'):
        Collective.from_history(initial)
    first, second = lantern.visit(game, key='one'), lantern.visit(game, key='two')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda action: game.submit(action, binding=binding(game)), (first, second)))
    assert sum(result['ok'] for result in results) == 1
    assert game.project('visit_count') == 1
    assert any(result.get('errors') == ['stale_version'] for result in results)


def test_explicit_registration_resolves_descriptors_and_active_schemas(tmp_path):
    extension = replace(lantern.EXTENSION, id='fictional.registered-club')
    assert register_extension(extension) is extension
    game = Collective.start(lantern.definition(), extension=extension.descriptor(), path=tmp_path/'registered.sqlite')
    assert 'record_visit' in game.command_registry
    with pytest.raises(TypeError):
        game.command_registry['unexpected'] = None
    action = lantern.visit(game)
    assert action.command(registry=game.command_registry)['kind'] == 'record_visit'
    assert game.submit(action, binding=binding(game))['ok']
    reopened = Collective.open(tmp_path/'registered.sqlite', scope_id=game.scope_id)
    assert reopened.extension is extension and reopened.project('visit_count') == 1
    with pytest.raises(DomainError, match='extension_registration_conflict'):
        register_extension(replace(extension, projections={'something_else': lambda world: 1}))
    assert Collective.from_history(game.history()).project() == game.project()
