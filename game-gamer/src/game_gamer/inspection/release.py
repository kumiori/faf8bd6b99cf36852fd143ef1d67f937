"""Fail-closed, scoped release gates. No application-wide verification claim."""
from .audit import audit_graph


def release_gate(graph,evidence,*,responsiveness=None,max_p95_ms=100):
    import math
    if not graph.get('contract'):
        raise ValueError('release_gate_requires_executable_contract')
    if graph.get('view') or graph.get('selection') or any(n['scope'] not in {graph['contract']['scope'],'engine'} for n in graph['nodes']):
        raise ValueError('release_gate_requires_complete_unfiltered_release_scope')
    if not isinstance(evidence,dict) or evidence.get('schema_version')!='game-gamer/transition-evidence/v1':
        raise ValueError('unsupported_transition_evidence_schema')
    if evidence.get('contract_id')!=graph['contract']['id'] or evidence.get('contract_digest')!=graph['contract']['digest'] or evidence.get('source')!='passed_test_runtime_traces':
        raise ValueError('missing_or_stale_release_evidence')
    audit=audit_graph(graph)
    issues=[]
    rows=evidence.get('transitions',{})
    missing_tests=[];missing_instrumentation=[];missing_checks=[]
    for definition in graph['contract']['definitions']:
        if not definition['critical']:
            continue
        id=definition['id']; row=rows.get(id,{})
        if definition['instrumentation']!='registered_handler':
            missing_instrumentation.append(id)
        if not row.get('test_refs'):
            missing_tests.append(id)
        normal_outcomes=('completed','selected','committed','idempotent','cancelled','rejected','blocked')
        default=next((outcome for outcome in normal_outcomes if outcome in definition['destinations']),None)
        required=definition['requirements'] or ((default,) if default else ('normal_outcome_not_declared',))
        available=set(row.get('outcomes',[]))|set(row.get('checks',[]))
        for requirement in required:
            if requirement not in available:
                missing_checks.append({'transition_id':id,'requirement':requirement})
        for kind in definition['engine_actions']:
            if kind not in row.get('committed_engine_actions',[]):
                missing_checks.append({'transition_id':id,'requirement':'committed_variant:'+kind})
        for question in definition['questions']:
            if question not in row.get('observed_questions',[]):
                missing_checks.append({'transition_id':id,'requirement':'observed_question:'+question})
    violations=[{'transition_id':id,'violations':row['contract_violations']} for id,row in rows.items() if row.get('contract_violations')]
    unexpected_errors=[{'transition_id':id,'test_ref':observation['test_ref']} for id,row in rows.items()
                       for observation in row.get('observations',[]) if observation['trace']['outcome']=='error'
                       and observation['test_ref'] not in row.get('check_test_refs',{}).get('error_recovery',[])]
    unresolved=[f for f in audit['findings'] if f['code'] in {'broken_reference','unmapped_option','missing_recovery','unresolved_dynamic_provider','unresolved_route_dispatch','source_adapter_incomplete'}]
    if not isinstance(max_p95_ms,(int,float)) or not math.isfinite(max_p95_ms) or max_p95_ms<=0:
        raise ValueError('invalid_responsiveness_threshold')
    measurement_valid=(isinstance(responsiveness,dict) and responsiveness.get('schema_version')=='game-gamer/responsiveness/v1'
                       and responsiveness.get('contract_digest')==graph['contract']['digest']
                       and responsiveness.get('samples',0)>=20 and responsiveness.get('measurement')=='handle_and_render'
                       and responsiveness.get('authoritative_history_unchanged') is True
                       and isinstance(responsiveness.get('p95_ms'),(int,float))
                       and math.isfinite(responsiveness['p95_ms']) and responsiveness['p95_ms']>=0)
    criteria={
        'unmapped_options':{'passed':audit['metrics']['unmapped_options']==0,'actual':audit['metrics']['unmapped_options'],'required':0},
        'missing_recovery_paths':{'passed':audit['metrics']['missing_recovery_paths']==0,'actual':audit['metrics']['missing_recovery_paths'],'required':0},
        'untested_critical_transitions':{'passed':not missing_tests,'ids':missing_tests,'required':0},
        'uninstrumented_critical_transitions':{'passed':not missing_instrumentation,'ids':missing_instrumentation,'required':0},
        'critical_lifecycle_checks':{'passed':not missing_checks,'missing':missing_checks},
        'unresolved_source_branches':{'passed':not unresolved,'findings':unresolved,
            'review':'Executable registrations replace source inference within this scope. External handoffs explicitly terminate the scope.'},
        'engine_state_consistency':{'passed':not violations and not any(m['requirement']=='engine_consistency' for m in missing_checks),'violations':violations},
        'persistence_and_replay':{'passed':not any(m['requirement'] in {'persistence','replay'} for m in missing_checks)},
        'unexpected_execution_errors':{'passed':not unexpected_errors,'observations':unexpected_errors},
        'navigation_responsiveness':{'passed':measurement_valid and responsiveness['p95_ms']<=max_p95_ms,
            'measurement':responsiveness,'max_p95_ms':max_p95_ms},
    }
    return {'schema_version':'game-gamer/release-gate/v1','scope':graph['contract']['scope'],
        'contract_digest':graph['contract']['digest'],'complete_application_verified':False,
        'passed':all(c['passed'] for c in criteria.values()),'criteria':criteria,
        'limitations':graph.get('limitations',[]), 'audit_metrics':audit['metrics']}
