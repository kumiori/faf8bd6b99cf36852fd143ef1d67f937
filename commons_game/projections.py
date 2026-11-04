"""Disposable multiplex and incidence projections; no canonical writes."""
from copy import deepcopy
from .model import require
from .presentation import person_labels


def network(world):
    labels=person_labels(world)
    nodes = [{**deepcopy(a), 'kind': a['kind'], **({'display_name':labels[a['id']]} if a['id'] in labels else {})}
             for a in world['actors'].values()]
    edges = [{**deepcopy(r), 'layer': 'invitation' if r['kind'] == 'contact_invitation' else
              'connection' if r['kind'] == 'acknowledged_connection' else 'inferred' if r['status'] == 'inferred' else
              'documented' if r['status'] == 'verified' or r.get('provenance', {}).get('epistemic_status') == 'documented' else 'declared'}
             for r in world['relationships'].values()]
    for record in world['relationships'].values():
        if record['kind'] == 'contact_invitation':
            nodes.append({**deepcopy(record), 'kind': 'invitation'})
    for table, kind in (('resources', 'resource'), ('capacities', 'capacity'), ('needs', 'need'),
                        ('objectives', 'objective'), ('governance', 'policy'), ('evidence', 'evidence')):
        for record in world[table].values():
            nodes.append({**deepcopy(record), 'kind': kind,
                          'label': record.get('label', record.get('domain', record['id']))})

    def link(source, target, kind, **fields):
        edges.append({'id': f'{kind}:{source}:{target}', 'source_id': source, 'target_id': target,
                      'kind': kind, 'layer': 'institutional', **fields})

    for record in world['relationships'].values():
        if record['kind'] == 'contact_invitation':
            for source, target, role in ((record['source_id'], record['id'], 'invitation_sent_by'),
                                         (record['id'], record['target_id'], 'invitation_for')):
                edges.append({'id': f'{role}:{record["id"]}', 'source_id': source, 'target_id': target,
                              'kind': role, 'layer': 'invitation', 'status': record['status'], 'directed': True})

    for table, relation, field in (('resources', 'owned_by', 'owner_id'),
                                   ('capacities', 'declared_by', 'actor_id'),
                                   ('needs', 'expressed_by', 'actor_id')):
        for record in world[table].values():
            if record.get(field):
                link(record['id'], record[field], relation)
    for agreement in world['agreements'].values():
        version = agreement['versions'][agreement['current_version'] - 1]
        nodes.append({**deepcopy(agreement), 'kind': 'agreement'})
        for party in agreement['parties']:
            edges.append({'source_id': party, 'target_id': agreement['id'], 'kind': 'party_to',
                          'layer': 'agreement', 'status': agreement['status']})
        link(agreement['id'], agreement['created_by'], 'proposed_by')
        link(agreement['id'], agreement['objective_id'], 'serves_objective')
        link(agreement['id'], version['policy_id'], 'requires_authorisation')
        for allocation in version['resources']:
            link(agreement['id'], allocation['resource_id'], 'concerns_resource', quantity=allocation['quantity'])
        for evidence_id in agreement['evidence_ids']:
            link(agreement['id'], evidence_id, 'has_evidence')
    for possibility in potential_complementarities(world):
        edges.append({**possibility,'layer':'inferred','directed':True})
    return {'nodes': nodes, 'edges': edges}


def potential_complementarities(world):
    """The existing exact-domain declaration match; never an accepted relation."""
    if 'ecosystem-expertise' in world['configuration']:
        from .expertise import potential_edges
        return list(potential_edges(world))
    return [{'id':f"potential:{capacity['id']}:{need['id']}",'kind':'potential_complementarity',
             'source_id':capacity['actor_id'],'target_id':need['actor_id'],'domain':capacity['domain'],
             'status':'inferred','generator':'exact_domain_match','source_record_ids':[capacity['id'],need['id']]}
            for capacity in world['capacities'].values() for need in world['needs'].values()
            if capacity['domain']==need['domain'] and capacity['unit']==need['unit'] and capacity['unit'] is not None
            and capacity['actor_id']!=need['actor_id'] and capacity['status']==need['status']=='reported']


def neighbourhood(graph, node_id):
    """A disposable view of the existing projection, never another graph store."""
    require(any(n['id'] == node_id for n in graph['nodes']), 'unknown_node')
    edges = [e for e in graph['edges'] if node_id in (e['source_id'], e['target_id'])]
    ids = {node_id} | {e[k] for e in edges for k in ('source_id', 'target_id')}
    return {'nodes': [deepcopy(n) for n in graph['nodes'] if n['id'] in ids], 'edges': deepcopy(edges)}


def contract_registry(world, *, actor=None, status=None, objective=None, resource=None):
    return [deepcopy(a) for a in world['agreements'].values()
            if (actor is None or actor in a['parties']) and (status is None or status == a['status'])
            and (objective is None or objective == a['objective_id'])
            and (resource is None or any(r['resource_id'] == resource
                 for r in a['versions'][a['current_version'] - 1]['resources']))]


def complementarity(offered, needed):
    """B = O∨N; raw directed W = O Nᵀ, with explicit unknown contributions.

    Bounds preserve unknown responses. A known zero multiplied by an unknown
    contributes a known zero. Raw diagonal values are intentionally retained.
    """
    require(isinstance(offered, list) and isinstance(needed, list) and len(offered) == len(needed), 'invalid_matrix_shape')
    width = len(offered[0]) if offered else 0
    require(all(isinstance(row, list) and len(row) == width for row in offered + needed), 'invalid_matrix_shape')
    require(all(value is None or type(value) is int and value in {0, 1} for row in offered + needed for value in row), 'binary_or_missing_required')
    union = [[1 if a == 1 or b == 1 else None if a is None or b is None else 0
              for a, b in zip(o, n)] for o, n in zip(offered, needed)]
    matrix = []
    for row in offered:
        output = []
        for other in needed:
            lower = unknown = 0
            for a, b in zip(row, other):
                if a == 0 or b == 0:
                    continue
                if a is None or b is None:
                    unknown += 1
                else:
                    lower += a * b
            output.append({'value': lower if unknown == 0 else None,
                           'lower': lower, 'upper': lower + unknown, 'missing_terms': unknown})
        matrix.append(output)
    return {'B': union, 'W': matrix, 'interpretation': 'declared_potential_not_agreement'}
