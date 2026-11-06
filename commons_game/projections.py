"""Host labels and Montréal's questionnaire-specific projections."""
from game_gamer.projections.network import contract_registry as contract_registry
from game_gamer.projections.network import neighbourhood as neighbourhood
from game_gamer.projections.network import network as project_network
from game_gamer.projections.network import potential_complementarities as exact_domain_matches
from .model import require
from .presentation import person_labels


def network(world):
    graph = project_network(world, possibilities=potential_complementarities(world))
    labels = person_labels(world)
    for node in graph['nodes']:
        if node['kind'] == 'person' and node['id'] in labels:
            node['display_name'] = labels[node['id']]
    return graph


def potential_complementarities(world):
    if 'ecosystem-expertise' in world['configuration']:
        from .expertise import potential_edges
        return list(potential_edges(world))
    return exact_domain_matches(world)


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
