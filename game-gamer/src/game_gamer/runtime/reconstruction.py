"""Actor-owned declarations about an encounter, stored in the existing world."""
from datetime import date

from ..model import require
from .curation import canonical

RECOLLECTION = 'recollection_claim'
PRIOR = 'prior_relationship_claim'
CLAIM_KINDS = {RECOLLECTION, PRIOR}
FIELDS = {
    'recall_connection': ({'target_id', 'context_id'}, {'historical_date', 'note'}),
    'record_prior_relationship': ({'target_id', 'context_id'}, {'historical_date', 'note'}),
    'dispute_recollection': ({'claim_id'}, {'note'}),
    'retract_relationship_claim': ({'claim_id'}, {'note'}),
}


def prepare(world, command, *, actor, timestamp, sequence, action):
    kind = command['kind']
    note = command.get('note', '')
    require(isinstance(note, str) and len(note) <= 1000, 'invalid_claim_note')
    event_ref = f'commit_{sequence:06}'
    if kind in {'dispute_recollection', 'retract_relationship_claim'}:
        claim = world['relationships'].get(command['claim_id'], {})
        require(claim.get('kind') in CLAIM_KINDS, 'unknown_relationship_claim')
        if kind == 'dispute_recollection':
            require(claim['kind'] == RECOLLECTION and claim['status'] == 'claimed', 'claim_not_disputable')
            require(canonical(world, claim['target_id']) == actor, 'recipient_required')
            claim['status'] = 'disputed'
            claim['dispute'] = {'actor_id': actor, 'recorded_at': timestamp, 'note': note}
        else:
            require(canonical(world, claim['source_id']) == actor, 'claim_author_required')
            require(claim['status'] != 'retracted', 'claim_already_retracted')
            claim['status'] = 'retracted'
            claim['retraction'] = {'actor_id': actor, 'recorded_at': timestamp, 'note': note}
        claim['event_refs'].append(event_ref)
    else:
        target = command['target_id']
        require(target != actor and world['actors'].get(target, {}).get('status') == 'active',
                'invalid_claim_target')
        require(world['actors'][actor]['kind'] == world['actors'][target]['kind'] == 'person',
                'person_required')
        context = command['context_id']
        require(isinstance(context, str) and 0 < len(context) <= 128 and context == context.strip(),
                'invalid_claim_context')
        historical_date = command.get('historical_date')
        if historical_date is not None:
            try:
                require(date.fromisoformat(historical_date).isoformat() == historical_date, 'invalid_historical_date')
            except (TypeError, ValueError):
                require(False, 'invalid_historical_date')
        relation_kind = RECOLLECTION if kind == 'recall_connection' else PRIOR
        require(not any(r.get('kind') == relation_kind and r.get('context_id') == context
                        and canonical(world, r['source_id']) == actor and canonical(world, r['target_id']) == target
                        and r['status'] != 'retracted'
                        for r in world['relationships'].values()), 'duplicate_relationship_claim')
        claim_id = f'relationship_claim_{sequence:06}'
        require(not any(claim_id in table for table in world.values()), 'relationship_claim_id_conflict')
        claim = {'id': claim_id, 'kind': relation_kind, 'source_id': actor, 'target_id': target,
                 'context_id': context, 'historical_date': historical_date, 'note': note,
                 'created_by': actor, 'created_at': timestamp, 'status': 'claimed', 'directed': True,
                 'event_refs': [event_ref],
                 'provenance': {'kind': 'player_declaration', 'action_id': action['id']}}
        world['relationships'][claim_id] = claim
    action['target_ids'] = [claim['id'], claim['target_id']]
