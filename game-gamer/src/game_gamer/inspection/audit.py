"""Structural metrics, explicit exceptions and actionable diagnostics."""
from collections import defaultdict, deque


def reachable(starts, adjacency):
    seen, queue = set(starts), deque(starts)
    while queue:
        for target in adjacency[queue.popleft()]:
            if target not in seen:
                seen.add(target); queue.append(target)
    return seen


def audit_graph(graph, *, exceptions=()):
    nodes = {n['id']: n for n in graph['nodes']}
    findings = list(graph.get('diagnostics', []))
    forward, reverse = defaultdict(set), defaultdict(set)
    unmapped = []
    for e in graph['edges']:
        broken = e['source'] not in nodes or (e.get('target') is not None and e['target'] not in nodes)
        if broken:
            findings.append({'severity': 'ERROR', 'code': 'broken_reference', 'edge_id': e['id'],
                             'reason': 'Source or destination is absent from the canonical graph.'})
        elif e.get('target'):
            forward[e['source']].add(e['target']); reverse[e['target']].add(e['source'])
        if e.get('declared_option') and e.get('target') is None and not e.get('action_id') and not e.get('terminal'):
            unmapped.append(e['id'])
        if e.get('coverage_status') != 'covered' and (e.get('declared_option') or e['kind'] == 'action'):
            findings.append({'severity': 'WARNING', 'code': 'untested_transition', 'edge_id': e['id'],
                             'reason': 'No observed automated test traversal.' if e.get('instrumentation') else
                             'This imperative transition cannot yet be instrumented.',
                             'coverage_status': e.get('coverage_status', 'uninstrumented')})
        if (e.get('declared_option') or e['kind']=='action') and not e.get('instrumentation'):
            findings.append({'severity':'WARNING','code':'uninstrumented_transition','edge_id':e['id'],
                             'reason':'No registered execution observer exists for this transition.'})
        if e.get('dynamic_provider') and e.get('resolution') == 'unresolved':
            findings.append({'severity': 'WARNING', 'code': 'unresolved_dynamic_provider', 'edge_id': e['id'],
                             'reason': e['dynamic_provider']['expression']})
        if e.get('availability', {}).get('status') == 'disabled':
            findings.append({'severity': 'INFO', 'code': 'disabled_action', 'edge_id': e['id'],
                             'reason': ', '.join(e['availability']['reasons'])})
    entries = {n['id'] for n in nodes.values() if n.get('entry_point') or n['kind'] == 'action'}
    seen = reachable(entries, forward)
    unreachable = sorted(n['id'] for n in nodes.values() if n['kind'] == 'screen' and n['id'] not in seen)
    # Recovery edges are themselves verified references, never assumed for every screen.
    recovery_sources = {e['source'] for e in graph['edges'] if e.get('recovery') and e.get('target') in nodes}
    ends = entries | recovery_sources | {n['id'] for n in nodes.values() if n.get('terminal')}
    recoverable = reachable(ends, reverse)
    missing = sorted(n['id'] for n in nodes.values() if n['kind'] in {'screen', 'question', 'route'}
                     and not n.get('terminal') and n['id'] not in recoverable)
    for ident in unreachable:
        findings.append({'severity': 'ERROR', 'code': 'unreachable_screen', 'node_id': ident,
                         'reason': 'No resolved structural path from a declared interface entry point.'})
    for ident in unmapped:
        findings.append({'severity': 'ERROR', 'code': 'unmapped_option', 'edge_id': ident,
                         'reason': 'No resolvable destination, action or explicit terminal outcome.'})
    for ident in missing:
        findings.append({'severity': 'ERROR', 'code': 'missing_recovery', 'node_id': ident,
                         'reason': 'No resolved route to cancellation, completion or an entry point.'})
    for exception in exceptions:
        if not exception.get('reason') or not exception.get('code') or not exception.get('id'):
            raise ValueError('exception_requires_code_id_and_reason')
        matched = False
        for finding in findings:
            if finding['code'] == exception['code'] and exception['id'] in (finding.get('node_id'), finding.get('edge_id')):
                finding['exception'] = exception['reason']; matched = True
        if not matched:
            findings.append({'severity': 'WARNING', 'code': 'unused_exception', 'reason': str(exception)})
    for finding in findings:
        finding.setdefault('classification','graph_defect' if finding['code']=='broken_reference' else
                           'verification_gap' if finding['code']=='untested_transition' else
                           'extraction_uncertainty')
    unique = {str(sorted(f.items())): f for f in findings}
    findings = sorted(unique.values(), key=lambda f: (f['severity'], f['code'], f.get('node_id', ''), f.get('edge_id', ''), f['reason']))
    decisions = [e for e in graph['edges'] if e.get('declared_option') or e['kind'] == 'action']
    metrics = {'screens': sum(n['kind'] == 'screen' for n in nodes.values()),
               'questions': sum(n['kind'] == 'question' for n in nodes.values()),
               'options': sum(bool(e.get('declared_option')) for e in graph['edges']),
               'engine_actions': sum(n['kind'] == 'action' for n in nodes.values()),
               'unreachable_screens': len(unreachable), 'unmapped_options': len(unmapped),
               'missing_recovery_paths': len(missing),
               'untested_transitions': sum(e.get('coverage_status') != 'covered' for e in decisions),
               'uninstrumented_transitions': sum(not e.get('instrumentation') for e in decisions)}
    return {'schema_version': '0.1.0', 'metrics': metrics, 'findings': findings,
            'interfaces': graph.get('interfaces', []),
            'passed': not any(f['severity'] == 'ERROR' and not f.get('exception') for f in findings)}


def audit_text(report):
    labels = [('screens', 'Screens'), ('questions', 'Questions'), ('options', 'Options'),
              ('engine_actions', 'Engine actions'), ('unreachable_screens', 'Unreachable screens'),
              ('unmapped_options', 'Unmapped options'), ('missing_recovery_paths', 'Missing recovery paths'),
              ('untested_transitions', 'Untested transitions'), ('uninstrumented_transitions', 'Uninstrumented transitions')]
    lines = ['DECISION GRAPH AUDIT', ''] + [f'{label + ":":28} {report["metrics"][key]:6}' for key, label in labels]
    counts = {severity: sum(f['severity'] == severity for f in report['findings']) for severity in ('ERROR', 'WARNING', 'INFO')}
    lines += ['', ' · '.join(f'{key}: {value}' for key, value in counts.items()),
              'Detailed diagnostics are in --audit-output. Exceptions remain visible.']
    for interface in report['interfaces']:
        lines.append(interface['id'] + ': ' + interface['status'] +
                     (' (imperative branches remain unresolved)' if not interface.get('complete') else ''))
    if not report['interfaces']:
        lines.append('Terminal navigation coverage unavailable.')
    return '\n'.join(lines) + '\n'
