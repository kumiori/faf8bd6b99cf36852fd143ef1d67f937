"""Rebuild relationship interpretations from attributed records."""
from copy import deepcopy
import json
from collections import defaultdict

from ..runtime.reconstruction import PRIOR, RECOLLECTION


def reconstruction_edges(world, *, context_id=None):
    edges = []
    pairs = defaultdict(list)
    for record in world['relationships'].values():
        kind = record['kind']
        if kind not in {PRIOR, RECOLLECTION} or record['status'] == 'retracted':
            continue
        if context_id is not None and record['context_id'] != context_id:
            continue
        if kind == PRIOR:
            edges.append({**deepcopy(record), 'layer': 'prior_relationship'})
        else:
            a, b = sorted((record['source_id'], record['target_id']))
            pairs[(record['context_id'], a, b)].append(record)
    for key, claims in pairs.items():
        context, a, b = key
        if len(claims) == 2 and all(r['status'] == 'claimed' for r in claims):
            edges.append({
                'id': 'corroborated:' + json.dumps(key, separators=(',', ':')),
                'kind': 'corroborated_recollection', 'layer': 'corroborated', 'context_id': context,
                'source_id': a, 'target_id': b, 'directed': False, 'status': 'corroborated',
                'claim_ids': sorted(r['id'] for r in claims),
                'event_refs': sorted({event for r in claims for event in r['event_refs']}),
                'provenance': {'kind': 'derived_mutual_recollection'},
            })
        else:
            edges.extend({**deepcopy(r), 'layer': 'disputed_recollection' if r['status'] == 'disputed'
                          else 'recollection'} for r in claims)
    for evidence in world['evidence'].values():
        if evidence['kind'] == 'whiteboard_connection' and (
                context_id is None or evidence['context_id'] == context_id):
            edges.append({**deepcopy(evidence), 'id': 'historical:'+evidence['id'],
                          'evidence_id': evidence['id'], 'layer': 'historical_whiteboard'})
    return edges


RECONSTRUCTION_LAYERS = ('historical_whiteboard', 'recollection', 'corroborated', 'disputed_recollection',
                         'prior_relationship', 'invitation', 'connection', 'inferred')


def exercise_graph(graph, *, context_id, actor_ids):
    """Keep actor-to-actor observations and the full roster, including unlinked actors."""
    agreements = {node['id'] for node in graph['nodes'] if node['kind'] == 'agreement'
                  and set(node['parties']) & set(actor_ids)}
    ids = set(actor_ids) | agreements
    edges = []
    for edge in graph['edges']:
        if edge['source_id'] not in ids or edge['target_id'] not in ids:
            continue
        if edge.get('context_id', context_id) != context_id:
            continue
        layer = edge['layer']
        if layer == 'invitation' and edge['status'] != 'sent':
            continue
        if layer not in RECONSTRUCTION_LAYERS and layer not in {'declared', 'documented', 'agreement'}:
            continue
        group = ('reconstruction' if layer in {'historical_whiteboard', 'recollection', 'corroborated', 'disputed_recollection'}
                 else 'invitations' if layer in {'invitation', 'connection'}
                 else 'potential' if layer == 'inferred' else 'contracts' if layer == 'agreement' else 'existing')
        edges.append({**edge, 'directed': True if layer == 'agreement' else edge.get('directed'),
                      'graph_identity': context_id if group == 'reconstruction' else 'world',
                      'display_group': group,
                      'source_record_ids': edge.get('source_record_ids') or edge.get('claim_ids') or
                      [edge.get('evidence_id') or edge.get('id') or
                       (edge['target_id'] if layer == 'agreement' else edge['source_id'])]})
    return {'nodes': [node for node in graph['nodes'] if node['id'] in ids], 'edges': edges}



def reconstruction_counts(world, graph, *, context_id, actor_id):
    from ..runtime.curation import canonical
    ids = {node['id'] for node in graph['nodes']}
    claims = [r for r in world['relationships'].values() if r['kind'] == RECOLLECTION
              and r['context_id'] == context_id and r['status'] != 'retracted'
              and {canonical(world, r['source_id']), canonical(world, r['target_id'])} <= ids
              and canonical(world, r['source_id']) != canonical(world, r['target_id'])]
    pairs = {frozenset((canonical(world, r['source_id']), canonical(world, r['target_id']))) for r in claims}
    disputed = {frozenset((canonical(world, r['source_id']), canonical(world, r['target_id']))) for r in claims if r['status'] == 'disputed'}
    layers = [edge['layer'] for edge in graph['edges']]
    corroborated = layers.count('corroborated')
    return {'participants': sum(node['kind'] == 'person' for node in graph['nodes']),
            'pairs': len(pairs), 'claims': len(claims), 'corroborated': corroborated,
            'unilateral': max(0, len(pairs) - len(disputed) - corroborated), 'disputed': len(disputed),
            'contributors': len({canonical(world, r['source_id']) for r in claims}),
            'own': sum(canonical(world, r['source_id']) == actor_id for r in claims), 'invitations': layers.count('invitation'),
            'accepted_connections': layers.count('connection')}
