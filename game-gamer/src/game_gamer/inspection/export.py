"""Three deterministic serialisers of one canonical graph, plus release comparison."""
import html
import json
import textwrap
from . import SCHEMA_VERSION, canonical_json
from .source import token


def export_graph(graph, format='json'):
    if format == 'json':
        return canonical_json(graph)
    if format == 'mermaid':
        return mermaid(presentation_metadata(graph))
    if format == 'dot':
        return dot(presentation_metadata(graph))
    raise ValueError('unsupported_graph_format: ' + format)


def presentation_metadata(graph):
    from .audit import audit_graph
    report=audit_graph(graph)
    result={**graph,'edges':[dict(edge) for edge in graph['edges']]}
    result.setdefault('audit_summary',{'metrics':report['metrics'],'complete_application_verified':False})
    result.setdefault('limitations',['Source-only interface observations carry extraction uncertainty. Engine definitions and observed calls are not full application verification.'])
    defects={f.get('edge_id') for f in report['findings'] if f.get('classification') in {'graph_defect','confirmed_application_defect'}}
    for edge in result['edges']:
        if edge['id'] in defects:edge['classification']='graph_defect'
    return result


def coverage_label(graph):
    metrics=graph.get('audit_summary',{}).get('metrics',{})
    counts=' · '.join(key.replace('_',' ')+'='+str(value) for key,value in metrics.items())
    return textwrap.fill('Coverage / audit: '+counts,110)+'\n'+textwrap.fill('; '.join(graph.get('limitations',[])),110)


def colour(edge):
    if edge.get('classification') in {'graph_defect','confirmed_application_defect'}:return '#c62828'
    if edge.get('availability', {}).get('status') == 'disabled': return '#9e9e9e'
    if edge.get('extraction_status')=='source_only' or edge.get('target') is None:return '#ef6c00'
    if edge.get('recovery'): return '#2e7d32'
    if edge.get('changes_world_state'): return '#7b1fa2'
    if edge.get('guard'): return '#ef6c00'
    return '#607d8b'


def mermaid(graph):
    def label(value):
        return html.escape(str(value), quote=True).replace('\n', ' ').replace('|', '&#124;')
    lines = ['flowchart LR', '  %% Canonical IDs are retained in node/edge comments.']
    if graph.get('limitations') or graph.get('audit_summary'):
        lines.append('  graph_limits["'+label(coverage_label(graph))+'"]')
    aliases = {n['id']: 'n' + token(n['id']) for n in graph['nodes']}
    for scope in sorted({n['scope'] for n in graph['nodes']}):
        lines.append('  subgraph scope_' + token(scope) + '["' + label(scope.title()) + '"]')
        for n in graph['nodes']:
            if n['scope'] == scope:
                lines += ['    %% node ' + n['id'], f'    {aliases[n["id"]]}["{label(n["label"])}"]']
        lines.append('  end')
    rendered = 0
    for e in graph['edges']:
        target = aliases.get(e.get('target'))
        if not target:
            target = 'unresolved_' + token(e['id'])
            lines.append(f'  {target}["Unresolved destination"]')
        option = e['option']
        if len(option) > 90:
            option = option[:87] + '…'
        lines += ['  %% edge ' + e['id'], f'  {aliases[e["source"]]} -->|"{label(option)}"| {target}',
                  f'  linkStyle {rendered} stroke:{colour(e)}']
        rendered += 1
    lines += ['  subgraph legend["Legend (presentation only)"]',
              '    legend_text["Grey: navigation / disabled · Purple: state change · Amber: conditional or extraction uncertainty · Red: confirmed graph defect · Green: recovery"]', '  end']
    return '\n'.join(lines) + '\n'


def dot(graph):
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    splines = 'polyline' if len(graph['edges']) < 150 else 'false'
    lines = ['digraph decisions {', '  rankdir=LR;',
             '  graph [newrank=true, splines=' + splines + ', ranksep=1];',
             '  node [fontname="Helvetica", fontsize=11];', '  edge [fontname="Helvetica", fontsize=10];']
    if graph.get('limitations') or graph.get('audit_summary'):
        lines.append('  label='+quote(coverage_label(graph))+';')
    for scope in sorted({n['scope'] for n in graph['nodes']}):
        lines += ['  subgraph cluster_' + token(scope) + ' {', '    label=' + quote(scope.title()) + ';']
        for n in graph['nodes']:
            if n['scope'] == scope:
                shape = {'question': 'diamond', 'outcome': 'oval', 'action': 'hexagon'}.get(n['kind'], 'box')
                lines.append('    ' + quote(n['id']) + ' [id=' + quote(n['id']) + ', label=' + quote(n['label']) + ', shape=' + shape + '];')
        lines.append('  }')
    for e in graph['edges']:
        target = e.get('target') or 'unresolved.' + e['id']
        if e.get('target') is None:
            lines.append('  ' + quote(target) + ' [label="Unresolved", shape=octagon];')
        style = 'dashed' if e.get('guard') or e.get('availability', {}).get('status') == 'disabled' else 'solid'
        lines.append('  ' + quote(e['source']) + ' -> ' + quote(target) + ' [id=' + quote(e['id']) +
                     ', label=' + quote(e['option']) + ', color=' + quote(colour(e)) + ', style=' + style + '];')
    lines += ['  subgraph cluster_legend {', '    label="Legend (presentation only)";',
              '    legend [shape=note, label="Grey: navigation / disabled\\nPurple: state change\\nAmber: conditional / extraction uncertainty\\nRed: confirmed graph defect\\nGreen: recovery"];', '  }', '}']
    return '\n'.join(lines) + '\n'


def diff_graphs(previous, current):
    for graph in (previous, current):
        if graph.get('schema_version') != SCHEMA_VERSION or graph.get('graph_type') != 'decision':
            raise ValueError('unsupported_decision_graph_schema')
    def index(graph, collection, predicate=lambda row: True):
        return {row['id']: row for row in graph[collection] if predicate(row)}
    def difference(collection, predicate):
        old, new = index(previous, collection, predicate), index(current, collection, predicate)
        return {'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys())}
    def semantic(value):
        if isinstance(value, dict):
            return {k: semantic(v) for k, v in value.items() if k not in {'source', 'source_code'}}
        if isinstance(value, list): return [semantic(v) for v in value]
        return value
    old, new = index(previous, 'edges'), index(current, 'edges')
    fields = {'action_mappings': ('action_id',), 'guards': ('guard',), 'permissions': ('permissions',),
              'recovery_paths': ('recovery', 'target')}
    changes = {}
    for category, keys in fields.items():
        changes[category] = [{'id': ident, 'before': {key: old[ident].get(key) for key in keys},
                             'after': {key: new[ident].get(key) for key in keys}}
                            for ident in sorted(old.keys() & new.keys())
                            if any(semantic(old[ident].get(key)) != semantic(new[ident].get(key)) for key in keys)
                            and (category != 'recovery_paths' or old[ident].get('recovery') or new[ident].get('recovery'))]
    # Permissions/guards can change on an action with no interface edge.
    old_nodes, new_nodes = index(previous, 'nodes'), index(current, 'nodes')
    for category, key in [('guards', 'guards'), ('permissions', 'permissions')]:
        changes[category] += [{'id': ident, 'before': old_nodes[ident].get(key), 'after': new_nodes[ident].get(key)}
                              for ident in sorted(old_nodes.keys() & new_nodes.keys())
                              if semantic(old_nodes[ident].get(key)) != semantic(new_nodes[ident].get(key))]
    return {'schema_version': SCHEMA_VERSION, 'screens': difference('nodes', lambda n: n['kind'] == 'screen'),
            'options': difference('edges', lambda e: e.get('declared_option', False)), 'changed': changes}
