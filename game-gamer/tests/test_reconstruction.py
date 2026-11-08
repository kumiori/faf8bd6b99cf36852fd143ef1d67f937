from concurrent.futures import ThreadPoolExecutor

from game_gamer import ActionSubmission, Collective, SimulationBinding


def start(path=None):
    return Collective.start({
        'schema': 'game-gamer/world/v1', 'scope_id': 'forum', 'revision': 1,
        'execution_mode': 'simulation', 'world_time': '2026-10-01T00:00:00+00:00',
        'title': 'Fictional forum',
        'actors': [{'id': key, 'label': name} for key, name in
                   [('a', 'Ada'), ('b', 'Bina'), ('c', 'Cal')]],
    }, path=path)


def submit(game, actor, kind, key, *, revision=None, **payload):
    target = next((payload[k] for k in ('claim_id', 'target_id', 'invitation_id', 'id', 'merge_id') if k in payload), None)
    submission = ActionSubmission(
        action_id=key, actor_id=actor, scope_id=game.scope_id, target_id=target,
        expected_revision=revision or game.project()['version'], action_type=kind, payload=payload)
    return game.submit(submission, binding=SimulationBinding(scope_id=game.scope_id, actor_id=actor))


def test_recall_is_a_directed_declaration_with_its_own_event_time():
    game = start()
    assert submit(game, 'a', 'recall_connection', 'first', target_id='b', context_id='forum-2025',
                  historical_date='2025-10-01')['ok']
    claim, = game.project('relationships')
    assert (claim['source_id'], claim['target_id'], claim['status']) == ('a', 'b', 'claimed')
    assert claim['historical_date'] == '2025-10-01'
    assert claim['created_at'] == game.project('log')[-1]['occurred_at']
    assert claim['provenance']['kind'] == 'player_declaration'
    assert game.project('network')['edges'][0]['layer'] == 'recollection'


def test_distinct_players_corroborate_and_can_retract_only_their_own_claim(tmp_path):
    path = tmp_path / 'world.sqlite'
    game = start(path)
    original_revision = game.project()['version']
    first = submit(game, 'a', 'recall_connection', 'first', target_id='b', context_id='forum')
    assert first['ok']
    assert submit(game, 'a', 'recall_connection', 'first', revision=original_revision,
                  target_id='b', context_id='forum') == first
    assert submit(game, 'a', 'recall_connection', 'duplicate', target_id='b', context_id='forum')['errors'] == [
        'duplicate_relationship_claim']
    first_id = game.project('relationships')[0]['id']
    assert submit(game, 'b', 'retract_relationship_claim', 'wrong-actor', claim_id=first_id)['errors'] == [
        'claim_author_required']
    assert submit(game, 'b', 'recall_connection', 'reply', target_id='a', context_id='forum')['ok']
    edge, = game.project('network')['edges']
    assert edge['layer'] == 'corroborated' and edge['directed'] is False
    assert len(edge['claim_ids']) == 2
    assert submit(game, 'a', 'retract_relationship_claim', 'withdraw', claim_id=first_id)['ok']
    edge, = game.project('network')['edges']
    assert (edge['source_id'], edge['target_id'], edge['layer']) == ('b', 'a', 'recollection')
    assert submit(game, 'a', 'recall_connection', 'corrected', target_id='b', context_id='forum',
                  note='Corrected account')['ok']
    reopened = Collective.open(path, scope_id='forum')
    assert reopened.project('relationships')[0]['status'] == 'retracted'
    assert Collective.from_history(reopened.history()).project() == game.project()
    for revision in range(1, game.project()['version'] + 1):
        assert reopened.project(at=revision) == game.project(at=revision)


def test_concurrent_players_retry_conflicts_without_losing_the_other_claim(tmp_path):
    path = tmp_path / 'shared.sqlite'
    game = start(path)
    revision = game.project()['version']

    def recall(pair):
        actor, target = pair
        client = Collective.open(path, scope_id='forum')
        result = submit(client, actor, 'recall_connection', actor, revision=revision,
                        target_id=target, context_id='forum')
        if not result['ok']:
            assert result['errors'] == ['stale_version']
            result = submit(client, actor, 'recall_connection', actor, target_id=target, context_id='forum')
        return result

    with ThreadPoolExecutor(2) as pool:
        assert all(result['ok'] for result in pool.map(recall, [('a', 'b'), ('b', 'a')]))
    assert game.project()['version'] == revision + 2
    assert game.project('network')['edges'][0]['status'] == 'corroborated'


def test_dispute_prior_relationship_and_contact_are_separate_layers():
    game = start()
    assert submit(game, 'a', 'recall_connection', 'memory', target_id='b', context_id='forum')['ok']
    claim = game.project('relationships')[0]['id']
    assert submit(game, 'c', 'dispute_recollection', 'outsider', claim_id=claim)['errors'] == ['recipient_required']
    assert submit(game, 'b', 'dispute_recollection', 'dispute', claim_id=claim)['ok']
    assert submit(game, 'a', 'record_prior_relationship', 'prior', target_id='b', context_id='forum')['ok']
    assert submit(game, 'a', 'send_contact', 'invite', id='inv', recipient_id='b', message='Talk?')['ok']
    binding = SimulationBinding(scope_id=game.scope_id, actor_id='b')
    assert any(row['id'] == 'inv' for row in game.inbox(binding=binding))
    assert submit(game, 'b', 'respond_contact', 'yes', invitation_id='inv', response='accept')['ok']
    layers = {edge['layer'] for edge in game.project('network')['edges']}
    assert layers == {'disputed_recollection', 'prior_relationship', 'invitation', 'connection'}


def test_source_transcription_and_photo_remain_distinct_from_recollection():
    from game_gamer import epistemic_status

    game = Collective.start({
        'schema': 'game-gamer/world/v1', 'scope_id': 'second-forum', 'revision': 1,
        'execution_mode': 'simulation', 'world_time': '2026-10-01T00:00:00+00:00', 'title': 'Second forum',
        'actors': [{'id': 'a', 'label': 'Ada'}, {'id': 'b', 'label': 'Bina'}],
        'reconstruction_sources': [
            {'id': 'photo', 'kind': 'whiteboard_photo', 'context_id': 'f', 'reference': 'photo:page-1'},
            {'id': 'possible-link', 'kind': 'whiteboard_connection', 'context_id': 'f',
             'source_id': 'a', 'target_id': 'b', 'directed': None, 'observation': 'possible',
             'reference': 'transcription:row-1'},
            {'id': 'statement', 'kind': 'participant_statement', 'context_id': 'f',
             'actor_id': 'b', 'statement': 'Find a collaborator', 'reference': 'notes:row-1'},
        ],
    })
    historical, = game.project('network')['edges']
    assert historical['layer'] == 'historical_whiteboard' and historical['directed'] is None
    assert historical['observation'] == 'possible'
    assert epistemic_status(historical) == 'historical_evidence'
    assert not game.project('relationships')
    from game_gamer.projections.participants import ParticipantDirectory, ParticipantFilters
    directory = ParticipantDirectory(game.project('world'), context_id='f')
    assert [p.name for p in directory.browse(ParticipantFilters('motivation', 'collaborator'))] == ['Bina']
    assert directory.profiles['a'].motivation is None


def test_directory_filters_declared_attributes_and_portrait_is_stable_after_claims():
    from game_gamer.projections.participants import ParticipantDirectory, ParticipantFilters
    from game_gamer.tui.portrait import generate_portrait

    game = start()

    def directory():
        return ParticipantDirectory(game.project('world'), reconstruction=game.project('network')['edges'])

    before = directory()
    assert [p.name for p in before.browse(ParticipantFilters('name', 'bín'))] == ['Bina']
    assert not before.browse(ParticipantFilters('motivation', 'invented'))
    assert before.profiles['a'].motivation is None
    portrait = generate_portrait('a', before.profiles['a'])
    assert submit(game, 'a', 'declare', 'offer', table='capacities',
                  record={'domain': 'Mapping', 'quantity': 1, 'unit': 'hour'})['ok']
    with_offer = directory()
    assert [p.id for p in with_offer.browse(ParticipantFilters('offers', 'mapping'))] == ['a']
    assert generate_portrait('a', with_offer.profiles['a']) != portrait
    assert submit(game, 'a', 'recall_connection', 'connect', target_id='b', context_id='forum')['ok']
    after = directory()
    assert [p.id for p in after.browse(ParticipantFilters('neighbourhood'), neighbour_of='a')] == ['b']
    for size in ('small', 'medium', 'large'):
        shown = generate_portrait('a', after.profiles['a'], size=size, plain=True)
        assert shown == generate_portrait('a', with_offer.profiles['a'], size=size, plain=True)
        assert all(line.isascii() for line in shown.lines)
        assert '1 recorded offers' in shown.description


def test_filters_sorts_and_unknown_questionnaire_fields_remain_explicit():
    from game_gamer.projections.participants import ParticipantDirectory, ParticipantFilters

    world = start().project('world')
    world['actors']['org'] = {'id': 'org', 'label': 'Test institution', 'kind': 'organisation',
                              'status': 'active', 'roles': []}
    world['actors']['b']['roles'] = ['research']
    world['relationships']['affiliation'] = {
        'id': 'affiliation', 'kind': 'affiliated_with', 'source_id': 'b', 'target_id': 'org',
        'status': 'reported'}
    directory = ParticipantDirectory(world, questionnaire={
        'capacities': {'a': {'domains': ['Maps'], 'state': 'answered'},
                       'b': {'domains': ['Maps'], 'state': 'partial'},
                       'c': {'domains': [], 'state': 'skipped'}},
        'needs': {'a': {'domains': [], 'state': 'answered'}},
    })
    for field, query, expected in [('roles', 'research', ['b']), ('organisations', 'institution', ['b']),
                                    ('actor_type', 'organisation', ['org']), ('offers', 'maps', ['a', 'b'])]:
        assert [p.id for p in directory.browse(ParticipantFilters(field, query))] == expected
    assert 'motivation' not in directory.available_filters
    assert directory.profiles['a'].needs_state == 'answered'
    assert directory.profiles['c'].offers_state == 'skipped'
    assert [p.id for p in directory.browse(sort='shared_offers', reference='a')][:2] == ['a', 'b']
    assert directory.browse(sort='organisation')[0].id == 'b'


def test_portraits_are_identical_in_fresh_interpreters_with_different_hash_seeds():
    import json
    import os
    import subprocess
    import sys

    source = """
import json
from game_gamer.projections.participants import ParticipantProfile
from game_gamer.tui.portrait import generate_portrait
profile = ParticipantProfile('b', 'Bina', 'person', offers=('Maps',), needs=('Data',))
print(json.dumps(generate_portrait('b', profile, plain=True).lines))
"""
    results = [subprocess.run([sys.executable, '-B', '-c', source], env={**os.environ, 'PYTHONHASHSEED': seed},
                              capture_output=True, text=True, check=True).stdout for seed in ('1', '5831')]
    assert results[0] == results[1]
    assert json.loads(results[0])[0] == '+-------------+'


def test_unrelated_worlds_and_contexts_cannot_corroborate_each_other():
    game = start()
    assert submit(game, 'a', 'recall_connection', 'a', target_id='b', context_id='first-forum')['ok']
    assert submit(game, 'b', 'recall_connection', 'b', target_id='a', context_id='second-forum')['ok']
    edges = game.project('network')['edges']
    assert len(edges) == 2 and {edge['layer'] for edge in edges} == {'recollection'}
    other = start()
    assert other.project('network')['edges'] == []
    assert submit(game, 'a', 'recall_connection', 'self', target_id='a', context_id='first-forum')['errors'] == [
        'invalid_claim_target']
