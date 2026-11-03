from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from commons_engine import WorldEngine
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.model import DomainError
from commons_game.projections import complementarity
from commons_game.scenario import SCENARIOS, definition, run_demo


def send(game, kind, actor='researcher', **payload):
    command = {'key': f'test-{len(game.project("log")) + 1}', 'kind': kind, 'actor': actor, **payload}
    return game.submit(command)


def propose(game, gid='agreement-main', **changes):
    proposal = deepcopy(definition('bilateral-logs')['proposal'])
    return send(game, 'propose', **{**proposal, 'id': gid, **changes})


def move(game, kind, actor='researcher', gid='agreement-main', version=1, **payload):
    return send(game, kind, actor, agreement_id=gid, version=version, **payload)


def ready(game, gid='agreement-main'):
    assert propose(game, gid)['ok']
    assert move(game, 'accept', gid=gid)['ok']
    assert move(game, 'accept', 'custodian', gid=gid)['ok']
    assert move(game, 'authorize', 'officer', gid=gid)['ok']


def delivered(game):
    ready(game)
    assert move(game, 'activate')['ok']
    for actor in ('researcher', 'custodian'):
        assert move(game, 'initiate', actor, reference='Synthetic execution note')['ok']
        assert move(game, 'fulfill', actor, reference='Synthetic delivery artefact',
                    criteria=definition('bilateral-logs')['proposal']['verification']['criteria'])['ok']


def assert_rejected_unchanged(game, command, error):
    before = game.get_world(), game.project('log')
    result = game.submit(command)
    assert not result['ok'] and error in result['errors'], result
    assert before == (game.get_world(), game.project('log'))


def test_bilateral_agreement_has_distinct_commitment_commit_and_verified_outcome():
    game = run_demo()
    assert isinstance(game, WorldEngine)
    agreement = game.project('agreements')[0]
    assert agreement['status'] == 'fulfilled' and agreement['outcome_status'] == 'verified'
    assert len(game.project('commitments')) == 2
    commit = game.project('log')[-1]['commit']
    assert commit['id'] != game.project('commitments')[0]['id']
    assert commit['author_id'] == 'verifier' and commit['action_id']
    assert commit['previous_state'] != commit['resulting_state']
    assert commit['previous_version'] + 1 == commit['resulting_version']
    assert commit['authorization']['decision'] == 'allowed'
    assert game.project('objectives')[0]['status'] == 'verified'


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_all_scenarios_replay_and_independent_mode_objectives(scenario):
    game = run_demo(scenario)
    assert game.get_world() == game.replay().get_world()
    assert game.project('objectives')[0]['status'] == 'verified'
    assert game.project('now', at=1)['world']['objectives']['objective-main']['status'] == 'open'


def test_rejected_agreement_cannot_be_accepted():
    game = load_scenario()
    assert propose(game)['ok']
    assert move(game, 'reject', 'custodian', reason='Conditions not acceptable')['ok']
    assert not move(game, 'accept')['ok']
    assert game.project('agreements')[0]['status'] == 'rejected'


def test_unauthorized_approval_and_missing_institutional_authorization():
    game = load_scenario()
    assert propose(game)['ok']
    assert move(game, 'accept')['ok']
    assert move(game, 'accept', 'custodian')['ok']
    before = game.get_world(), game.project('log')
    assert move(game, 'authorize')['errors'] == ['unauthorized_approval']
    assert move(game, 'activate')['errors'] == ['missing_authorization']
    assert before == (game.get_world(), game.project('log'))
    assert game.project('commitments') == []


def test_acceptance_is_version_bound_and_amendment_revokes_authorization():
    game = load_scenario()
    ready(game)
    terms = deepcopy(game.project('agreements')[0]['versions'][0]['terms'])
    terms['conditions'].append('A revised privacy condition')
    assert move(game, 'amend', 'custodian', terms=terms)['ok']
    agreement = game.project('agreements')[0]
    assert agreement['status'] == 'negotiating' and agreement['current_version'] == 2
    old, new = agreement['versions']
    assert old['status'] == 'superseded' and len(old['acceptances']) == 2
    assert old['authorizations'] and not new['authorizations'] and not new['acceptances']
    assert old['content_digest'] != new['content_digest']
    assert move(game, 'accept', version=1)['errors'] == ['agreement_version_conflict']
    assert move(game, 'activate', version=2)['errors'] == ['invalid_transition']
    for actor in ('researcher', 'custodian'):
        assert move(game, 'accept', actor, version=2)['ok']
    assert move(game, 'activate', version=2)['errors'] == ['missing_authorization']


def test_approvals_include_content_digest_and_are_not_cryptographic_signatures():
    game = load_scenario()
    ready(game)
    version = game.project('agreements')[0]['versions'][0]
    for receipt in list(version['acceptances'].values()) + list(version['authorizations'].values()):
        assert receipt['version'] == 1
        assert receipt['content_digest'] == version['content_digest']
        assert receipt['method'] == 'local_simulated_identity'


def test_threshold_named_and_stakeholder_category_rules_are_inspectable():
    game = load_scenario('montreal-geneva')
    proposal = definition('montreal-geneva')['proposal']
    assert send(game, 'propose', **proposal)['ok']
    for actor in proposal['parties']:
        assert move(game, 'accept', actor)['ok']
    assert move(game, 'authorize', 'researcher')['ok']
    assert game.project('agreements')[0]['status'] == 'accepted'
    assert move(game, 'activate')['errors'] == ['missing_authorization']
    assert move(game, 'authorize', 'officer')['ok']
    assert move(game, 'activate')['ok']
    auth = game.project('log')[-1]['commit']['authorization']
    assert auth['policy_snapshot']['threshold'] == 2
    assert auth['policy_snapshot']['required_categories'] == ['community', 'institutional']


def test_overcommitment_is_atomic_and_termination_releases_reservations():
    game = load_scenario()
    ready(game, 'a'); ready(game, 'b')
    assert move(game, 'activate', gid='a')['ok']
    before = game.get_world(), game.project('log')
    assert move(game, 'activate', gid='b')['errors'] == ['resource_overcommitment']
    assert before == (game.get_world(), game.project('log'))
    assert move(game, 'terminate', gid='a', reason='Cancel synthetic research')['ok']
    assert move(game, 'activate', gid='b')['ok']
    assert sum(r['quantity'] for r in game.project('reservations') if r['status'] == 'held') == 1


def reserve_in_process(path, gid):
    return SQLiteStore(path, CommonsGame).submit({'key': 'activate-' + gid, 'kind': 'activate',
        'actor': 'researcher', 'agreement_id': gid, 'version': 1})


def test_concurrent_processes_cannot_double_reserve_sqlite_capacity(tmp_path):
    game = load_scenario()
    ready(game, 'a'); ready(game, 'b')
    store = SQLiteStore(tmp_path / 'race.sqlite', CommonsGame)
    store.initialise(game)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve_in_process, str(store.path), gid) for gid in ('a', 'b')]
        results = [future.result(timeout=20) for future in futures]
    assert sum(result['ok'] for result in results) == 1
    assert next(result for result in results if not result['ok'])['errors'] == ['resource_overcommitment']
    restored = store.load()
    assert len([r for r in restored.project('reservations') if r['status'] == 'held']) == 1
    assert restored.replay().get_world() == restored.get_world()


def test_duplicate_submission_and_payload_conflict_survive_restart(tmp_path):
    game = load_scenario()
    command = {'key': 'unique', 'kind': 'propose', 'actor': 'researcher', **definition('bilateral-logs')['proposal']}
    result = game.submit(command)
    assert result['ok']
    assert game.submit(command) == result
    assert game.submit({**command, 'label': 'Different'})['errors'] == ['key_conflict']
    store = SQLiteStore(tmp_path / 'retry.sqlite', CommonsGame)
    store.initialise(game)
    retry = store.submit(command, expected_version=1)
    assert retry['commit_id'] == result['commit_id']
    assert len(store.load().project('log')) == 2


def test_stale_version_is_domain_conflict(tmp_path):
    game = load_scenario()
    store = SQLiteStore(tmp_path / 'stale.sqlite', CommonsGame)
    store.initialise(game)
    result = store.submit({'key': 'new', 'kind': 'propose', 'actor': 'researcher',
                           **definition('bilateral-logs')['proposal']}, expected_version=0)
    assert result['errors'] == ['stale_version']
    assert len(store.load().project('log')) == 1


def test_recorded_time_expiration_releases_resource_and_blocks_execution():
    game = load_scenario()
    ready(game); assert move(game, 'activate')['ok']
    assert send(game, 'advance_time', 'researcher', time='2027-01-01T00:00:00+00:00')['errors'] == ['facilitator_required']
    assert send(game, 'advance_time', 'facilitator', time='2027-01-01T00:00:00+00:00')['ok']
    assert game.project('agreements')[0]['status'] == 'expired'
    assert all(r['status'] == 'released' for r in game.project('reservations'))
    assert not move(game, 'initiate', reference='Late execution')['ok']
    assert game.replay().get_world() == game.get_world()


def test_fulfilment_requires_execution_and_is_separate_from_verification():
    game = load_scenario()
    ready(game); assert move(game, 'activate')['ok']
    criteria = definition('bilateral-logs')['proposal']['verification']['criteria']
    assert move(game, 'fulfill', reference='Promise only', criteria=criteria)['errors'] == ['execution_required']
    assert move(game, 'verify', 'verifier', reference='Too early')['errors'] == ['invalid_transition']
    for actor in ('researcher', 'custodian'):
        assert move(game, 'initiate', actor, reference='Execution actually recorded')['ok']
        assert move(game, 'fulfill', actor, reference='Evidence missing one criterion', criteria=criteria[:-1])['errors'] == ['all_criteria_required']
        assert move(game, 'fulfill', actor, reference='All synthetic criteria addressed', criteria=criteria)['ok']
    assert game.project('agreements')[0]['status'] == 'fulfilled'
    assert game.project('agreements')[0]['outcome_status'] == 'unverified'
    assert game.project('objectives')[0]['status'] == 'open'
    assert game.project('reservations')[0]['status'] == 'held'
    assert move(game, 'verify', 'researcher', reference='Self-verify')['errors'] == ['independent_verifier_required']
    assert move(game, 'verify', 'officer', reference='Wrong verifier')['errors'] == ['unauthorized_verifier']
    assert move(game, 'verify', 'verifier', reference='Independent criterion review')['ok']
    assert game.project('objectives')[0]['status'] == 'verified'
    assert game.project('reservations')[0]['status'] == 'released'


@pytest.mark.parametrize('payload,error', [
    ({'kind':'accept','actor':'researcher','agreement_id':'missing','version':1}, 'unknown_agreement'),
    ({'kind':'advance_time','actor':'facilitator','time':'invalid'}, 'invalid_timestamp'),
    ({'kind':'advance_time','actor':'facilitator','time':'2026-12-01'}, 'timezone_required'),
    ({'kind':'declare','actor':'researcher','table':'actors','record':{}}, 'invalid_declaration_table'),
    ({'kind':'accept','actor':'nobody','agreement_id':'missing','version':1}, 'unknown_actor'),
])
def test_invalid_commands_leave_no_partial_mutations(payload,error):
    game = load_scenario()
    assert_rejected_unchanged(game, {'key':'invalid', **payload}, error)


def test_active_amendment_cannot_rewrite_reserved_terms():
    game = load_scenario()
    ready(game); assert move(game, 'activate')['ok']
    terms = definition('bilateral-logs')['proposal']['terms']
    before = game.get_world(), game.project('log')
    assert move(game, 'amend', terms=terms)['errors'] == ['invalid_transition']
    assert before == (game.get_world(), game.project('log'))


def test_suspension_dispute_and_termination_are_explicit():
    game = load_scenario()
    ready(game); assert move(game, 'activate')['ok']
    assert move(game, 'suspend', 'custodian', reason='Review privacy conditions')['ok']
    assert game.project('reservations')[0]['status'] == 'held'
    assert not move(game, 'initiate', reference='During suspension')['ok']
    assert move(game, 'resume')['ok']
    assert move(game, 'dispute', 'custodian', reason='Delivery disputed')['ok']
    assert move(game, 'terminate', reason='Close disputed agreement')['ok']
    assert game.project('reservations')[0]['status'] == 'released'


def test_external_capacity_requires_independent_reconciliation():
    game = load_scenario()
    # Synthetic fixture variation; re-seed as an external resource, never mutate a live world.
    world = game.get_world()
    world['resources']['synthetic-logs'].update(control='external', status='reported')
    game = CommonsGame(); game._commit(game.get_world(), world, 'world.initialized')
    ready(game)
    assert move(game, 'activate')['errors'] == ['external_resource_unverified']
    assert send(game, 'reconcile_resource', 'verifier', resource_id='synthetic-logs', quantity=1,
                reference='Synthetic custodian confirmation')['ok']
    assert move(game, 'activate')['ok']


def test_replay_detects_commit_state_tampering():
    game = run_demo()
    entries = game.project('log')
    entries[-1]['commit']['resulting_state'] = 'forged'
    with pytest.raises(DomainError, match='invalid_commit_state'):
        CommonsGame.from_log(entries)


def test_discovery_is_reported_and_matches_are_disposable_not_agreements():
    game = load_scenario()
    before = game.get_world(), game.project('log')
    potential = game.derive_possibilities()
    assert potential[0]['status'] == 'inferred'
    assert before == (game.get_world(), game.project('log'))
    assert not game.project('agreements')
    assert send(game, 'declare', 'researcher', table='relationships', record={
        'source_id':'custodian', 'target_id':'institution', 'kind':'knows', 'note':'A reported connection'})['ok']
    record = game.project('relationships')[-1]
    assert record['status'] == 'reported' and record['created_by'] == 'researcher'


def test_multiplex_agreement_is_a_separate_node():
    game = load_scenario()
    assert propose(game)['ok']
    graph = game.project('network')
    assert any(n['kind'] == 'agreement' for n in graph['nodes'])
    assert len([e for e in graph['edges'] if e['layer'] == 'agreement']) == 2
    assert graph['edges'][0]['layer'] == 'declared'


def test_missing_matrix_responses_are_not_known_zeros_and_direction_is_retained():
    result = complementarity([[1,None],[0,1]], [[0,1],[1,0]])
    assert result['B'][0] == [1,1]
    assert result['W'][0][0] == {'value':None,'lower':0,'upper':1,'missing_terms':1}
    assert result['W'][0][1]['value'] == 1
    assert result['W'][1][0]['value'] == 1
    assert result['W'][1][1]['value'] == 0
    assert complementarity([[None]], [[0]])['B'] == [[None]]
    assert complementarity([[1]], [[1]])['W'][0][0]['value'] == 1


def test_gathering_requires_recipient_consent_and_attendance():
    game = load_scenario('commons-gathering')
    proposal = definition('commons-gathering')['proposal']
    assert send(game, 'propose', **proposal)['ok']
    for actor in proposal['parties']:
        assert move(game, 'accept', actor)['ok']
    for actor in ('researcher','officer'):
        assert move(game, 'authorize', actor)['ok']
    assert move(game, 'activate')['errors'] == ['gathering_attendance_required']
    assert send(game, 'invite', recipient_id='custodian', objective_id='objective-main')['ok']
    invitation = next(r for r in game.project('relationships') if r['kind'] == 'invited')
    assert send(game, 'respond_invitation', invitation_id=invitation['id'], response='accept')['errors'] == ['recipient_required']
    assert send(game, 'respond_invitation','custodian',invitation_id=invitation['id'],response='accept')['ok']


def test_infrastructure_failure_is_not_misreported_as_domain_rejection(tmp_path):
    with pytest.raises(ValueError, match='game_not_started'):
        SQLiteStore(tmp_path/'missing.sqlite', CommonsGame).submit({})


def test_hube_uses_same_shared_engine_and_all_original_tests_pass():
    sibling = Path(__file__).resolve().parents[2] / 'game_hube'
    if not sibling.exists():
        pytest.skip('Sibling compatibility requires the game_hube source checkout')
    code = 'from game import Game; from commons_engine import WorldEngine; assert issubclass(Game, WorldEngine)'
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=sibling, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                            cwd=sibling, capture_output=True, text=True, timeout=60,
                            env={**__import__('os').environ,'PYTHONDONTWRITEBYTECODE':'1'})
    assert result.returncode == 0, result.stdout + result.stderr
    assert '58 passed' in result.stdout
