"""Disposable multiplex and incidence projections; no canonical writes."""
from copy import deepcopy
from .model import require


def network(world):
    nodes = [{'id': a['id'], 'label': a['label'], 'kind': a['kind']} for a in world['actors'].values()]
    edges = [{**deepcopy(r), 'layer': 'documented' if r['status'] == 'verified' else 'declared'}
             for r in world['relationships'].values()]
    for agreement in world['agreements'].values():
        nodes.append({'id': agreement['id'], 'label': agreement['label'], 'kind': 'agreement', 'status': agreement['status']})
        for party in agreement['parties']:
            edges.append({'source_id': party, 'target_id': agreement['id'], 'kind': 'party_to',
                          'layer': 'agreement', 'status': agreement['status']})
    return {'nodes': nodes, 'edges': edges}


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
