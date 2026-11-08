from copy import deepcopy

from game_gamer import Collective
from game_gamer.runtime.curation import canonical, merge_preview, visible, profile
from test_reconstruction import submit


def start(path=None):
    return Collective.start({
        'schema': 'game-gamer/world/v1', 'scope_id': 'curation-test', 'revision': 1,
        'execution_mode': 'simulation', 'world_time': '2026-10-01T00:00:00+00:00',
        'title': 'Fictional identity review',
        'actors': [{'id': 'curator', 'label': 'Curator', 'roles': ['curator']},
                   {'id': 'a', 'label': 'A'}, {'id': 'duplicate', 'label': 'A'},
                   {'id': 'b', 'label': 'B'}],
    }, path=path)


def test_player_cannot_correct_hide_merge_or_reverse_identity():
    game = start()
    before = game.history()
    for kind, payload in [
        ('correct_profile', {'target_id': 'a', 'changes': {'label': 'Changed'}, 'reference': 'case'}),
        ('set_profile_visibility', {'target_id': 'a', 'visibility': 'hidden', 'reference': 'case'}),
        ('merge_profiles', {'source_id': 'duplicate', 'target_id': 'a', 'reference': 'case',
                            'identity_confirmed': True, 'preview_digest': 'x'}),
        ('reverse_profile_merge', {'merge_id': 'merge', 'reference': 'case'}),
    ]:
        assert submit(game, 'a', kind, kind, **payload)['errors'] == ['curator_required']
    assert game.history() == before


def test_merge_is_previewed_resolvable_and_reversible_without_rewriting_claims(tmp_path):
    path = tmp_path/'curation.sqlite'
    game = start(path)
    assert submit(game, 'duplicate', 'recall_connection', 'claim', target_id='b', context_id='forum')['ok']
    assert submit(game, 'b', 'recall_connection', 'reply', target_id='a', context_id='forum')['ok']
    history_before_merge = deepcopy(game.history()['events'])
    preview = merge_preview(game.project('world'), 'duplicate', 'a')
    assert preview['relationships'] == 2  # one affected by each side of the merge
    assert submit(game, 'curator', 'merge_profiles', 'merge', source_id='duplicate', target_id='a',
                  reference='Identity checked with participant', identity_confirmed=True,
                  preview_digest=preview['digest'])['ok']
    assert canonical(game.project('world'), 'duplicate') == 'a'
    graph = game.project('network')
    assert {edge['layer'] for edge in graph['edges']} == {'recollection'}
    assert len(graph['edges']) == 2  # aliases do not invent reciprocal corroboration
    assert any(edge.get('original_source_id') == 'duplicate' for edge in graph['edges'])
    assert game.history()['events'][:len(history_before_merge)] == history_before_merge
    assert submit(game, 'duplicate', 'recall_connection', 'alias', target_id='b', context_id='new')['errors'] == [
        'canonical_identity_required']
    merge_id = next(iter(game.project('world')['configuration']['curation']['merges']))
    assert submit(game, 'curator', 'reverse_profile_merge', 'reverse', merge_id=merge_id, reference='Identity review corrected')['ok']
    assert canonical(game.project('world'), 'duplicate') == 'duplicate'
    assert game.project('network')['edges'][0]['source_id'] == 'duplicate'
    assert Collective.open(path, scope_id='curation-test').project() == game.project()
    assert Collective.from_history(game.history()).project() == game.project()


def test_correction_visibility_and_provenance_keep_raw_source_and_authority():
    game = start()
    assert submit(game, 'curator', 'correct_profile', 'edit', target_id='a',
                  changes={'label': 'Ada', 'motivation': 'Map commons', 'profile_role': 'Research'},
                  reference='Participant correction')['ok']
    world = game.project('world')
    assert world['actors']['a']['label'] == 'A'
    assert profile(world, 'a')['label'] == 'Ada'
    assert submit(game, 'curator', 'correct_profile', 'grant', target_id='a', changes={'roles': ['curator']},
                  reference='Invalid grant')['errors'] == ['invalid_profile_correction']
    assert submit(game, 'curator', 'set_profile_visibility', 'hide', target_id='a',
                  visibility='hidden', reference='Pending review')['ok']
    assert not visible(game.project('world'), 'a')
    assert submit(game, 'curator', 'set_profile_visibility', 'archive', target_id='a',
                  visibility='archived', reference='Retired profile')['ok']
    assert submit(game, 'a', 'recall_connection', 'archived', target_id='b', context_id='forum')['errors'] == [
        'archived_actor']
    assert 'a' in game.project('world')['actors']


def test_a_stale_preview_and_unconfirmed_identity_cannot_merge():
    game = start()
    preview = merge_preview(game.project('world'), 'duplicate', 'a')
    assert submit(game, 'curator', 'merge_profiles', 'unconfirmed', source_id='duplicate', target_id='a',
                  reference='Guess', identity_confirmed=False, preview_digest=preview['digest'])['errors'] == [
        'explicit_identity_confirmation_required']
    assert submit(game, 'a', 'recall_connection', 'new', target_id='b', context_id='forum')['ok']
    assert submit(game, 'curator', 'merge_profiles', 'stale', source_id='duplicate', target_id='a',
                  reference='case', identity_confirmed=True, preview_digest=preview['digest'])['errors'] == [
        'merge_preview_stale']


def test_canonical_claim_ownership_and_duplicates_follow_author_and_target_merges():
    game = start()
    assert submit(game, 'duplicate', 'recall_connection', 'alias-claim', target_id='b', context_id='forum')['ok']
    first_id = game.project('relationships')[0]['id']
    preview = merge_preview(game.project('world'), 'duplicate', 'a')
    assert submit(game, 'curator', 'merge_profiles', 'merge-author', source_id='duplicate', target_id='a',
                  reference='Participant identity checked', identity_confirmed=True, preview_digest=preview['digest'])['ok']
    assert submit(game, 'a', 'recall_connection', 'duplicate-current-author', target_id='b', context_id='forum')['errors'] == [
        'duplicate_relationship_claim']
    assert submit(game, 'a', 'retract_relationship_claim', 'canonical-retract', claim_id=first_id)['ok']
    assert submit(game, 'a', 'recall_connection', 'canonical-correct', target_id='b', context_id='forum')['ok']
    assert submit(game, 'b', 'recall_connection', 'target-alias-invalid', target_id='duplicate', context_id='forum')['errors'] == [
        'canonical_target_required']
    # A claim to an old target identity also blocks a fresh duplicate after that target is merged.
    other = start()
    assert submit(other, 'b', 'recall_connection', 'old-target', target_id='duplicate', context_id='forum')['ok']
    target_claim = other.project('relationships')[0]['id']
    preview = merge_preview(other.project('world'), 'duplicate', 'a')
    assert submit(other, 'curator', 'merge_profiles', 'merge-target', source_id='duplicate', target_id='a',
                  reference='Participant identity checked', identity_confirmed=True, preview_digest=preview['digest'])['ok']
    assert submit(other, 'b', 'recall_connection', 'new-target-duplicate', target_id='a', context_id='forum')['errors'] == [
        'duplicate_relationship_claim']
    assert submit(other, 'a', 'dispute_recollection', 'canonical-target-dispute', claim_id=target_claim)['ok']
    assert len(other.project('relationships')) == 1


def test_merge_suppresses_self_links_and_reversal_restores_them_with_attribution():
    game = start()
    assert submit(game, 'duplicate', 'recall_connection', 'first', target_id='a', context_id='forum')['ok']
    assert submit(game, 'a', 'recall_connection', 'second', target_id='duplicate', context_id='forum')['ok']
    prior_edges = game.project('network')['edges']
    preview = merge_preview(game.project('world'), 'duplicate', 'a')
    assert preview['self_links_hidden'] == 2
    assert submit(game, 'curator', 'merge_profiles', 'merge', source_id='duplicate', target_id='a',
                  reference='Verified identity', identity_confirmed=True, preview_digest=preview['digest'])['ok']
    graph = game.project('network')
    assert not graph['edges'] and graph['identity_suppressed_edges']
    merge_id = next(iter(game.project('world')['configuration']['curation']['merges']))
    assert submit(game, 'curator', 'reverse_profile_merge', 'reverse', merge_id=merge_id,
                  reference='Correction from participant')['ok']
    assert game.project('network')['edges'] == prior_edges
