"""Explicit Montréal identity decisions over immutable source observations."""

from collections import defaultdict
from dataclasses import asdict
from difflib import SequenceMatcher

from game_gamer.runtime.curation import canonical, profile, visible

from .model import Actor, require
from .montreal_sources import LAYER, _normalise

FIELDS = {
    'reconcile_source_identity': ({'source_id', 'decision', 'reference'}, {'target_id'}),
}
DECISIONS = ('match', 'create', 'defer', 'reject')


def reviewed_binding(world, source_id):
    dataset = world['configuration'][LAYER]
    return dataset['identities'][source_id]


def notion_identity(world, actor_id):
    remote = world['configuration'].get('profile-sync', {}).get('bindings', {}).get(actor_id)
    if remote:
        return remote
    source = world['actors'][actor_id].get('provenance', {})
    if source.get('kind') == 'notion_snapshot' and source.get('record_id') and source.get('data_source_id'):
        return {key: source[key] for key in ('record_id', 'data_source_id')}
    return None


def candidates(world, dataset, source_id):
    """Rank suggestions without making an identity decision."""
    source_names = {_normalise(name) for name in dataset['names'][source_id]}
    rows = [row['raw'] for row in dataset['statements'] if row['person_id'] == source_id]
    organisations = {_normalise(row['Organisation']) for row in rows if row['Organisation'].strip()}
    affiliations = defaultdict(set)
    for edge in world['relationships'].values():
        if edge['kind'] == 'affiliated_with' and edge['target_id'] in world['actors']:
            affiliations[canonical(world, edge['source_id'])].add(world['actors'][edge['target_id']]['label'])
    aliases = defaultdict(set)
    for other, binding in dataset['identities'].items():
        if binding['actor_id'] and binding.get('method') != 'unique_full_name':
            aliases[canonical(world, binding['actor_id'])].update(dataset['names'][other])
    matches = []
    for actor_id, actor in world['actors'].items():
        if actor['kind'] != 'person' or actor['status'] != 'active' or not visible(world, actor_id):
            continue
        remote = notion_identity(world, actor_id)
        if not remote:
            continue
        curated = profile(world, actor_id)
        names = {_normalise(name) for name in {actor['label'], curated['label'], *aliases[actor_id]}}
        orgs = {curated.get('profile_organisation', ''), *affiliations[actor_id]} - {''}
        organisation_match = bool(organisations & {_normalise(org) for org in orgs})
        similarity = max(SequenceMatcher(None, name, other).ratio() for name in source_names for other in names)
        known_id = actor_id in reviewed_binding(world, source_id).get('candidates', ())
        score = similarity + .3*organisation_match + .6*known_id
        matches.append((score, actor_id, curated['label'], tuple(sorted(orgs)), remote['record_id']))
    return sorted(matches, key=lambda item: (-item[0], item[2].casefold(), item[1]))


def prepare(world, command, *, actor, timestamp, sequence, action):
    require('curator' in world['actors'][actor]['roles'], 'curator_required')
    dataset = world['configuration'].get(LAYER, {})
    source_id, decision = command['source_id'], command['decision']
    require(source_id in dataset.get('identities', {}), 'unknown_source_identity')
    require(decision in DECISIONS, 'invalid_source_decision')
    reference = command['reference']
    require(isinstance(reference, str) and 0 < len(reference.strip()) <= 2000 and reference.isprintable(),
            'curator_reference_required')
    previous = dataset['identities'][source_id]
    require(previous.get('review_status') not in {'matched', 'created', 'rejected'}, 'source_review_is_final')
    require(not previous['actor_id'] or previous.get('method') == 'unique_full_name', 'source_review_is_final')
    target = command.get('target_id')
    require(decision == 'match' or target is None, 'unexpected_related_identity')
    if decision == 'match':
        candidate = world['actors'].get(target, {})
        require(candidate.get('kind') == 'person' and candidate.get('status') == 'active'
                and visible(world, target) and notion_identity(world, target), 'notion_person_required')
        require(not any(other != source_id and binding['actor_id'] and
                        binding.get('method') != 'unique_full_name' and canonical(world, binding['actor_id']) == target
                        for other, binding in dataset['identities'].items()), 'source_actor_already_bound')
    elif decision == 'create':
        target = 'provisional:' + source_id.rsplit(':', 1)[-1]
        require(target not in world['actors'], 'provisional_profile_exists')
        # An exact name only triggers review. It never makes a binding.
        require(not any(_normalise(other['label']) in {_normalise(name) for name in dataset['names'][source_id]}
                        for other in world['actors'].values() if other['kind'] == 'person'), 'possible_duplicate_profile')
        world['actors'][target] = asdict(Actor(id=target, label=dataset['names'][source_id][0],
                                              status='provisional', provenance={'kind': 'curated_provisional',
                                                                               'source_identity_id': source_id}))
    audit = {'actor_id': actor, 'reference': reference.strip(), 'recorded_at': timestamp,
             'event_ref': f'commit_{sequence:06}', 'decision': decision, 'previous_actor_id': previous['actor_id']}
    status = {'match': 'matched', 'create': 'created', 'defer': 'deferred', 'reject': 'rejected'}[decision]
    if decision == 'create':
        from .profile_sync import ledger
        ledger(world)['jobs'][target] = {
            'kind': 'create', 'actor_id': target, 'changes': {'label': world['actors'][target]['label']},
            'approval': audit, 'status': 'pending', 'attempts': [],
        }
    dataset['identities'][source_id] = {**previous, 'actor_id': target, 'method': 'curator_review',
                                        'review_status': status, 'history': [*previous.get('history', ()), audit]}
    action['target_ids'] = [source_id] + ([target] if target else [])
