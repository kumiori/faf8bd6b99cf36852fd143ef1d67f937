"""Audited curator decisions and reversible canonical identity mappings."""
from copy import deepcopy
import hashlib
import json

from ..model import require

FIELDS = {
    'correct_profile': ({'target_id', 'changes', 'reference'}, set()),
    'set_profile_visibility': ({'target_id', 'visibility', 'reference'}, set()),
    'merge_profiles': ({'source_id', 'target_id', 'reference', 'identity_confirmed', 'preview_digest'}, set()),
    'reverse_profile_merge': ({'merge_id', 'reference'}, set()),
}


def state(world):
    return world['configuration'].get('curation', {})


def canonical(world, actor_id):
    aliases = state(world).get('aliases', {})
    seen = set()
    while actor_id in aliases:
        require(actor_id not in seen, 'identity_alias_cycle')
        seen.add(actor_id)
        actor_id = aliases[actor_id]
    return actor_id


def visible(world, actor_id):
    return canonical(world, actor_id) == actor_id and state(world).get('visibility', {}).get(actor_id, {}).get('value', 'visible') == 'visible'


def profile(world, actor_id):
    result = deepcopy(world['actors'][actor_id])
    changes = state(world).get('profiles', {}).get(actor_id, {}).get('changes', {})
    result.update(changes)
    visibility = state(world).get('visibility', {}).get(actor_id, {}).get('value', 'visible')
    result['discovery_status'] = visibility
    if visibility == 'archived':
        result['status'] = 'archived'
    return result


def merge_preview(world, source_id, target_id):
    require(source_id in world['actors'] and target_id in world['actors'] and source_id != target_id,
            'invalid_merge_actors')
    source, target = world['actors'][source_id], world['actors'][target_id]
    require(source['kind'] == target['kind'], 'merge_actor_kind_mismatch')
    require(canonical(world, source_id) == source_id and canonical(world, target_id) == target_id,
            'merge_requires_canonical_actors')
    require(source['status'] == target['status'] == 'active', 'inactive_merge_actor')
    blocked = []
    pair = {source_id, target_id}
    if any(a['status'] not in {'rejected', 'withdrawn', 'expired', 'terminated'} and
           a.get('outcome_status') != 'verified' and pair & set(a['parties']) for a in world['agreements'].values()):
        blocked.append('Resolve open agreements before merging their parties.')
    if any(r['owner_id'] in pair for r in world['resources'].values()):
        blocked.append('Resource-owning identities require an explicit ownership migration.')
    if any(r['kind'] in {'contact_invitation', 'invited'} and r['status'] in {'draft', 'sent', 'proposed'}
           and pair & {r['source_id'], r['target_id']} for r in world['relationships'].values()):
        blocked.append('Resolve pending invitations before merging their participants.')
    touched = [r for r in world['relationships'].values() if pair & {r['source_id'], r['target_id']}]
    self_links = sum({r['source_id'], r['target_id']} == pair for r in touched)
    material = {'source_id': source_id, 'target_id': target_id, 'relationships': len(touched),
                'self_links_hidden': self_links, 'blocked': blocked}
    encoded = json.dumps([world, material], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return {**material, 'digest': hashlib.sha256(encoded).hexdigest()}


def prepare(world, command, *, actor, timestamp, sequence, action):
    require('curator' in world['actors'][actor]['roles'], 'curator_required')
    reference = command['reference']
    require(isinstance(reference, str) and bool(reference.strip()) and len(reference) <= 2000,
            'curator_reference_required')
    preview = merge_preview(world, command['source_id'], command['target_id']) if command['kind'] == 'merge_profiles' else None
    config = world['configuration'].setdefault('curation', {
        'id': 'curation', 'status': 'active', 'schema_version': 'game-gamer/curation/v1',
        'aliases': {}, 'merges': {}, 'profiles': {}, 'visibility': {},
    })
    audit = {'actor_id': actor, 'reference': reference, 'recorded_at': timestamp,
             'event_ref': f'commit_{sequence:06}'}
    kind = command['kind']
    if kind == 'reverse_profile_merge':
        merge = config['merges'].get(command['merge_id'])
        require(merge is not None and merge['status'] == 'active', 'active_merge_required')
        source, target = merge['source_id'], merge['target_id']
        require(config['aliases'].get(source) == target and canonical(world, target) == target,
                'reverse_dependent_merge_first')
        del config['aliases'][source]
        merge.update(status='reversed', reversal=audit)
        action['target_ids'] = [source, target]
        return
    target = command['target_id']
    require(target in world['actors'], 'unknown_actor')
    action['target_ids'] = [target]
    if kind == 'correct_profile':
        changes = command['changes']
        require(isinstance(changes, dict) and changes and set(changes) <= {'label', 'motivation', 'profile_role'},
                'invalid_profile_correction')
        require(all(isinstance(value, str) and len(value) <= 4000 for value in changes.values()),
                'invalid_profile_correction')
        require('label' not in changes or bool(changes['label'].strip()), 'invalid_profile_label')
        prior = config['profiles'].get(target, {}).get('changes', {})
        config['profiles'][target] = {'changes': {**prior, **deepcopy(changes)}, **audit}
    elif kind == 'set_profile_visibility':
        require(command['visibility'] in {'visible', 'hidden', 'archived'}, 'invalid_profile_visibility')
        config['visibility'][target] = {'value': command['visibility'], **audit}
    elif kind == 'merge_profiles':
        source = command['source_id']
        require(preview['digest'] == command['preview_digest'], 'merge_preview_stale')
        require(not preview['blocked'], 'merge_has_unresolved_obligations')
        require(command['identity_confirmed'] is True, 'explicit_identity_confirmation_required')
        require('curator' not in world['actors'][source]['roles'], 'curator_identity_merge_forbidden')
        ident = f'merge_{sequence:06}'
        config['aliases'][source] = target
        config['merges'][ident] = {'id': ident, 'source_id': source, 'target_id': target,
                                   'status': 'active', **audit}
        action['target_ids'].append(source)


def resolve_graph(world, graph):
    """Resolve display endpoints while retaining raw IDs and provenance on each observation."""
    if not state(world):
        return graph
    nodes = []
    for node in graph['nodes']:
        if node['kind'] in {'person', 'organisation'}:
            if not visible(world, node['id']):
                continue
            node = {**node, **profile(world, node['id'])}
        nodes.append(node)
    ids = {node['id'] for node in nodes}
    edges, suppressed = [], []
    for edge in graph['edges']:
        source, target = edge['source_id'], edge['target_id']
        resolved_source, resolved_target = canonical(world, source), canonical(world, target)
        if resolved_source == resolved_target and source != target:
            suppressed.append(deepcopy(edge))
            continue
        if resolved_source not in ids or resolved_target not in ids:
            suppressed.append({**deepcopy(edge), 'projection_omission': 'profile_hidden_or_archived'})
            continue
        if (source, target) != (resolved_source, resolved_target):
            edge = {**edge, 'source_id': resolved_source, 'target_id': resolved_target,
                    'original_source_id': source, 'original_target_id': target}
        edges.append(edge)
    return {**graph, 'nodes': nodes, 'edges': edges, 'identity_suppressed_edges': suppressed}
