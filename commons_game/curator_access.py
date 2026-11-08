"""Trusted local role setup, outside the player command registry."""
from copy import deepcopy

from game_gamer.runtime.curation import canonical
from .model import require
from .presentation import person_labels


def provision_curator(game, actor_name, *, enabled, reference):
    world = game.get_world()
    require(isinstance(reference, str) and bool(reference.strip()), 'curator_reference_required')
    require(type(enabled) is bool, 'invalid_curator_assignment')
    labels = person_labels(world)
    matches = [actor for ident, actor in world['actors'].items()
               if actor_name == ident or actor_name.casefold() in
               {actor['label'].casefold(), labels.get(ident, '').casefold()}]
    require(len(matches) == 1, 'curator_actor_unknown_or_ambiguous')
    actor = matches[0]
    require(actor['status'] == 'active' and canonical(world, actor['id']) == actor['id'],
            'active_canonical_actor_required')
    require(world['configuration'].get('curation', {}).get('visibility', {}).get(actor['id'], {}).get('value') != 'archived',
            'archived_actor')
    current = 'curator' in actor['roles']
    if current == enabled:
        return {'ok': True, 'changed': False, 'actor_id': actor['id'], 'enabled': enabled}
    after = deepcopy(world)
    roles = after['actors'][actor['id']]['roles']
    if enabled:
        roles.append('curator')
    else:
        roles.remove('curator')
    ident = 'curator-access:'+actor['id']
    audit = after['configuration'].setdefault(ident, {
        'id': ident, 'status': 'recorded', 'actor_id': actor['id'], 'decisions': []})
    audit['decisions'].append({
        'enabled': enabled, 'reference': reference.strip(), 'authority': 'trusted_local_operator',
        'recorded_at': game._timestamp(), 'event_ref': f'commit_{game.revision+1:06}'})
    game._commit(world, after, 'curator.access_granted' if enabled else 'curator.access_revoked')
    return {'ok': True, 'changed': True, 'actor_id': actor['id'], 'enabled': enabled}
