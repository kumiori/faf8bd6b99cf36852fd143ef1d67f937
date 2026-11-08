"""Project executable transition registrations, never infer their Python bodies."""
from copy import deepcopy
from dataclasses import asdict
from importlib.util import find_spec
import hashlib
from pathlib import Path

RECONSTRUCTION_SCOPE = 'exercise.reconstruct'


def reconstruction_registry():
    # Import the owning UI declarations; no world or player session is created.
    try:
        from commons_game.reconstruction import TRANSITIONS
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith('commons_game'):
            raise ValueError('reconstruction_contract_requires_the_commons_host') from None
        raise
    return TRANSITIONS.validate()


def contract_graph(registry, *, evidence=None):
    from . import SCHEMA_VERSION, fingerprint
    from .engine import extract_engine
    definitions = [registry.transitions[id].document() for id in sorted(registry.transitions)]
    graph = {'schema_version': SCHEMA_VERSION, 'graph_type': 'decision', 'mode': 'structural',
        'levels': ['navigation','decision','state'], 'nodes': [], 'edges': [], 'diagnostics': [],
        'interfaces': [{'id': registry.id, 'status':'executable_contract','complete':True}],
        'contract': {'id':registry.id,'digest':registry.digest(),'scope':RECONSTRUCTION_SCOPE,
                     'definitions':definitions, 'boundaries':'Shared screens are handoffs; their internal gameplay is outside this release scope.'},
        'limitations': ['This contract verifies the reconstruction slice only. Shared handoff destinations and the remaining application require their own contracts and evidence.']}
    evidence_rows = {}
    if evidence is not None:
        if not isinstance(evidence,dict) or evidence.get('schema_version')!='game-gamer/transition-evidence/v1':
            raise ValueError('unsupported_transition_evidence_schema')
        if evidence.get('contract_id')!=registry.id or evidence.get('source')!='passed_test_runtime_traces':
            raise ValueError('invalid_transition_evidence_source')
        if evidence.get('contract_digest') != graph['contract']['digest']:
            raise ValueError('stale_transition_evidence')
        evidence_rows = evidence.get('transitions',{})
    for state in registry.states.values():
        graph['nodes'].append({'id':state.id,'kind':state.kind,'label':state.label,
            'scope':RECONSTRUCTION_SCOPE,'level':'navigation','entry_point':state.entry,
            'boundary':state.boundary,'terminal':state.boundary,'provider':state.provider,
            'extraction_status':'declared_contract','source':state.source})
    action_types = {kind for definition in definitions for kind in definition['engine_actions']}
    action_types|={d['action_reference'] for d in definitions if d['action_reference']}
    engine_nodes, engine_edges = extract_engine()
    ids = {'engine.'+kind for kind in action_types}
    for node in engine_nodes:
        if node['id'] in ids:
            node['ui_transition_ids']=sorted(d['id'] for d in definitions if node['action_id'] in d['engine_actions'] or node['action_id']==d['action_reference'])
            graph['nodes'].append(node)
    for definition in definitions:
        id = definition['id']
        execution = id + '.execution'
        question = definition['sources'][0] if len(definition['sources'])==1 else id+'.sources'
        if len(definition['sources'])>1:
            graph['nodes'].append({'id':question,'kind':'interaction','label':definition['label'],
                'scope':RECONSTRUCTION_SCOPE,'level':'navigation','source':definition['source'],
                'extraction_status':'declared_contract'})
            for source in definition['sources']:
                graph['edges'].append(_edge(id+'.from.'+source,source,question,definition,declared_option=False))
        graph['nodes'].append({'id':execution,'kind':'interaction','label':definition['label'],
            'scope':RECONSTRUCTION_SCOPE,'level':'decision','source':definition['source'],
            'transition_id':id,'critical':definition['critical'],'extraction_status':'declared_contract'})
        entry = _edge(id,question,execution,definition,declared_option=True)
        observed = evidence_rows.get(id,{})
        entry['test_refs'] = sorted(observed.get('test_refs',[]))
        entry['coverage_status'] = 'covered' if entry['test_refs'] else 'uncovered'
        entry['observed_outcomes'] = sorted(observed.get('outcomes',[]))
        entry['verification_checks'] = sorted(observed.get('checks',[]))
        graph['edges'].append(entry)
        for state in definition['questions']:
            graph['edges'].append(_edge(id+'.question.'+state,execution,state,definition,declared_option=False,kind='question'))
            graph['edges'].append(_edge(id+'.question_return.'+state,state,execution,definition,declared_option=False,kind='return'))
        for outcome, targets in sorted(definition['destinations'].items()):
            for target in targets:
                edge = _edge(id+'.outcome.'+outcome+'.'+target,execution,target,definition,
                             declared_option=False,kind='outcome',outcome=outcome)
                edge['guard']={'handler_outcome':outcome}
                edge['changes_world_state']=outcome=='committed'
                edge['recovery']=definition['recovery'] or outcome in {'cancelled','rejected','blocked'}
                graph['edges'].append(edge)
        for kind in sorted(set(definition['engine_actions'])|({definition['action_reference']} if definition['action_reference'] else set())):
            graph['edges'].append(_edge(id+'.engine.'+kind,execution,'engine.'+kind,definition,
                declared_option=False,kind='engine_reference',action_id=kind,level='state'))
    modules=set(registry.dependency_modules)|{d['source']['module'] for d in definitions}
    graph['sources']=[{'module':module,'sha256':hashlib.sha256(Path(find_spec(module).origin).read_bytes()).hexdigest()}
                      for module in sorted(modules)]
    graph['nodes'].sort(key=lambda n:n['id']);graph['edges'].sort(key=lambda e:e['id'])
    graph['implementation_digest']=fingerprint(graph)
    graph['verification']={'status':'evidence_attached' if evidence else 'not_verified',
                           'evidence_source':'passed_test_runtime_traces' if evidence else None,
                           'complete_application_verified':False}
    return graph


def _edge(id,source,target,definition,**extra):
    return {'id':id,'transition_id':definition['id'],'source':source,'target':target,
        'kind':'decision' if definition['engine_actions'] else 'navigation',
        'level':'decision' if definition['engine_actions'] else 'navigation',
        'scope':RECONSTRUCTION_SCOPE,'option':definition['label'],'option_id':definition['id'],
        'action_id':definition['action_reference'] or (definition['engine_actions'][0] if len(definition['engine_actions'])==1 else None),
        'engine_actions':definition['engine_actions'], 'guard':definition['guards'],
        'changes_world_state':False,'source_code':definition['source'],
        'recovery':definition['recovery'],'critical':definition['critical'],
        'dynamic_provider':{'provider_id':definition['provider'],'enumeration':'symbolic'} if definition['provider'] else None,
        'resolution':'registered_handler','instrumentation':'registered_handler','coverage_status':'not_applicable',
        'test_refs':[],'extraction_status':'declared_contract',**extra}
