"""User journeys over one authoritative world; mocks never authenticate people."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys

import pytest

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.ecosystem_import import (SCHEMA, capture_snapshot, connector_people_snapshot,
                                          import_snapshot, source_id)
from commons_game.identity import MockIdentityProvider, ActorBinding, request_binding
from commons_game.player import ActorSession
from commons_game.projections import neighbourhood, contract_registry
from commons_game.scenario import definition, demo_commands
from commons_game.tui import Terminal, run_play

ROOT = Path(__file__).resolve().parents[1]
CAPTURED = '2026-11-04T10:00:00+00:00'


def snapshot():
    # Explicitly fictional source records. No real names or private source export.
    rows = [{'url': 'https://app.notion.com/' + str(i) * 32, 'Name': f'Fixture Person {i}',
             'institution': 'Fixture organisation', 'createdTime': '2026-10-01T00:00:00+00:00'} for i in (1, 2)]
    return connector_people_snapshot(rows, captured_at=CAPTURED, data_source_id='fixture-source', database_id='fixture-db')


def imported_world():
    game = load_scenario('montreal-commons')
    report = import_snapshot(game, snapshot())
    assert len(report['created']) == 6 and not report['rejected']
    people = [a['id'] for a in game.project('actors') if a['kind'] == 'person' and a['provenance']['kind'] == 'notion_snapshot']
    provider = MockIdentityProvider({'mode': 'simulation', 'players': {
        'a': {'label': 'Player A (mock)', 'bindings': [{'actor_id': people[0]}]},
        'b': {'label': 'Player B (mock)', 'bindings': [{'actor_id': people[1]}]},
        'guest': {'label': 'Unbound (mock)', 'bindings': []}}})
    return game, provider, people


def bound(game, provider, subject, store=None):
    identity = provider.sign_in(subject)
    binding = provider.bindings(identity)[0]
    return ActorSession(game, binding.actor_id, store=store, identity=identity, binding=binding, provider=provider)


def proposal(people):
    return {'kind': 'propose', 'id': 'collaboration-1', 'label': 'Simulated collaboration',
        'parties': people, 'objective_id': 'montreal-collaboration',
        'terms': {'purpose': 'Explore a possible collaboration (simulation)',
                  'conditions': ['No genuine consent or institutional authority implied.'],
                  'responsibilities': [{'actor_id': p, 'description': 'Discuss the proposed plan'} for p in people]},
        'resources': [], 'valid_until': '2026-12-01T00:00:00+00:00', 'policy_id': 'simulation-personal',
        'verification': {'independent': True, 'verifier_ids': ['simulation-verifier'], 'criteria': ['Documented evidence reviewed']}}


def test_contract_is_immediate_connected_stable_and_replayable_through_lifecycle():
    game = load_scenario()
    script = demo_commands()
    assert game.submit(script[0])['ok']
    graph = game.project('network')
    contract = next(n for n in graph['nodes'] if n['kind'] == 'agreement')
    assert contract['status'] == 'proposed' and contract['outcome_status'] == 'unverified'
    assert len([n for n in graph['nodes'] if n['id'] == contract['id']]) == 1
    edges = neighbourhood(graph, contract['id'])['edges']
    assert {'party_to', 'proposed_by', 'concerns_resource', 'serves_objective', 'requires_authorisation'} <= {e['kind'] for e in edges}
    for command in script[1:]:
        assert game.submit(command)['ok']
        assert len([n for n in game.project('network')['nodes'] if n['id'] == contract['id']]) == 1
    current = next(n for n in game.project('network')['nodes'] if n['id'] == contract['id'])
    assert current['current_version'] == 2 and current['status'] == 'fulfilled' and current['outcome_status'] == 'verified'
    assert any(e['kind'] == 'has_evidence' for e in game.project('network')['edges'])
    assert game.replay().project('network') == game.project('network')
    assert contract_registry(game.get_world(), actor='custodian', resource='synthetic-logs')[0]['id'] == contract['id']
    assert not contract_registry(game.get_world(), status='proposed')


def test_rejected_and_expired_contracts_keep_their_graph_node():
    for kind, extra in [('reject', {'reason': 'Declined in simulation'}), ('advance_time', {'time': '2027-01-01T00:00:00+00:00'})]:
        game = load_scenario(); assert game.submit(demo_commands()[0])['ok']
        command = {'key': kind, 'kind': kind, 'actor': 'custodian' if kind == 'reject' else 'facilitator', **extra}
        if kind == 'reject':
            command.update(agreement_id='agreement-main', version=1)
        assert game.submit(command)['ok']
        assert next(n for n in game.project('network')['nodes'] if n['kind'] == 'agreement')['status'] in {'rejected', 'expired'}
        assert game.replay().project('network') == game.project('network')


def test_import_is_idempotent_source_scoped_and_never_imports_authority_or_credentials():
    game, provider, people = imported_world()
    assert len(set(people)) == 2
    organisations = [a for a in game.project('actors') if a['kind'] == 'organisation']
    assert len(organisations) == 2  # Same label is not an identity reconciliation.
    assert all(not a['roles'] for a in organisations)
    before = game.get_world(), game.project('log')
    report = import_snapshot(game, snapshot())
    assert len(report['skipped']) == 6 and before == (game.get_world(), game.project('log'))
    modified = snapshot(); modified['records'][0]['fields']['roles'] = ['authorizer']
    report = import_snapshot(game, modified)
    assert report['rejected'][0]['reason'] == 'unsupported_source_field'
    assert not game.project('agreements') and not game.project('commitments')
    assert game.replay().get_world() == game.get_world()


def test_import_updates_retains_absence_and_rejects_stale_or_unresolved_records():
    game, _, people = imported_world()
    changed = snapshot(); changed['captured_at'] = '2026-11-05T10:00:00+00:00'
    changed['records'] = changed['records'][:1]; changed['records'][0]['fields']['label'] = 'Revised display name'
    assert import_snapshot(game, changed)['updated'] == [people[0]]
    assert people[1] in game.get_world()['actors']
    assert import_snapshot(game, snapshot())['rejected'][0]['reason'] == 'stale_snapshot'
    bad = snapshot(); bad['records'] = [{'kind': 'need', 'data_source_id': 's', 'record_id': 'n',
        'fields': {'actor_id': 'missing', 'domain': 'research'}, 'source_properties': {}}]
    assert import_snapshot(game, bad)['rejected'][0]['reason'] == 'unresolved_source_reference'


def test_import_capacities_needs_resources_and_missingness_remain_assertions():
    game, _, people = imported_world(); data = snapshot(); data['records'] = []
    for kind, fields in [('capacity', {'actor_id': people[0], 'domain': 'research'}),
                         ('need', {'actor_id': people[1], 'domain': 'research'}),
                         ('resource', {'owner_id': people[0], 'label': 'Documented resource', 'quantity': 1, 'unit': 'item'})]:
        data['records'].append({'kind': kind, 'data_source_id': 's', 'record_id': kind, 'fields': fields})
    report = import_snapshot(game, data)
    assert len(report['created']) == 3 and not report['rejected']
    assert game.project('capacities')[0]['quantity'] is None and game.project('needs')[0]['unit'] is None
    assert game.project('resources')[0]['control'] == 'external'
    assert game.project('resources')[0]['status'] == 'reported'


def test_capture_paginates_allows_only_mapped_fields_and_uses_source_ids():
    class Client:
        def query(self, source, **kwargs):
            page = {'id': 'p2' if kwargs.get('start_cursor') else 'p1',
                    'properties': {'Name': {'type': 'title', 'title': [{'plain_text': 'Fixture'}]},
                                   'access_key': {'type': 'rich_text', 'rich_text': [{'plain_text': 'SECRET'}]}}}
            return {'results': [page], 'has_more': not kwargs.get('start_cursor'), 'next_cursor': 'next'}
    data = capture_snapshot(Client(), [{'kind': 'person', 'data_source_id': 's', 'properties': {'label': 'Name'}}], captured_at=CAPTURED)
    assert len(data['records']) == 2 and 'SECRET' not in json.dumps(data) and 'access_key' not in json.dumps(data)
    assert data['records'][0]['fields'] == {'label': 'Fixture'}


def test_unverified_claims_and_affiliations_never_grant_bindings(tmp_path):
    game, provider, people = imported_world()
    guest = provider.sign_in('guest')
    store = SQLiteStore(tmp_path/'world.sqlite', CommonsGame); store.initialise(game)
    request = store.transact(lambda g: request_binding(g, guest, actor_id=people[0]))
    assert request['request']['status'] == 'pending'
    assert store.transact(lambda g: request_binding(g, guest, actor_id=people[0]))['duplicate']
    assert not provider.bindings(guest)
    fabricated = ActorBinding('local_mock', 'guest', people[0], 'verified_simulation')
    with pytest.raises(ValueError, match='verified_simulation_binding_required'):
        ActorSession(game, people[0], identity=guest, binding=fabricated, provider=provider)
    identity = provider.sign_in('a'); org = next(a for a in game.project('actors') if a['kind'] == 'organisation')
    with pytest.raises(ValueError, match='verified_simulation_binding_required'):
        ActorSession(game, org['id'], identity=identity, binding=provider.bindings(identity)[0], provider=provider)
    assert store.load().replay().get_world() == store.load().get_world()


def test_mock_binding_cannot_switch_forge_an_actor_or_claim_real_authentication():
    game, provider, people = imported_world(); session = bound(game, provider, 'a')
    with pytest.raises(ValueError, match='sign_out_before_changing_player'):
        session.switch(people[1])
    assert session.submit({**proposal(people), 'actor': people[1]})['errors'] == ['actor_mismatch']
    assert session.submit(proposal(people))['ok']
    event = game.project('log')[-1]
    assert event['command']['session']['authenticated'] is False
    assert event['commit']['authorization']['session']['mode'] == 'simulation'
    command = {'kind': 'accept', 'agreement_id': 'collaboration-1', 'version': 1, 'key': 'live', 'actor': people[0],
               'session': {**event['command']['session'], 'mode': 'live', 'authenticated': True}}
    assert game.submit(command)['errors'] == ['live_identity_unavailable']


def test_two_players_concurrent_transitions_restart_inbox_and_native_trajectory(tmp_path):
    pytest.importorskip('trajectory_engine')
    from commons_game.trajectory import project_trajectory, reconstruct, trajectory_yaml, load_trajectory_yaml
    game, provider, people = imported_world(); store = SQLiteStore(tmp_path/'world.sqlite', CommonsGame); store.initialise(game)
    a, b = bound(game, provider, 'a', store), bound(game, provider, 'b', store)
    assert a.submit({**proposal(people), 'key': 'proposal'}, expected_version=2)['ok']
    assert b.inbox()[0]['reasons'] == ['Proposal awaiting your response']
    before = len(store.load().project('log'))
    def accept(session, key):
        return session.submit({'kind': 'accept', 'key': key, 'agreement_id': 'collaboration-1', 'version': 1}, expected_version=before)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda pair: accept(*pair), [(a, 'accept-a'), (b, 'accept-b')]))
    assert sum(r['ok'] for r in results) == 1 and any(r.get('errors') == ['stale_version'] for r in results)
    loser, key = (a, 'accept-a') if not results[0]['ok'] else (b, 'accept-b')
    assert loser.submit({'kind': 'accept', 'key': key, 'agreement_id': 'collaboration-1', 'version': 1},
                        expected_version=len(store.load().project('log')))['ok']
    assert accept(loser, key)['ok']  # Exact retry remains idempotent after restart/version drift.
    recovered = store.load(); assert len(recovered.project('log')) == before + 2
    agreement = recovered.project('agreements')[0]
    assert agreement['status'] == 'accepted' and agreement['outcome_status'] == 'unverified'
    assert not a.inbox() and not b.inbox()
    assert all(x['method'] == 'mock_identity_simulation' for x in agreement['versions'][0]['acceptances'].values())
    document = load_trajectory_yaml(trajectory_yaml(project_trajectory(recovered)))
    assert reconstruct(document).get_world() == recovered.get_world()
    assert reconstruct(document).project('network') == recovered.project('network')
    assert document['plan']['commons_trajectory']['provenance']['world_kind'] == 'empirical_ecosystem_simulation'


def test_terminal_graph_inbox_direct_links_and_onboarding_are_reachable():
    game, provider, people = imported_world()
    assert bound(game, provider, 'a').submit(proposal(people))['ok']
    output = StringIO()
    run_play(game, provider=provider, identity=provider.sign_in('b'), plain=True,
        source=StringIO('n\nopen collaboration-1\nact collaboration-1\n1\ny\nb\ng\nopen collaboration-1\nhistory collaboration-1\nb\nx\n1\nb\n3\nq\n'), output=output)
    text = output.getvalue()
    assert 'SADDLE PATHWAYS' in text and 'CONTRACT INBOX / SIMULATION' in text
    assert 'Proposal awaiting your response' in text and 'NEIGHBOURHOOD' in text and 'HISTORICAL STATE' in text
    assert 'SIMULATED ACTION' in text and 'Signed out.' in text and 'All current actions are simulated.' in text
    assert game.project('agreements')[0]['versions'][0]['acceptances'].keys() == {people[1]}
    assert game.project('agreements')[0]['outcome_status'] == 'unverified'


def test_terminal_proposal_direct_open_and_ecosystem_visibility():
    game = load_scenario(); output = StringIO()
    run_play(game, actor='researcher', source=StringIO('3\na\n1\n\n\n\ny\no\ng\nb\nh\nb\n1\nb\nq\n'), output=output)
    text = output.getvalue()
    assert 'I hereby declare the right of the commons.' in text
    assert 'CONTRACT NODES\nagreement-main' in text
    assert 'NEIGHBOURHOOD / CURRENT WORLD' in text and 'CREATION / HISTORICAL GRAPH' in text
    assert len(game.project('agreements')) == 1


def test_real_cli_import_two_mock_players_and_restart(tmp_path):
    pytest.importorskip('trajectory_engine')
    data = snapshot(); source = tmp_path/'source.json'; source.write_text(json.dumps(data))
    db = tmp_path/'world.sqlite'; prefix = [sys.executable, '-B', '-m', 'commons_game', '--db', str(db)]
    def cli(args, entered=''):
        result = subprocess.run(prefix + args, input=entered, capture_output=True, text=True, cwd=ROOT, timeout=20)
        assert result.returncode == 0, result.stderr
        return result.stdout
    cli(['start', 'montreal-commons'])
    assert len(json.loads(cli(['import-ecosystem', str(source)]))['created']) == 6
    game = CommonsGame.load(db)
    people = [a['id'] for a in game.project('actors') if a['provenance']['kind'] == 'notion_snapshot' and a['kind'] == 'person']
    manifest = tmp_path/'identities.json'
    manifest.write_text(json.dumps({'mode': 'simulation', 'players': {
        key: {'label': key + ' (mock)', 'bindings': [{'actor_id': actor}]} for key, actor in zip(('a','b'), people)}}))
    targets = [a for a in game.project('actors') if a['id'] != people[0]]
    target = next(i for i,a in enumerate(targets, 1) if a['id'] == people[1])
    first = ['1','a','1',str(target),'1','','Proposed discussion','Proposed contribution','','','','y','o','g','b','b','q']
    flags = ['play','--mock-identities',str(manifest),'--mock-player']
    output = cli(flags+['a'], '\n'.join(first)+'\n')
    assert 'SIMULATED ACTION' in output and 'NEIGHBOURHOOD' in output
    response = cli(flags+['b'], 'n\nopen contract-0001\nact contract-0001\n1\ny\nb\nq\n')
    assert 'Proposal awaiting your response' in response
    final = cli(flags+['a'], 'n\nact contract-0001\n1\ny\nb\n4\nt\nr\nb\nq\n')
    assert 'REPLAY CONSISTENT: True' in final and 'STATE 005 [recorded]' in final
    agreement = CommonsGame.load(db).project('agreements')[0]
    assert agreement['status'] == 'accepted' and agreement['outcome_status'] == 'unverified'
    assert len(agreement['versions'][0]['acceptances']) == 2


def test_inbox_tracks_amendments_authorisation_obligations_and_independent_review():
    game = load_scenario(); script = demo_commands()
    for command in script:
        assert game.submit(command)['ok']
        if command['kind'] == 'amend':
            assert ActorSession(game, 'researcher').inbox()[0]['reasons'] == ['Amendment awaiting your response']
        if command['kind'] == 'accept' and command['actor'] == 'custodian':
            assert ActorSession(game, 'officer').inbox()[0]['reasons'] == ['Awaiting your authorisation']
        if command['kind'] == 'activate':
            assert ActorSession(game, 'researcher').inbox()[0]['reasons'] == ['Outstanding obligations']
        if command['kind'] == 'fulfill' and command['actor'] == 'custodian':
            assert ActorSession(game, 'verifier').inbox()[0]['reasons'] == ['Independent verification requested']
    assert not ActorSession(game, 'verifier').inbox()


def test_onboarding_pending_claim_is_wired_without_granting_a_role():
    game, provider, people = imported_world(); output = StringIO()
    # Unbound mock sign-in → pending profile claim → real play unavailable → exit.
    run_play(game, provider=provider, source=StringIO('2\n3\nc\n'+people[0]+'\n3\nq\n'), output=output)
    text = output.getvalue()
    assert 'No verified simulation binding' in text and 'PENDING CLAIM' in text
    assert 'No acceptance or organisational authority granted' in text
    assert not game.project('agreements') and not provider.bindings(provider.sign_in('guest'))
    assert len([c for c in game.project('configuration') if c['id'].startswith('binding-request:')]) == 1
    assert game.replay().get_world() == game.get_world()


def test_unknown_direction_and_missing_units_are_not_silently_inferred():
    game, _, people = imported_world(); output = StringIO()
    Terminal(game, output=output).inspect_node(people[0])
    assert '[direction unknown]' in output.getvalue()
    data = snapshot(); data['records'] = [
        {'kind':kind,'data_source_id':'s','record_id':kind,'fields':{'actor_id':actor,'domain':'shared'}}
        for kind,actor in zip(('capacity','need'),people)]
    assert len(import_snapshot(game, data)['created']) == 2
    assert not game.derive_possibilities()
