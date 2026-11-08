"""Presentation projections with source limitations and verification kept visible."""
from copy import deepcopy
from .audit import audit_graph

FILTERS={'unmapped':'unmapped_option','missing-recovery':'missing_recovery','untested':'untested_transition',
         'uninstrumented':'uninstrumented_transition','unresolved-dynamic':'unresolved_dynamic_provider'}
VIEWS=('overview','navigation','decisions','lifecycle')


def project_view(graph,view='decisions',*,filters=()):
    if view not in VIEWS or set(filters)-FILTERS.keys():
        raise ValueError('unknown_decision_view_or_filter')
    report=audit_graph(graph)
    result=deepcopy(graph)
    result.setdefault('limitations',['Source-only interface observations are discovery evidence; full application navigation and authoritative lifecycles remain unverified outside executable contracts.'])
    result.setdefault('audit_summary',{'metrics':report['metrics'],'complete_application_verified':False,
        'extraction_uncertainty':sum(f.get('classification')=='extraction_uncertainty' for f in report['findings']),
        'confirmed_application_defects':sum(f.get('classification')=='confirmed_application_defect' for f in report['findings'])})
    result['view']={'name':view,'filters':list(filters),'not_a_release_gate_input':True}
    if filters:
        findings=[f for f in report['findings'] if f['code'] in {FILTERS[f] for f in filters}]
        selected_edges={f['edge_id'] for f in findings if f.get('edge_id')}
        selected_nodes={f['node_id'] for f in findings if f.get('node_id')}
        result['edges']=[e for e in result['edges'] if e['id'] in selected_edges or e['source'] in selected_nodes or e.get('target') in selected_nodes]
        selected_nodes|={id for e in result['edges'] for id in (e['source'],e.get('target')) if id}
        result['nodes']=[n for n in result['nodes'] if n['id'] in selected_nodes]
        result['diagnostics']=findings
    if view=='overview':
        return overview(result)
    if view=='lifecycle' and result.get('contract'):
        return lifecycle(result)
    if view=='navigation' and result.get('contract'):
        flattened=navigation(result)
        legacy=[e for e in result['edges'] if e.get('extraction_status')!='declared_contract' and e.get('level')=='navigation']
        if legacy:
            ids={n['id'] for n in flattened['nodes']}|{i for e in legacy for i in (e['source'],e.get('target')) if i}
            flattened['nodes']=[n for n in result['nodes'] if n['id'] in ids]
            flattened['edges']+=legacy
            flattened['view']['semantics']='Registered screen transitions plus unchanged source-only discoveries. Amber source-only edges are not verified navigation.'
        return flattened
    if view=='navigation':
        keep={n['id'] for n in result['nodes'] if n.get('level')=='navigation'}
        result['edges']=[e for e in result['edges'] if e['source'] in keep and (e.get('target') in keep or e.get('target') is None)]
        result['nodes']=[n for n in result['nodes'] if n['id'] in keep]
    return result


def overview(graph):
    result=deepcopy(graph); nodes={}; membership={}
    for n in graph['nodes']:
        scope=n['scope']
        id='overview.'+scope
        membership[n['id']]=id
        item=nodes.setdefault(id,{'id':id,'kind':'overview','scope':scope,'level':'navigation','label':scope,
                                 'canonical_node_ids':[]})
        item['canonical_node_ids'].append(n['id'])
    edges={}
    for edge in graph['edges']:
        source=membership[edge['source']]; target=membership.get(edge.get('target'))
        key=(source,target)
        item=edges.setdefault(key,{'id':source+'.to.'+(target or 'unresolved'),'source':source,'target':target,
            'scope':nodes[source]['scope'],'kind':'overview','level':'navigation','option':'Declared transitions',
            'changes_world_state':False,'canonical_edge_ids':[],'test_refs':[]})
        item['canonical_edge_ids'].append(edge['id'])
        item['changes_world_state']|=bool(edge.get('changes_world_state'))
        if edge.get('extraction_status')=='source_only':
            item['extraction_status']='source_only';item['option']='Unverified source observations'
    result['nodes']=sorted(nodes.values(),key=lambda n:n['id'])
    result['edges']=sorted(edges.values(),key=lambda e:e['id'])
    for node in result['nodes']:
        node['label']=node['scope']+' · '+str(len(node['canonical_node_ids']))+' states/definitions'
    return result


def navigation(graph):
    result=deepcopy(graph)
    definitions=graph['contract']['definitions']
    retained={e.get('transition_id') for e in graph['edges']}
    nodes={n['id']:n for n in graph['nodes']}; edges=[]
    for definition in definitions:
        if definition['id'] not in retained:
            continue
        for source in definition['sources']:
            for outcome,targets in definition['destinations'].items():
                for target in targets:
                    if source not in nodes or target not in nodes:
                        continue
                    edges.append({'id':definition['id']+'.'+source+'.'+outcome+'.'+target,
                        'transition_id':definition['id'],'source':source,'target':target,'scope':definition['id'].rsplit('.',1)[0],
                        'kind':'navigation','level':'navigation','option':definition['label']+' / '+outcome,
                        'guard':definition['guards'],'changes_world_state':outcome=='committed',
                        'recovery':definition['recovery'] or outcome in {'cancelled','rejected'},
                        'canonical_transition_id':definition['id']})
    ids={i for e in edges for i in (e['source'],e['target'])}
    result['edges']=edges;result['nodes']=[n for n in graph['nodes'] if n['id'] in ids]
    return result


def lifecycle(graph):
    result=deepcopy(graph);nodes={};edges=[]
    retained={e.get('transition_id') for e in graph['edges']}
    canonical={n['id']:n for n in graph['nodes']}
    for d in graph['contract']['definitions']:
        if d['id'] not in retained:
            continue
        id=d['id']
        def phase(name):
            ident=id+'.lifecycle.'+name
            nodes.setdefault(ident,{'id':ident,'kind':'lifecycle','scope':id,'level':'decision',
                'label':d['label']+' / '+name,'transition_id':id,'canonical_transition_id':id})
            return ident
        def link(a,b,label):
            edges.append({'id':id+'.lifecycle.'+a+'.'+b,'source':phase(a),'target':phase(b),
                'transition_id':id,'scope':id,'level':'decision','kind':'lifecycle','option':label,
                'changes_world_state':b.startswith('receipt.committed'),'canonical_transition_id':id,
                'guard':d['guards'] if b=='guards' else None})
        for source in d['sources']:
            if source in canonical:
                nodes[source]=canonical[source]
                edges.append({'id':id+'.lifecycle.source.'+source,'source':source,'target':phase('request'),
                    'transition_id':id,'scope':id,'level':'decision','kind':'lifecycle','option':d['label'],
                    'changes_world_state':False,'canonical_transition_id':id})
        link('request','guards','Check source and preconditions')
        for outcome,targets in d['destinations'].items():
            if outcome=='blocked':
                link('guards','feedback.'+outcome,'Precondition denied')
            elif outcome=='cancelled':
                link('guards','input','Ask / choose / confirm')
                link('input','feedback.'+outcome,'Cancel before submission')
            elif outcome=='error':
                link('guards','input','Collect / confirm inputs')
                link('input','feedback.error','Input or UI failure before submission')
                if d['engine_actions']:
                    link('receipt.committed','feedback.error','UI failure after accepted commit: preserve receipt')
                    link('receipt.rejected','feedback.error','UI failure after rejection: preserve unchanged history')
            elif outcome=='aborted':
                for point in ['guards','input','handler']+(['submission','receipt.committed'] if d['engine_actions'] else []):
                    link(point,'feedback.aborted','Interrupt at this stage; inspect authoritative history')
            elif d['engine_actions']:
                link('guards','input','Collect and confirm inputs')
                link('input','submission','Submit to commit boundary')
                link('submission','receipt.'+outcome,'Observe '+outcome+' result')
                link('receipt.'+outcome,'feedback.'+outcome,'Render result')
            else:
                link('guards','handler','Run registered navigation handler')
                link('handler','feedback.'+outcome,'Observe '+outcome)
            link('feedback.'+outcome,'recovery.'+outcome,'Recover / continue / hand off')
            for target in targets:
                if target not in canonical:
                    continue
                nodes[target]=canonical[target]
                edges.append({'id':id+'.lifecycle.destination.'+outcome+'.'+target,
                    'source':phase('recovery.'+outcome),'target':target,'transition_id':id,'scope':id,
                    'level':'decision','kind':'outcome','option':outcome,'changes_world_state':False,
                    'guard':{'outcome':outcome},'canonical_transition_id':id})
    result['nodes']=list(nodes.values())
    legacy=[e for e in graph['edges'] if e.get('extraction_status') not in {'declared_contract',None}]
    if legacy:
        for e in legacy:
            for endpoint in (e['source'],e.get('target')):
                if endpoint in canonical:nodes[endpoint]=canonical[endpoint]
        edges+=legacy
        result['nodes']=list(nodes.values())
    result['edges']=list({e['id']:e for e in edges}.values())
    result['view']['semantics']='Declared paths separate precondition denial, cancellation before submission, commit-boundary rejection, accepted commits and exact retries. Engine receipts and UI trace observations remain distinct.'
    return result
