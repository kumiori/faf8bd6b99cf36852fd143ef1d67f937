"""Auditable review requests in the existing authoritative configuration table."""
from copy import deepcopy

from ..model import require
from .curation import canonical, profile, validate_changes

FIELDS = {
    'request_curation': ({'target_id', 'request_type', 'reason'}, {'related_id', 'proposed_changes'}),
    'review_curation_request': ({'request_id', 'decision', 'reason'}, set()),
    'clarify_curation_request': ({'request_id', 'reason'}, set()),
}
TYPES = {'correction', 'duplicate_merge', 'profile_review'}


def records(world):
    return world['configuration'].get('curation-requests', {}).get('requests', {})


def find_object(world, ident):
    request = records(world).get(ident)
    if request is not None:
        return request
    return next((table[ident] for table in world.values() if ident in table), None)


def prepare(world, command, *, actor, timestamp, sequence, action):
    reason = command['reason']
    require(isinstance(reason, str) and bool(reason.strip()) and len(reason) <= 4000, 'request_reason_required')
    kind = command['kind']
    audit = {'actor_id': actor, 'reason': reason.strip(), 'recorded_at': timestamp,
             'event_ref': f'commit_{sequence:06}', 'action_id': action['id']}
    container = world['configuration'].setdefault('curation-requests', {
        'id': 'curation-requests', 'status': 'active', 'schema_version': 'game-gamer/curation-requests/v1', 'requests': {}})
    requests = container['requests']
    if kind == 'request_curation':
        target = command['target_id']
        require(find_object(world, target) is not None, 'unknown_curation_target')
        request_type = command['request_type']
        require(request_type in TYPES, 'invalid_curation_request_type')
        changes = command.get('proposed_changes', {})
        validate_changes(changes, 'invalid_proposed_correction')
        require(not changes or (request_type == 'correction' and target in world['actors']),
                'profile_correction_target_required')
        related = command.get('related_id')
        if request_type == 'duplicate_merge':
            require(target in world['actors'] and related in world['actors'] and related != target,
                    'merge_request_actors_required')
            require(world['actors'][target]['kind'] == world['actors'][related]['kind'], 'merge_actor_kind_mismatch')
        else:
            require(related is None, 'unexpected_related_identity')
        ident = f'curation_request_{sequence:06}'
        require(find_object(world, ident) is None and ident not in requests, 'curation_request_id_conflict')
        request = {'id': ident, 'kind': 'curation_request', 'request_type': request_type,
                   'requester_id': actor, 'target_id': target, 'related_id': related,
                   'reason': reason.strip(), 'proposed_changes': deepcopy(changes), 'status': 'submitted',
                   'created_at': timestamp, 'history': [{**audit, 'kind': 'submitted'}]}
        if changes:
            before = profile(world, target)
            request['previous_values'] = {field: deepcopy(before.get(field)) for field in changes}
        requests[ident] = request
    else:
        request = requests.get(command['request_id'])
        require(request is not None, 'unknown_curation_request')
        require(request['status'] not in {'approved', 'rejected'}, 'request_review_is_final')
        if kind == 'clarify_curation_request':
            require(canonical(world, request['requester_id']) == actor, 'requester_required')
            require(request['status'] == 'needs_clarification', 'clarification_not_requested')
            request['status'] = 'submitted'
        else:
            require('curator' in world['actors'][actor]['roles'], 'curator_required')
            decision = command['decision']
            require(decision in {'approve', 'reject', 'request_clarification'}, 'invalid_review_decision')
            require(request['status'] == 'submitted', 'request_not_ready_for_review')
            request['status'] = {'approve': 'approved', 'reject': 'rejected',
                                 'request_clarification': 'needs_clarification'}[decision]
        request['history'].append({**audit, 'kind': request['status']})
    action['target_ids'] = [request['id'], request['target_id'], request['requester_id']]
    if request['related_id']:
        action['target_ids'].append(request['related_id'])
