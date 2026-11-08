"""Failure modes of the verification machinery, not just happy-path counts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game_gamer.inspection import extract_decisions
from game_gamer.inspection.diagnostics import diagnostic_inventory
from game_gamer.inspection.evidence import TransitionEvidence
from game_gamer.inspection.release import release_gate
from game_gamer.inspection.views import project_view,FILTERS,VIEWS
from commons_game.reconstruction_transitions import REGISTRY,P
from test_matrix_navigation import app
from test_network_reconstruction import enter_reconstruction

ROOT=Path(__file__).resolve().parents[1]


def test_baseline_inventory_reconciles_all_rows_and_does_not_invent_locations():
    folder=ROOT/'docs/decision-graphs/baseline'
    graph=json.loads((folder/'decisions.json').read_text())
    report=json.loads((folder/'decision_audit.json').read_text())
    inventory=diagnostic_inventory(graph,report)
    assert inventory['counts']=={'unmapped_option':132,'missing_recovery':41,
                                'untested_transition':527,'uninstrumented_transition':376}
    fields={'diagnostic_id','severity','category','source_adapter','source_file','source_line','screen_id',
            'question_id','option_id','transition_id','target','guard','engine_action','reason'}
    assert len({r['diagnostic_id'] for r in inventory['diagnostics']})==1076
    assert all(fields<=r.keys() for r in inventory['diagnostics'])
    assert inventory['classification']['confirmed_application_defects']==0
    assert len(inventory['groups'])>len(inventory['counts'])
    assert all(r['application_defect_evidence'] is None for r in inventory['diagnostics'])
    # A missing provenance field is null, not filled from a guessed file/line.
    artificial={'nodes':[{'id':'q','kind':'question'}], 'edges':[
        {'id':'opaque','source':'q','target':None,'kind':'navigation','declared_option':True}], 'sources':[]}
    row=diagnostic_inventory(artificial,{'findings':[{'code':'unmapped_option','edge_id':'opaque',
        'severity':'ERROR','reason':'unresolved'}]})['diagnostics'][0]
    assert row['source_file'] is None and row['source_line'] is None and row['screen_id'] is None


def test_failed_pytest_observations_are_not_published_as_verification(tmp_path):
    test=tmp_path/'test_failed_evidence.py'
    test.write_text(f'''import sys
sys.path.insert(0,{str(ROOT/'tests')!r})
from test_matrix_navigation import app
from test_network_reconstruction import enter_reconstruction

def test_passing_navigation():
 ui,_=app(choices=[3]);enter_reconstruction(ui)
 assert ui.route.kind=='reconstruction'

def test_failing_after_observed_commit():
 ui,_=app(choices=[3,0],answers=['y']);enter_reconstruction(ui)
 ui.handle('down',ui.build_screen());ui.handle('c',ui.build_screen())
 assert False, 'intentional assertion failure after actual commit'
''')
    output=tmp_path/'evidence.json'
    result=subprocess.run([sys.executable,'-m','pytest',str(test),'-q','-p','game_gamer.inspection.pytest_plugin',
                           '--transition-evidence',str(output)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==1,result.stdout+result.stderr
    evidence=json.loads(output.read_text())
    assert any('test_passing_navigation' in ref for ref in evidence['passed_test_refs'])
    assert all('test_failing_after_observed_commit' not in ref for ref in evidence['passed_test_refs'])
    assert P+'connect.recall' not in evidence['transitions']
    assert P+'intro.begin' in evidence['transitions']


def test_unaccepted_trials_and_stale_evidence_cannot_open_the_release_gate():
    recorder=TransitionEvidence(REGISTRY)
    with recorder.capture('unaccepted'):
        ui,_=app(choices=[3]);enter_reconstruction(ui)
    evidence=recorder.document()
    assert not evidence['transitions']
    graph=extract_decisions(scope='exercise.reconstruct',transition_evidence=evidence)
    gate=release_gate(graph,evidence)
    assert not gate['passed'] and not gate['criteria']['untested_critical_transitions']['passed']
    assert not gate['criteria']['persistence_and_replay']['passed']
    stale={**evidence,'contract_digest':'old'}
    with pytest.raises(ValueError,match='stale'):
        release_gate(graph,stale)
    with pytest.raises(ValueError,match='unfiltered'):
        release_gate(project_view(graph,'navigation'),evidence)


@pytest.mark.parametrize('view',VIEWS)
def test_four_views_preserve_transition_references_and_extraction_limits(view):
    graph=extract_decisions(scope='exercise.reconstruct')
    result=project_view(graph,view)
    assert result['nodes'] and result['edges'] and result['limitations']
    assert result['audit_summary']['complete_application_verified'] is False
    known={n['id'] for n in result['nodes']}
    assert all(e['source'] in known and (e.get('target') is None or e['target'] in known) for e in result['edges'])
    if view!='overview':
        assert any(e.get('transition_id')==P+'connect.recall' for e in result['edges'])
    if view=='lifecycle':
        # Cancellation must bypass submission and receipts, not follow a fake
        # success lifecycle merely to reach its recovery destination.
        cancellation=[e for e in result['edges'] if e['id']==P+'connect.recall.lifecycle.input.feedback.cancelled']
        assert cancellation and 'submission' not in cancellation[0]['source']


@pytest.mark.parametrize('filter',FILTERS)
def test_diagnostic_filters_are_views_of_actual_findings(filter):
    baseline=json.loads((ROOT/'docs/decision-graphs/baseline/decisions.json').read_text())
    result=project_view(baseline,'decisions',filters=[filter])
    assert result['view']['filters']==[filter] and result['edges']
    assert all(f['code']==FILTERS[filter] for f in result['diagnostics'])


def test_trace_sink_failure_does_not_change_a_committed_action():
    from game_gamer.transitions import TraceSession
    ui,_=app(choices=[3,0],answers=['y'])
    def unavailable(record):raise OSError('sink unavailable')
    ui.transition_trace=TraceSession(sink=unavailable)
    enter_reconstruction(ui);ui.handle('down',ui.build_screen())
    before=ui.current().revision;ui.handle('c',ui.build_screen())
    assert ui.current().revision==before+1
    assert ui.transition_trace.records[-1]['outcome']=='committed'
    assert ui.transition_trace.sink_errors>0 and not ui.transition_trace.records[-1]['contract_violations']


def test_cli_exposes_views_inventory_and_a_fail_closed_release_gate(tmp_path):
    def run(*arguments):
        return subprocess.run([sys.executable,'-m','game_gamer','inspect','decisions',*map(str,arguments)],
                               capture_output=True,text=True,cwd=ROOT)
    inventory=tmp_path/'inventory.json'
    result=run('--scope','exercise.reconstruct','--audit','--inventory-output',inventory)
    assert result.returncode==0,result.stderr
    assert json.loads(inventory.read_text())['counts']['untested_transition']>0
    for view in VIEWS:
        result=run('--scope','exercise.reconstruct','--view',view)
        graph=json.loads(result.stdout)
        assert result.returncode==0 and graph['view']['name']==view
    recorder=TransitionEvidence(REGISTRY)
    evidence=tmp_path/'evidence.json';evidence.write_text(json.dumps(recorder.document()))
    output=tmp_path/'gate.json'
    result=run('--scope','exercise.reconstruct','--transition-evidence',evidence,
               '--release-gate','--release-output',output)
    assert result.returncode==1 and 'BLOCKED' in result.stdout
    assert not json.loads(output.read_text())['passed']


def test_trace_jsonl_uses_the_requested_schema_without_payload_text(tmp_path):
    from game_gamer.transitions import TraceSession,jsonl_sink
    trace=tmp_path/'trace.jsonl'
    ui,_=app(choices=[3,0],answers=['y'])
    ui.transition_trace=TraceSession(sink=jsonl_sink(trace))
    enter_reconstruction(ui);ui.handle('down',ui.build_screen());ui.handle('c',ui.build_screen())
    records=[json.loads(line) for line in trace.read_text().splitlines()]
    required={'transition_id','session_id','actor_id','source_state','requested_action','outcome',
              'destination_state','duration_ms','correlation_id'}
    assert all(required<=record.keys() for record in records)
    assert records[-1]['transition_id']==P+'connect.recall'
    assert records[-1]['engine_results'][0]['commit_id']
    assert 'payload' not in trace.read_text() and 'Fixture' not in trace.read_text()
    assert (trace.stat().st_mode&0o777)==0o600


def test_real_cli_can_record_the_reconstruction_slice_in_line_mode(tmp_path):
    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame
    from test_matrix_navigation import world
    db=tmp_path/'world.sqlite';trace=tmp_path/'ui.jsonl'
    store=SQLiteStore(db,CommonsGame);store.initialise(world())
    before=store.load().project('log')
    result=subprocess.run([sys.executable,'-m','commons_game','--db',str(db),'play','--line-mode',
                           '--explore','--ui-trace-output',str(trace)],
                          input='enter\n4\n4\nenter\nq\n',capture_output=True,text=True,cwd=ROOT,timeout=15)
    assert result.returncode==0,result.stderr
    records=[json.loads(line) for line in trace.read_text().splitlines()]
    assert [r['transition_id'] for r in records]==[P+'enter',P+'intro.begin',P+'quit']
    assert all(not r['contract_violations'] for r in records)
    assert store.load().project('log')==before


def test_release_requirements_survive_canonical_json_object_ordering():
    recorder=TransitionEvidence(REGISTRY)
    with recorder.capture('navigation') as trial:
        ui,_=app(choices=[3]);enter_reconstruction(ui)
    recorder.accept(trial)
    evidence=recorder.document()
    graph=extract_decisions(scope='exercise.reconstruct',transition_evidence=evidence)
    original=release_gate(graph,evidence)
    loaded=release_gate(json.loads(json.dumps(graph,sort_keys=True)),evidence)
    assert original==loaded
    missing=original['criteria']['critical_lifecycle_checks']['missing']
    assert not any(m['transition_id'] in {P+'enter',P+'intro.begin'} for m in missing)
    with pytest.raises(ValueError,match='schema'):
        release_gate(graph,{**evidence,'schema_version':'unsupported'})
    with pytest.raises(ValueError,match='threshold'):
        release_gate(graph,evidence,max_p95_ms=float('nan'))
