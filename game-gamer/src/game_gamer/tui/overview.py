"""Fit an entire actor graph into a terminal-sized read-only overview."""

from collections import Counter, deque
from dataclasses import dataclass

from .network import LAYERS
from .objects import OBJECTS
from .visual import NAVIGATION, SECONDARY


@dataclass
class NetworkScope:
    nodes: dict
    edges: list
    components: list
    isolates: list


def select_scope(graph, centre, scope, *, actor_type=None):
    """Community means weak connectivity in the selected actor/edge layers."""
    nodes = {node['id']: node for node in graph['nodes']
             if actor_type is None or node['kind'] == actor_type}
    neighbours = {key: set() for key in nodes}
    edges = [edge for edge in graph['edges']
             if edge['source_id'] in nodes and edge['target_id'] in nodes]
    for edge in edges:
        source, target = edge['source_id'], edge['target_id']
        if source != target:
            neighbours[source].add(target)
            neighbours[target].add(source)
    if scope == 'local':
        keys = ({centre} | neighbours[centre]) if centre in nodes else set()
    elif scope == 'community':
        keys = set(_walk(neighbours, centre)) if centre in nodes else set()
    else:
        keys = set(nodes)
    if scope != 'global':
        nodes = {key: node for key, node in nodes.items() if key in keys}
        edges = [edge for edge in edges if edge['source_id'] in keys and edge['target_id'] in keys]
    isolates = sorted(key for key in keys if not neighbours[key] & keys)
    remaining = keys - set(isolates)
    components = []
    for root in sorted(remaining, key=lambda key: (-len(neighbours[key]), key)):
        if root in remaining:
            component = _walk(neighbours, root, remaining)
            components.append(component)
            remaining.difference_update(component)
    components.sort(key=lambda group: (-len(group), group[0]))
    return NetworkScope(nodes, edges, components, isolates)


def _walk(neighbours, root, allowed=None):
    seen = {root}
    pending = deque([root])
    ordered = []
    while pending:
        key = pending.popleft()
        ordered.append(key)
        for other in sorted(neighbours[key] - seen):
            if allowed is None or other in allowed:
                seen.add(other)
                pending.append(other)
    return ordered


def overview(scope, width, height, *, selected=None):
    """Allocate overview slots to components, grouping adjacent traversal rows.

    Every actor belongs to exactly one slot. Cross-slot edges retain their
    layer and count. Internal edges contribute to the reported total.
    """
    columns, rows = max(1, width//8), max(1, height//3)
    budget = columns*rows
    isolates = set(scope.isolates)
    groups = [*scope.components, *([scope.isolates] if scope.isolates else [])]
    if len(groups) > budget:
        groups = [*groups[:budget-1], [key for group in groups[budget-1:] for key in group]]
    slots = [1]*len(groups)
    for _ in range(len(groups), min(budget, len(scope.nodes))):
        index = max(range(len(groups)), key=lambda i: len(groups[i])/slots[i])
        slots[index] += 1

    nodes, membership = [], {}
    for group, count in zip(groups, slots):
        for i in range(count):
            members = group[i*len(group)//count:(i+1)*len(group)//count]
            key = members[0]
            node = scope.nodes[key]
            style = OBJECTS.get(node['kind'], OBJECTS['evidence'])
            aggregated = len(members) > 1
            isolated = all(member in isolates for member in members)
            if isolated:
                symbol = '◌' if aggregated else '∘'
            elif aggregated:
                symbol = '◆'
            else:
                symbol = '■' if node['kind'] == 'organisation' else style.symbol
            ascii_symbol = '+' if aggregated else 'o' if isolated else style.plain[1]
            row, column = divmod(len(nodes), columns)
            nodes.append({**node, 'visual_id': key, 'position': (column, -row, 0),
                          'entity_type': node['kind'], 'symbol': symbol, 'ascii_symbol': ascii_symbol,
                          'colour': SECONDARY if isolated else NAVIGATION,
                          'member_count': len(members)})
            membership.update(dict.fromkeys(members, key))

    bundles = Counter()
    singletons = {node['id'] for node in nodes if node['member_count'] == 1}
    for edge in scope.edges:
        a, b = membership[edge['source_id']], membership[edge['target_id']]
        if a != b:
            directed = edge.get('directed') if {a, b} <= singletons else False
            if not directed:
                a, b = sorted((a, b))
            bundles[a, b, edge['layer'], directed] += 1
    edges = []
    for (a, b, layer, directed), count in bundles.items():
        colour, pattern = LAYERS.get(layer, (SECONDARY, 'solid'))
        edges.append({'id': (a, b, layer), 'visual_source': a, 'visual_target': b,
                      'layer': layer, 'weight': count, 'pattern': pattern, 'colour': colour,
                      'directed': directed, 'unknown_marker': directed is None,
                      'directed': False})
    return {'nodes': nodes, 'edges': edges, 'centre': membership.get(selected)}
