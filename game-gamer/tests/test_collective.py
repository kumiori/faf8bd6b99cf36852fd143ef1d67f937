from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from game_gamer import (ActionSubmission, Collective, DomainError, EpistemicStatus, SimulationBinding,
                        epistemic_status, evaluate_authorisation)

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'minimal_collective' / 'world.json'


@pytest.fixture
def definition():
    return json.loads(EXAMPLE.read_text())


def action(game, actor, kind, key, *, target=None, **payload):
    binding = SimulationBinding(actor_id=actor, scope_id=game.scope_id)
    return ActionSubmission(actor_id=actor, scope_id=game.scope_id, action_id=key,
                            expected_revision=game.project()['version'], action_type=kind,
                            target_id=target, payload=payload), binding


def send(game, actor, kind, key, *, target=None, **payload):
    submission, binding = action(game, actor, kind, key, target=target, **payload)
    return game.submit(submission, binding=binding)


def contact(game, key='contact'):
    return action(game, 'sam', 'send_contact', key, target=key, id=key, recipient_id='jo', message='Rehearse?')


def test_authority_and_epistemic_status(definition):
    game = Collective.start(definition)
    submission, sender = contact(game)
    recipient = replace(sender, actor_id='jo')
    assert game.submit(submission, binding=recipient)['errors'] == ['actor_mismatch']
    assert game.submit(replace(submission, scope_id='other'), binding=sender)['errors'] == ['scope_mismatch']
    assert game.submit(replace(submission, target_id='room'), binding=sender)['errors'] == ['target_mismatch']
    assert game.evaluate(submission, binding=sender).status == 'allowed'
    assert game.project()['version'] == 1
    assert epistemic_status(game.project()['possibilities'][0]) == EpistemicStatus.INFERENCE
    assert game.project('relationships') == []
    assert game.submit(submission, binding=sender)['ok']
    assert epistemic_status(game.project('relationships')[0]) == EpistemicStatus.PROPOSAL
    assert game.inbox(binding=recipient)[0]['id'] == 'contact'
    assert game.inbox(binding=recipient, at=1) == []
    assert send(game, 'sam', 'respond_contact', 'denied', target='contact', invitation_id='contact',
                response='accept')['errors'] == ['recipient_required']
    assert send(game, 'jo', 'respond_contact', 'accept', target='contact', invitation_id='contact',
                response='accept')['ok']
    invitation, connection = game.project('relationships')
    assert epistemic_status(invitation) == EpistemicStatus.PROPOSAL
    assert epistemic_status(connection) == EpistemicStatus.ACKNOWLEDGED
    assert game.project('agreements') == []


@pytest.mark.parametrize('persistent', [False, True])
def test_competing_actions_and_exact_retries(definition, tmp_path, persistent):
    path = tmp_path / 'world.sqlite'
    game = Collective.start(definition, path=path if persistent else None)
    other = Collective.open(path, scope_id=game.scope_id) if persistent else game
    barrier = Barrier(2)

    def competing(store, submission, binding):
        barrier.wait(timeout=5)
        return store.submit(submission, binding=binding)

    first, second = contact(game, 'first'), contact(game, 'second')
    with ThreadPoolExecutor(max_workers=2) as workers:
        left = workers.submit(competing, game, *first)
        right = workers.submit(competing, other, *second)
        outcomes = [left.result(timeout=10), right.result(timeout=10)]
    assert sorted(result['ok'] for result in outcomes) == [False, True]
    winner = outcomes.index(next(result for result in outcomes if result['ok']))
    assert outcomes[1 - winner]['errors'] == ['stale_version']
    submission, binding = [first, second][winner]
    assert other.submit(submission, binding=binding) == outcomes[winner]
    changed = replace(submission, payload={**submission.payload, 'message': 'Changed'})
    assert other.submit(changed, binding=binding)['errors'] == ['key_conflict']
    assert other.project()['version'] == 2


def test_interrupted_append_recovers_and_retries(definition, tmp_path):
    path = tmp_path / 'world.sqlite'
    game = Collective.start(definition, path=path)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_append AFTER INSERT ON events BEGIN SELECT RAISE(ABORT, 'interrupted'); END;")
    submission, binding = contact(game)
    with pytest.raises(sqlite3.IntegrityError, match='interrupted'):
        game.submit(submission, binding=binding)
    restored = Collective.open(path, scope_id=game.scope_id)
    assert restored.project()['version'] == 1
    assert restored.project('relationships') == []
    with sqlite3.connect(path) as db:
        db.execute('DROP TRIGGER fail_append')
    assert restored.submit(submission, binding=binding)['ok']
    assert len(restored.project('relationships')) == 1
    with pytest.raises(DomainError, match='scope_mismatch'):
        Collective.open(path, scope_id='another-world')


def test_replay_and_fork_authority_are_distinct(definition):
    game = Collective.start(definition)
    first, sender = contact(game)
    assert game.submit(first, binding=sender)['ok']
    assert Collective.from_history(json.loads(json.dumps(game.history()))).project() == game.project()
    fork = game.fork(at=1, branch_id='try-gathering-first')
    alternative, author = action(fork, 'sam', 'invite', 'gathering', target='run-rehearsal',
                                 recipient_id='jo', objective_id='run-rehearsal')
    assert fork.submit(alternative, binding=author)['ok']
    assert game.submit(alternative, binding=author)['errors'] == ['scope_mismatch']
    assert fork.project('relationships')[0]['kind'] == 'invited'
    assert game.project('relationships')[0]['kind'] == 'contact_invitation'
    assert fork.inbox(binding=replace(author, actor_id='jo'))[0]['actions'][0]['kind'] == 'respond_invitation'
    history = fork.history()
    assert Collective.from_history(history).scope_id == fork.scope_id
    with pytest.raises(DomainError, match='invalid_history_authority'):
        Collective.from_history({**history, 'fork': None})
    with pytest.raises(DomainError, match='invalid_history_digest'):
        Collective.from_history({**history, 'events': history['events'][:-1]})


def test_schema_and_governance_fail_explicitly(definition):
    with pytest.raises(DomainError, match='unsupported_world_schema'):
        Collective.start({**definition, 'schema': 'future'})
    with pytest.raises(DomainError, match='unsupported_execution_mode'):
        Collective.start({**definition, 'execution_mode': 'live'})
    with pytest.raises(DomainError, match='invalid_seed_id'):
        Collective.start({**definition, 'actors': definition['actors'] * 2})
    game = Collective.start(definition)
    world = game.project('world')
    terms = {'policy_id': 'steward-approval', 'authorizations': {}}
    assert evaluate_authorisation(world, terms).status == 'requires_authorisation'
    assert evaluate_authorisation(world, terms).reasons == ('approval_threshold',)
    assert evaluate_authorisation(world, {**terms, 'authorizations': {'pat': {}}}).status == 'allowed'


def test_retry_compares_json_types(definition):
    game = Collective.start(definition)
    original, binding = action(game, 'sam', 'declare', 'capacity', table='capacities',
                               record={'domain': 'rehearsal', 'quantity': 1, 'unit': 'slot'})
    assert game.submit(original, binding=binding)['ok']
    changed = replace(original, payload={**original.payload, 'record': {**original.payload['record'], 'quantity': True}})
    assert game.submit(changed, binding=binding)['errors'] == ['key_conflict']
    assert game.project()['version'] == 2
