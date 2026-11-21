"""Installed-package API and extension/replay probes, using synthetic worlds only."""
from dataclasses import replace
import inspect
import json
from pathlib import Path
import sys


def api():
    import game_gamer
    result = {}
    for name in game_gamer.__all__:
        value = getattr(game_gamer, name)
        if inspect.isclass(value) or inspect.isfunction(value):
            try:
                signature = inspect.signature(value)
            except ValueError:
                continue
            result[name] = {key: {'kind': param.kind.name, 'required': param.default is inspect.Parameter.empty}
                            for key, param in signature.parameters.items()}
    for name in ('start', 'open', 'evaluate', 'submit', 'from_history', 'fork'):
        result['Collective.'+name] = {key: {'kind': param.kind.name, 'required': param.default is inspect.Parameter.empty}
            for key, param in inspect.signature(getattr(game_gamer.Collective, name)).parameters.items()}
    return result


def extension():
    from game_gamer import CommandDefinition, DomainError, Extension, PolicyHook
    def command(world, payload, **context):
        world['configuration']['probe'] = {'id': 'probe', 'status': 'active', 'value': payload['value']}
    def policy(world, payload, **context):
        if payload['value'] == 'deny':
            raise DomainError('probe_denied')
    return Extension(id='fictional.release-probe', version='1.0.0',
        commands={'set_probe': CommandDefinition(required={'value'}, handler=command)},
        policies=(PolicyHook(before=policy),), projections={'probe': lambda world: world['configuration'].get('probe')})


def runtime(path):
    from game_gamer import ActionSubmission, Collective, DomainError, SimulationBinding
    app = extension()
    definition = {'schema': 'game-gamer/world/v1', 'scope_id': 'release-probe', 'revision': 1,
                  'execution_mode': 'simulation', 'world_time': '2030-01-01T00:00:00+00:00',
                  'title': 'Synthetic release probe', 'actors': [{'id': 'a', 'label': 'A'}]}
    game = Collective.start(definition, path=path, extension=app)
    binding = SimulationBinding(scope_id=game.scope_id, actor_id='a')
    submission = ActionSubmission(action_id='probe', actor_id='a', scope_id=game.scope_id, target_id=None,
                                 expected_revision=game.revision, action_type='set_probe', payload={'value': 'ok'})
    before = game.history()
    assert game.submit(replace(submission, payload={'value': 'deny'}), binding=binding)['errors'] == ['probe_denied']
    assert game.history() == before
    assert game.evaluate(submission, binding=binding).status == 'allowed'
    assert game.submit(submission, binding=binding)['ok']
    saved = game.history()
    assert game.submit(submission, binding=binding)['ok'] and game.history() == saved
    assert Collective.from_history(saved, extension=app).project() == game.project()
    assert Collective.open(path, scope_id=game.scope_id, extension=app).project() == game.project()
    for supplied, error in ((None, 'extension_unavailable'), (replace(app, version='2.0.0'), 'extension_version_mismatch')):
        try:
            Collective.open(path, scope_id=game.scope_id, extension=supplied)
        except DomainError as rejected:
            assert str(rejected) == error
        else:
            raise AssertionError('Missing extension binding rejection')
    branch = game.fork(at=1, branch_id='possible')
    assert branch.submit(replace(submission, action_id='branch', scope_id=branch.scope_id),
                         binding=SimulationBinding(scope_id=branch.scope_id, actor_id='a'))['ok']
    assert game.history() == saved and Collective.from_history(branch.history(), extension=app).project() == branch.project()
    return {'extension_version_binding': 'PASS', 'event_replay': 'PASS', 'branch_isolation': 'PASS'}


if __name__ == '__main__':
    if sys.argv[1] == 'api':
        print(json.dumps(api(), sort_keys=True))
    elif sys.argv[1] == 'restart':
        from game_gamer import Collective
        assert Collective.open(Path(sys.argv[2]), scope_id='release-probe', extension=extension()).project('probe')['value'] == 'ok'
    else:
        print(json.dumps(runtime(Path(sys.argv[2]))))
