"""Reconcile graph diagnostics without turning extraction uncertainty into defects."""
from collections import Counter, defaultdict
import hashlib
from importlib.util import find_spec
from pathlib import Path

CATEGORIES = ('unmapped_option', 'missing_recovery', 'untested_transition', 'uninstrumented_transition')


def diagnostic_inventory(graph, report):
    nodes = {node['id']: node for node in graph['nodes']}
    edges = {edge['id']: edge for edge in graph['edges']}
    incoming = defaultdict(list)
    for edge in edges.values():
        incoming[edge.get('target')].append(edge)
    source_hashes = {s['module']: s['sha256'] for s in graph.get('sources', [])}
    findings = [dict(f) for f in report['findings'] if f['code'] in CATEGORIES]
    # The original report counted these but did not emit their individual rows.
    for edge in edges.values():
        if (edge.get('declared_option') or edge.get('kind') == 'action') and not edge.get('instrumentation') and not any(
                f['code']=='uninstrumented_transition' and f.get('edge_id')==edge['id'] for f in findings):
            findings.append({'severity': 'WARNING', 'code': 'uninstrumented_transition', 'edge_id': edge['id'],
                             'reason': 'No registered execution observer exists for this transition.'})
    rows = []
    for finding in findings:
        category = finding['code']
        edge = edges.get(finding.get('edge_id'))
        node = nodes.get(finding.get('node_id') or (edge or {}).get('source'), {})
        location = (edge or {}).get('source_code') or node.get('source')
        module = (location or {}).get('module')
        source_file = None
        matches_snapshot = None
        if module:
            try:
                spec = find_spec(module)
            except (ImportError, ValueError, AttributeError):
                spec = None
            if spec and spec.origin and Path(spec.origin).is_file():
                source_file = spec.origin
                if module in source_hashes:
                    matches_snapshot = hashlib.sha256(Path(source_file).read_bytes()).hexdigest() == source_hashes[module]
        question_id = node['id'] if node.get('kind') == 'question' else None
        screen_id = node['id'] if node.get('kind') == 'screen' else None
        if question_id:
            screens = {e['source'] for e in incoming[question_id] if nodes.get(e['source'], {}).get('kind') == 'screen'}
            if len(screens) == 1:
                screen_id = next(iter(screens))
        root, classification = root_cause(category, edge, node)
        subject = finding.get('edge_id') or finding.get('node_id')
        diagnostic_id = category + ':' + hashlib.sha256(subject.encode()).hexdigest()[:16]
        rows.append({'diagnostic_id': diagnostic_id, 'severity': finding['severity'], 'category': category,
                     'source_adapter': 'commons' if (module or subject or '').startswith('commons') else
                                       'terminal' if (module or subject or '').startswith(('game_gamer.tui', 'terminal.')) else
                                       'engine' if (module or subject or '').startswith(('game_gamer.runtime', 'engine.')) else None,
                     'source_file': source_file, 'source_line': (location or {}).get('line'),
                     'screen_id': screen_id, 'question_id': question_id,
                     'option_id': edge['id'] if edge and edge.get('declared_option') else None,
                     'transition_id': (edge or {}).get('transition_id') or (edge or {}).get('id'),
                     'target': (edge or {}).get('target'), 'guard': (edge or {}).get('guard'),
                     'engine_action': (edge or {}).get('action_id') or node.get('action_id'),
                     'reason': finding['reason'], 'root_cause': root, 'classification': classification,
                     'graph_subject_id': subject, 'source_module': module,
                     'source_location_kind': ('transition_callsite' if (edge or {}).get('source_code') else
                                              'action_definition' if node.get('kind')=='action' and location else
                                              'node_registration' if location else None),
                     'source_matches_snapshot': matches_snapshot,
                     'application_defect_evidence': None})
        rows[-1]['identity_status']='executable_transition' if (edge or {}).get('transition_id') else 'legacy_graph_observation_only'
    rows.sort(key=lambda r: (r['root_cause'], r['category'], r['diagnostic_id']))
    groups = []
    for cause in sorted({row['root_cause'] for row in rows}):
        members = [r for r in rows if r['root_cause'] == cause]
        groups.append({'root_cause': cause, 'finding_count': len(members),
                       'unique_subjects': len({r['graph_subject_id'] for r in members}),
                       'categories': dict(sorted(Counter(r['category'] for r in members).items())),
                       'diagnostic_ids': [r['diagnostic_id'] for r in members]})
    uncertain = [r for r in rows if r['classification'] == 'extraction_uncertainty']
    return {'schema_version': 'game-gamer/diagnostic-inventory/v1',
            'graph_implementation_digest': graph.get('implementation_digest'),
            'counts': dict(sorted(Counter(r['category'] for r in rows).items())),
            'classification': {'extraction_uncertainty_findings': len(uncertain),
                               'extraction_uncertainty_subjects': len({r['graph_subject_id'] for r in uncertain}),
                               'confirmed_application_defects': 0,
                               'note': 'A missing graph path is not evidence of an application defect. Coverage gaps are verification gaps; application defects require a separate reproducer.'},
            'groups': groups, 'diagnostics': rows}


def root_cause(category, edge, node):
    if category == 'missing_recovery':
        return ('route_dispatch_not_registered' if node.get('kind') == 'route' else
                'recovery_handler_not_registered'), 'extraction_uncertainty'
    if edge and edge.get('target') is None:
        return ('dynamic_provider_consumer_not_registered' if edge.get('dynamic_provider') else
                'menu_value_handler_not_registered'), 'extraction_uncertainty'
    if edge and not edge.get('instrumentation'):
        return 'runtime_transition_observer_not_registered', 'extraction_uncertainty'
    return ('engine_outcome_not_observed' if edge and edge.get('kind') == 'action' else
            'instrumented_transition_not_observed'), 'verification_gap'
