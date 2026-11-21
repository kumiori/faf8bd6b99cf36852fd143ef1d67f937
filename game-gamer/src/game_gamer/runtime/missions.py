"""Mission contributions use the collective command and evidence history."""

from copy import deepcopy

from ..model import require
from . import curation

CATALOGUE_ID = 'mission-catalogues'
SCHEMA = 'game-gamer/missions/v1'
PROPOSAL_TYPES = ('initiative', 'actor', 'means', 'step')
REVISION_FIELDS = ('need', 'rationale', 'target', 'requirements')
FIELDS = {
    'mission_join': ({'mission_id'}, set()),
    'mission_propose': ({'mission_id', 'proposal_type', 'description'}, {'card_id', 'after_step_id'}),
    'mission_commit': ({'mission_id', 'requirement_id', 'description'},
                       {'recipient_id', 'resource_id', 'quantity', 'proposal_id'}),
    'mission_challenge': ({'mission_id', 'field', 'reason'}, {'replacement'}),
    'mission_explore': ({'mission_id'}, set()),
    'mission_accept': ({'mission_id', 'contribution_id'}, set()),
    'mission_verify': ({'mission_id', 'contribution_id', 'reference'}, set()),
    'mission_revise': ({'mission_id', 'contribution_id'}, set()),
}


def definitions(world):
    return {record['id']: record for record in world['configuration'].values()
            if record.get('kind') == 'mission_definition'}


def contributions(world, mission_id=None):
    return [record for record in world['configuration'].values()
            if record.get('kind') == 'mission_contribution'
            and (mission_id is None or record['mission_id'] == mission_id)]


def members(world, mission_id):
    return list(dict.fromkeys(curation.canonical(world, record['actor_id'])
                             for record in contributions(world, mission_id) if record['type'] == 'join'))


def active_actor(world, actor_id):
    return (world['actors'].get(actor_id, {}).get('status') == 'active'
            and curation.canonical(world, actor_id) == actor_id
            and curation.state(world).get('visibility', {}).get(actor_id, {}).get('value') != 'archived')


def _text(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 4000,
            'mission_text_required')
    return value.strip()


def _proposal(world, command, catalogue, mission_id):
    proposal_type = command['proposal_type']
    require(proposal_type in PROPOSAL_TYPES, 'invalid_mission_proposal_type')
    proposal = {'proposal_type': proposal_type, 'description': _text(command['description'])}
    if 'card_id' in command:
        require(proposal_type in {'actor', 'means'} and
                command['card_id'] in catalogue['catalogues'][proposal_type], 'unknown_mission_card')
        proposal['card_id'] = command['card_id']
    if 'after_step_id' in command:
        step = world['configuration'].get(command['after_step_id'], {})
        require(proposal_type == 'step' and step.get('mission_id') == mission_id
                and step.get('proposal_type') == 'step', 'invalid_mission_predecessor')
        proposal['after_step_id'] = step['id']
    return proposal


def _offer(world, command, mission, actor):
    requirement_id = command['requirement_id']
    require(requirement_id in mission['requirements'], 'unknown_mission_requirement')
    offer = {'requirement_id': requirement_id, 'description': _text(command['description'])}
    if 'recipient_id' in command:
        recipient = command['recipient_id']
        require(recipient != actor and active_actor(world, recipient), 'invalid_mission_recipient')
        offer['recipient_id'] = recipient
    if 'resource_id' in command:
        resource = world['resources'].get(command['resource_id'], {})
        require('recipient_id' in offer, 'mission_resource_recipient_required')
        require(resource.get('owner_id') == actor, 'mission_resource_owner_required')
        quantity = command.get('quantity')
        require(type(quantity) is int and 0 < quantity <= resource['quantity'], 'invalid_quantity')
        offer.update(resource_id=resource['id'], quantity=quantity)
    else:
        require('quantity' not in command, 'invalid_quantity')
    if 'proposal_id' in command:
        step = world['configuration'].get(command['proposal_id'], {})
        require(step.get('mission_id') == mission['id'] and step.get('proposal_type') == 'step',
                'invalid_mission_step')
        offer['proposal_id'] = step['id']
    return offer


def _challenge(command, catalogue, mission):
    field = command['field']
    require(field in REVISION_FIELDS, 'invalid_mission_revision_field')
    challenge = {'field': field, 'reason': _text(command['reason'])}
    if 'replacement' in command:
        replacement = command['replacement']
        if field == 'requirements':
            require(isinstance(replacement, list) and replacement and
                    len(set(replacement)) == len(replacement) and
                    set(replacement) <= catalogue['requirements'].keys(), 'invalid_mission_requirements')
        else:
            replacement = _text(replacement)
        require(replacement != mission[field], 'unchanged_mission_revision')
        challenge['replacement'] = replacement
    return challenge


def _review(world, command, mission, actor, audit, action):
    record = world['configuration'].get(command['contribution_id'], {})
    require(record.get('kind') == 'mission_contribution' and record['mission_id'] == mission['id'],
            'unknown_mission_contribution')
    kind = command['kind']
    author = curation.canonical(world, record['actor_id'])
    recipient = curation.canonical(world, record['recipient_id']) if 'recipient_id' in record else None
    roles = world['actors'][actor]['roles']
    if kind == 'mission_accept':
        require(record['type'] == 'commit' and record['status'] == 'offered', 'pending_mission_offer_required')
        require(actor == recipient and actor != author, 'mission_recipient_required')
        record['status'] = 'accepted'
    elif kind == 'mission_verify':
        require(record['type'] == 'commit' and record['status'] in {'pledged', 'accepted'},
                'reviewable_mission_offer_required')
        require('verifier' in roles and actor not in {author, recipient}, 'independent_mission_verifier_required')
        reference = _text(command['reference'])
        evidence_id = 'evidence_' + audit['event_ref'].removeprefix('commit_')
        applicable = [ident for ident, definition in definitions(world).items()
                      if record['requirement_id'] in definition['requirements']]
        world['evidence'][evidence_id] = {
            'id': evidence_id, 'kind': 'mission_verification', 'status': 'verified',
            'requirement_id': record['requirement_id'], 'reference': reference, 'mission_ids': applicable,
            'mission_id': mission['id'], 'contribution_id': record['id'],
            'submitted_by': actor, 'submitted_at': audit['recorded_at'], 'action_id': action['id'],
            'provenance': {'kind': 'synthetic_gameplay'},
        }
        record.update(status='verified', evidence_id=evidence_id)
        action['target_ids'].append(evidence_id)
    else:
        require(record['type'] == 'challenge' and record['status'] == 'submitted' and 'replacement' in record,
                'pending_mission_revision_required')
        require('curator' in roles and actor != author, 'independent_mission_curator_required')
        require(record['mission_version'] == mission['version'], 'mission_version_conflict')
        mission[record['field']] = deepcopy(record['replacement'])
        mission['version'] += 1
        mission['revision_ref'] = audit['event_ref']
        record['status'] = 'applied'
    if kind == 'mission_accept':
        action['mission_ids'] = [ident for ident, definition in definitions(world).items()
                                 if record['requirement_id'] in definition['requirements']]
    record[record['status'] + '_by'] = audit
    action['target_ids'].append(record['id'])


def prepare(world, command, *, actor, timestamp, sequence, action):
    mission_id = command['mission_id']
    mission = definitions(world).get(mission_id)
    catalogue = world['configuration'].get(CATALOGUE_ID, {})
    require(catalogue.get('schema') == SCHEMA, 'unsupported_mission_catalogue')
    require(mission is not None and mission['status'] == 'open', 'open_mission_required')
    kind = command['kind']
    action['target_ids'] = [mission_id]
    audit = {'actor_id': actor, 'recorded_at': timestamp, 'event_ref': f'commit_{sequence:06}',
             'action_id': action['id']}
    if kind == 'mission_explore':
        return
    if kind in {'mission_accept', 'mission_verify', 'mission_revise'}:
        _review(world, command, mission, actor, audit, action)
        return
    joined = actor in members(world, mission_id)
    if kind == 'mission_join':
        require(not joined, 'already_joined_mission')
        status, details = 'joined', {}
    else:
        require(joined, 'join_mission_first')
        if kind == 'mission_propose':
            status, details = 'proposed', _proposal(world, command, catalogue, mission_id)
        elif kind == 'mission_challenge':
            status, details = 'submitted', _challenge(command, catalogue, mission)
        else:
            details = _offer(world, command, mission, actor)
            status = 'offered' if 'recipient_id' in details else 'pledged'
    ident = f'mission_contribution_{sequence:06}'
    world['configuration'][ident] = {
        'id': ident, 'kind': 'mission_contribution', 'type': kind.removeprefix('mission_'),
        'mission_id': mission_id, 'mission_version': mission['version'], 'status': status,
        'provenance': {'kind': 'player_contribution'}, **audit, **details,
    }
    action['target_ids'].append(ident)
