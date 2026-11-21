"""Deterministic, read-only decision inspection. No terminal dependencies required."""
from copy import deepcopy
import hashlib
import json

from .engine import extract_engine
from .interfaces import COMMONS, TERMINAL, InterfaceAdapter, extract_interface

SCHEMA_VERSION = '0.1.0'


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def fingerprint(graph):
    """Coverage is applicable only to exactly the inspected implementation."""
    material = deepcopy(graph)
    material.pop('context', None)
    material.pop('coverage', None)
    material.pop('implementation_digest', None)
    material.pop('verification',None)
    for collection in ('nodes', 'edges'):
        for row in material[collection]:
            for key in ('test_refs', 'coverage_status', 'availability', 'contextual_choices','observed_outcomes','verification_checks'):
                row.pop(key, None)
    return hashlib.sha256(canonical_json(material).encode()).hexdigest()


def extract_decisions(*, interfaces='auto', adapters=(), collective=None, binding=None,
                      limit=100, coverage=None, scope=None, level=None, transition_evidence=None):
    """Project runtime registry and registered interface sources into detached JSON data.

    ``interfaces``: auto, terminal, commons, none. ``adapters`` adds source-only
    InterfaceAdapter registrations. Context requires both a collective and binding.
    """
    if interfaces not in {'auto', 'terminal', 'commons', 'none'}:
        raise ValueError('unknown_interface: ' + interfaces)
    if type(limit) is not int or limit < 0:
        raise ValueError('invalid_choice_limit')
    if scope in {'exercise.reconstruct','reconstruction'}:
        from .contracts import contract_graph, reconstruction_registry
        if interfaces == 'none':
            raise ValueError('reconstruction_contract_requires_commons_interface')
        graph = contract_graph(reconstruction_registry(),evidence=transition_evidence)
        if collective is not None or binding is not None:
            if collective is None or binding is None:
                raise ValueError('context_requires_collective_and_binding')
            contextualise(graph,collective,binding,limit)
        if level:
            graph = select_scope(graph,level=level)
        return graph
    nodes, edges = extract_engine()
    graph = {'schema_version': SCHEMA_VERSION, 'graph_type': 'decision',
             'levels': ['navigation', 'decision', 'state'], 'mode': 'structural',
             'nodes': nodes, 'edges': edges, 'diagnostics': [], 'interfaces': []}
    selected = ([TERMINAL] if interfaces in {'auto', 'terminal', 'commons'} else [])
    if interfaces in {'auto', 'commons'}:
        from importlib.util import find_spec
        if find_spec('commons_game'):
            selected.append(COMMONS)
        elif interfaces == 'commons':
            raise ValueError('interface_unavailable: commons')
    available = []
    for adapter in [*selected, *adapters]:
        try:
            # Probe source availability before combining the registered call graph.
            from .source import load
            for module in adapter.modules:
                load(module)
        except (ImportError, ValueError, OSError) as error:
            graph['interfaces'].append({'id': adapter.id, 'status': 'unavailable', 'reason': str(error)})
            graph['diagnostics'].append({'severity': 'WARNING', 'code': 'interface_unavailable',
                                         'reason': adapter.id + ': ' + str(error)})
        else:
            available.append(adapter)
            graph['interfaces'].append({'id': adapter.id, 'status': 'source_adapter',
                                         'modules': list(adapter.modules), 'complete': False})
            graph['diagnostics'].append({'severity': 'WARNING', 'code': 'source_adapter_incomplete',
                                         'reason': adapter.id + ': imperative option handlers may be unresolved; see per-edge diagnostics.'})
    if available:
        has_commons=any(adapter.id=='commons' for adapter in available)
        owned={'commons_game.reconstruction','commons_game.reconstruction_filters',
               'game_gamer.tui.reconstruction','game_gamer.tui.opening'} if has_commons else set()
        combined = InterfaceAdapter('registered', tuple(sorted({m for a in available for m in a.modules})),
                                    tuple(sorted({f for a in available for f in a.entry_functions})))
        ns, es, diagnostics = extract_interface(combined)
        if owned:
            owned_ids={n['id'] for n in ns if n.get('source',{}).get('module') in owned or
                       (n.get('source',{}).get('module')=='commons_game.exercises' and
                        n['source']['function']=='exercise_menu')}
            ns=[n for n in ns if n['id'] not in owned_ids]
            dropped={e['id'] for e in es if e['source'] in owned_ids or e.get('target') in owned_ids}
            es=[e for e in es if e['id'] not in dropped]
            diagnostics=[d for d in diagnostics if d.get('node_id') not in owned_ids and d.get('edge_id') not in dropped]
        nodes.extend(ns); edges.extend(es)
        graph['diagnostics'].extend(diagnostics)
        if has_commons:
            from .contracts import contract_graph,reconstruction_registry
            declared=contract_graph(reconstruction_registry(),evidence=transition_evidence)
            existing={n['id'] for n in nodes}
            by_id={n['id']:n for n in nodes}
            for node in declared['nodes']:
                if node['id'] in by_id and node.get('ui_transition_ids'):
                    by_id[node['id']]['ui_transition_ids']=node['ui_transition_ids']
            nodes.extend(n for n in declared['nodes'] if n['id'] not in existing)
            edges.extend(declared['edges'])
            graph['contract']=declared['contract']
            graph['limitations']=declared['limitations']+['Source-only adapters remain uncertain outside the declared scope.']
            graph['verification']=declared['verification']
            graph['interfaces'].append(declared['interfaces'][0])
    from importlib.util import find_spec
    from pathlib import Path
    source_modules = {'game_gamer.runtime.' + name for name in
                      ('engine', 'actions', 'governance', 'invitations', 'curation', 'curation_requests', 'reconstruction', 'runner', 'transactions', 'missions', 'mission_lifecycle')}
    source_modules.add('game_gamer.extensions')
    source_modules |= {m for a in available for m in a.modules}
    if graph.get('contract'):
        source_modules |= set(reconstruction_registry().dependency_modules)
        source_modules |= {d['source']['module'] for d in graph['contract']['definitions']}
    graph['sources'] = [{'module': module, 'sha256': hashlib.sha256(Path(find_spec(module).origin).read_bytes()).hexdigest()}
                        for module in sorted(source_modules)]
    if not selected and not adapters:
        graph['diagnostics'].append({'severity': 'WARNING', 'code': 'navigation_unavailable',
                                     'reason': 'No interface selected; terminal navigation coverage is unavailable.'})
    # Merge shared registrations by stable identity. Conflicting adapters are an error.
    for collection in ('nodes', 'edges'):
        unique = {}
        for row in graph[collection]:
            row.setdefault('extraction_status','engine_definition' if row['id'].startswith('engine.') else 'source_only')
            if row['extraction_status']=='source_only':row.setdefault('transition_id',None)
            if row['id'] in unique and unique[row['id']] != row:
                raise ValueError('conflicting_graph_id: ' + row['id'])
            unique[row['id']] = row
        graph[collection] = sorted(unique.values(), key=lambda item: item['id'])
    graph['implementation_digest'] = fingerprint(graph)
    if coverage is not None:
        apply_coverage(graph, coverage)
    if collective is not None or binding is not None:
        if collective is None or binding is None:
            raise ValueError('context_requires_collective_and_binding')
        contextualise(graph, collective, binding, limit)
    if scope or level:
        graph = select_scope(graph, scope=scope, level=level)
    return graph


def contextualise(graph, collective, binding, limit):
    """Use actual validated candidates; missing input remains unknown, never allowed.

    Contextual export deliberately contains engine definitions and candidate IDs
    only. Developer UI source/curator navigation and private profile data are not
    included. Source-level structural inspection is a local developer API.
    """
    from ..runtime.curation import canonical, state, visible
    from ..runtime.runner import Collective
    collective = Collective.from_history(collective.history())
    world = collective.project('world')
    actor = world['actors'].get(binding.actor_id, {})
    # Enforce the same binding validation as the player-facing API.
    options = collective.action_options(binding=binding)
    privileged = {'correct_profile', 'set_profile_visibility', 'merge_profiles', 'reverse_profile_merge'}
    allowed_kinds = {row['action_id'] for row in graph['nodes'] if row['kind'] == 'action'}
    if 'curator' not in actor.get('roles', []):
        allowed_kinds -= privileged
    graph['nodes'] = [row for row in graph['nodes'] if row['id'].split('.')[0] == 'engine'
                      and row['id'].split('.')[1] in allowed_kinds]
    ids = {row['id'] for row in graph['nodes']}
    graph['edges'] = [e for e in graph['edges'] if e['source'] in ids and e['target'] in ids]
    graph['diagnostics'] = [d for d in graph['diagnostics'] if not d.get('edge_id') and not d.get('node_id')]
    graph['mode'] = 'contextual'
    graph.pop('contract',None)
    graph['verification']={'status':'contextual_engine_availability','complete_application_verified':False}
    graph['context'] = {'scope_id': collective.scope_id, 'actor_id': binding.actor_id,
                        'revision': options['revision'], 'choice_limit': limit,
                        'interface_navigation': 'developer_source_omitted'}
    # Targets that are explicitly hidden must not appear even as disabled choices.
    hidden = {key for key in world['actors'] if not visible(world, key)} - {binding.actor_id}
    grouped = {}
    for option in options['options']:
        candidate = option['action']
        target = candidate.get('agreement_id') or candidate.get('invitation_id')
        record = world['agreements'].get(target) or world['relationships'].get(target) or {}
        participants = set(record.get('parties', [])) | {record.get('source_id'), record.get('target_id')}
        if participants & hidden:
            continue
        grouped.setdefault(candidate['kind'], []).append({'action': candidate,
            'status': 'disabled' if option['errors'] else 'enabled', 'reasons': option['errors']})
    for row in graph['nodes']:
        if row['kind'] != 'action':
            continue
        candidates = sorted(grouped.get(row['action_id'], []), key=canonical_json)
        if candidates:
            enabled = any(c['status'] == 'enabled' for c in candidates)
            row['availability'] = {'status': 'enabled' if enabled else 'disabled',
                                   'reasons': [] if enabled else sorted({e for c in candidates for e in c['reasons']}),
                                   'basis': 'validated_existing_targets'}
        else:
            reasons = ['input_required']
            status = 'unknown'
            if canonical(world, binding.actor_id) != binding.actor_id:
                status, reasons = 'disabled', ['canonical_identity_required']
            elif state(world).get('visibility', {}).get(binding.actor_id, {}).get('value') == 'archived':
                status, reasons = 'disabled', ['archived_actor']
            row['availability'] = {'status': status, 'reasons': reasons}
        # Resolve unconditional, data-independent permission guards against this
        # actor without inventing payload values. Version/target guards remain
        # unknown until there is an actual candidate to validate.
        denied = []
        for guard in row.get('permissions', []):
            if guard['when'] or guard.get('validator') != 'require':
                continue
            if evaluate_permission(guard['condition'], world, binding.actor_id) is False:
                denied.append(guard['reason'])
        if denied:
            row['availability'] = {'status': 'disabled', 'reasons': sorted(set(denied)),
                                   'basis': 'implemented_permission_guards'}
        row['contextual_choices'] = {'items': candidates[:limit], 'total': len(candidates),
                                     'truncated': len(candidates) > limit}
    availability = {n['action_id']: n['availability'] for n in graph['nodes'] if n['kind'] == 'action'}
    for e in graph['edges']:
        e['availability'] = deepcopy(availability[e['action_id']])


def evaluate_permission(expression, world, actor):
    """Evaluate a deliberately small, non-executing subset of guard expressions."""
    import ast
    def value(node):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Name) and node.id in {'actor', 'world'}:
            return {'actor': actor, 'world': world}[node.id]
        if isinstance(node, ast.Subscript): return value(node.value)[value(node.slice)]
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)): return [value(n) for n in node.elts]
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = value(node.left), value(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.In): return left in right
            if isinstance(op, ast.NotIn): return left not in right
            if isinstance(op, ast.Eq): return left == right
            if isinstance(op, ast.NotEq): return left != right
        if isinstance(node, ast.BoolOp):
            values = [value(n) for n in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        raise ValueError('unresolved')
    try:
        return value(ast.parse(expression, mode='eval').body)
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def apply_coverage(graph, document):
    if document.get('schema_version') != SCHEMA_VERSION or document.get('implementation_digest') != graph['implementation_digest']:
        raise ValueError('incompatible_or_stale_decision_coverage')
    known = {e['id'] for e in graph['edges']}
    if set(document.get('transitions', {})) - known:
        raise ValueError('unknown_coverage_transition')
    for edge in graph['edges']:
        if edge.get('instrumentation')=='registered_handler':
            continue
        refs = sorted(set(document.get('transitions', {}).get(edge['id'], [])))
        edge['test_refs'] = refs
        if refs:
            edge['coverage_status'] = 'covered'
    graph['coverage'] = {'source': 'observed_execution', 'implementation_digest': document['implementation_digest']}


def select_scope(graph, *, scope=None, level=None):
    result = deepcopy(graph)
    selected = {n['id'] for n in result['nodes'] if (not scope or n['scope'] == scope or n['id'].startswith(scope))
                and (not level or n['level'] == level)}
    def in_scope(edge):
        return not scope or edge['scope'] == scope or edge['source'].startswith(scope) or (edge.get('target') or '').startswith(scope)
    edges = [e for e in result['edges'] if
             (e['source'] in selected or e.get('target') in selected or (level == 'decision' and in_scope(e)))
             and (not level or e['level'] == level)]
    selected |= {ident for e in edges for ident in (e['source'], e.get('target')) if ident}
    result['nodes'] = [n for n in result['nodes'] if n['id'] in selected]
    result['edges'] = edges
    edge_ids = {e['id'] for e in edges}
    result['diagnostics'] = [d for d in result['diagnostics'] if
        (not d.get('node_id') or d['node_id'] in selected) and (not d.get('edge_id') or d['edge_id'] in edge_ids)]
    result['selection'] = {'scope': scope, 'level': level, 'includes_boundary_nodes': True}
    return result


__all__ = ['InterfaceAdapter', 'extract_decisions', 'canonical_json']
