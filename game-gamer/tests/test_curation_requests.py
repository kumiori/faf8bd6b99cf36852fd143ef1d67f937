from game_gamer import ActionSubmission, SimulationBinding, Collective
from game_gamer.runtime.curation_requests import records
from test_curation import start


def act(game, actor, kind, **payload):
    target = payload.get('target_id') or payload.get('request_id')
    command = ActionSubmission(action_id=f'{kind}-{game.revision}', actor_id=actor, scope_id=game.scope_id,
                               target_id=target, expected_revision=game.revision, action_type=kind, payload=payload)
    return game.submit(command, binding=SimulationBinding(scope_id=game.scope_id, actor_id=actor))


def test_request_review_clarification_and_final_decision_replay(tmp_path):
    game = start(tmp_path/'reviews.sqlite')
    assert act(game, 'a', 'request_curation', target_id='b', request_type='correction',
               reason='Wrong motivation', proposed_changes={'motivation': 'A supplied statement'})['ok']
    ident = next(iter(records(game.project('world'))))
    assert act(game, 'a', 'review_curation_request', request_id=ident, decision='approve', reason='Self review')['errors'] == ['curator_required']
    assert act(game, 'curator', 'review_curation_request', request_id=ident, decision='request_clarification', reason='Please cite the source')['ok']
    assert act(game, 'b', 'clarify_curation_request', request_id=ident, reason='Other player')['errors'] == ['requester_required']
    assert act(game, 'a', 'clarify_curation_request', request_id=ident, reason='Participant statement, page 1')['ok']
    assert act(game, 'curator', 'review_curation_request', request_id=ident, decision='approve', reason='Source reviewed')['ok']
    request = records(game.project('world'))[ident]
    assert request['status'] == 'approved' and len(request['history']) == 4
    assert game.project('world')['actors']['b'].get('motivation') is None
    assert act(game, 'curator', 'review_curation_request', request_id=ident, decision='reject', reason='Too late')['errors'] == ['request_review_is_final']
    assert Collective.from_history(game.history()).project() == game.project()
    assert Collective.open(tmp_path/'reviews.sqlite', scope_id=game.scope_id).project() == game.project()


def test_requests_cannot_propose_roles_or_merge_without_a_second_identity():
    game = start()
    assert act(game, 'a', 'request_curation', target_id='a', request_type='correction',
               proposed_changes={'roles': ['curator']}, reason='Grant powers')['errors'] == ['invalid_proposed_correction']
    assert act(game, 'a', 'request_curation', target_id='a', request_type='duplicate_merge',
               reason='Missing second identity')['errors'] == ['merge_request_actors_required']
    assert act(game, 'a', 'request_curation', target_id='duplicate', related_id='a',
               request_type='duplicate_merge', reason='Please check these records')['ok']
    ident = next(iter(records(game.project('world'))))
    assert act(game, 'curator', 'review_curation_request', request_id=ident, decision='reject', reason='Distinct people')['ok']


def test_retry_binding_and_replay_prefixes_do_not_duplicate_requests(tmp_path):
    game = start(tmp_path/'retry.sqlite')
    request = ActionSubmission(action_id='review-profile', actor_id='a', scope_id=game.scope_id,
                               target_id='b', expected_revision=game.revision, action_type='request_curation',
                               payload={'target_id': 'b', 'request_type': 'profile_review', 'reason': 'Check provenance'})
    binding = SimulationBinding(scope_id=game.scope_id, actor_id='a')
    original = game.history()
    assert not game.submit(request, binding=SimulationBinding(scope_id=game.scope_id, actor_id='b'))['ok']
    assert game.history() == original
    first = game.submit(request, binding=binding)
    assert first['ok']
    committed = game.history()
    assert game.submit(request, binding=binding)['ok']
    assert game.history() == committed and len(records(game.project('world'))) == 1
    reopened = Collective.open(tmp_path/'retry.sqlite', scope_id=game.scope_id)
    assert reopened.submit(request, binding=binding)['ok']
    assert reopened.history() == committed
    assert Collective.from_history(original).project('world') != game.project('world')
    assert Collective.from_history(committed).project('world') == game.project('world')


def test_requester_authority_follows_verified_canonical_identity():
    from game_gamer.runtime.curation import merge_preview
    game = start()
    assert act(game, 'a', 'request_curation', target_id='b', request_type='profile_review', reason='Check source')['ok']
    ident = next(iter(records(game.project('world'))))
    assert act(game, 'curator', 'review_curation_request', request_id=ident,
               decision='request_clarification', reason='Which source?')['ok']
    preview = merge_preview(game.project('world'), 'a', 'duplicate')
    assert act(game, 'curator', 'merge_profiles', source_id='a', target_id='duplicate',
               preview_digest=preview['digest'], identity_confirmed=True, reference='Identity confirmed')['ok']
    assert act(game, 'duplicate', 'clarify_curation_request', request_id=ident, reason='Source page 2')['ok']
    request = records(game.project('world'))[ident]
    assert request['requester_id'] == 'a' and request['history'][-1]['actor_id'] == 'duplicate'
    assert Collective.from_history(game.history()).project() == game.project()
