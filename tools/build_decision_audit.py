"""Rebuild diagnosis, views and scoped release evidence without live world data."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_gamer.inspection import canonical_json,extract_decisions,apply_coverage,select_scope
from game_gamer.inspection.audit import audit_graph,audit_text
from game_gamer.inspection.diagnostics import diagnostic_inventory
from game_gamer.inspection.export import export_graph,diff_graphs
from game_gamer.inspection.release import release_gate
from game_gamer.inspection.views import project_view,FILTERS
from measure_reconstruction_contract import measure


def write(path,value):
    path.write_text(value if isinstance(value,str) else canonical_json(value),encoding='utf-8')


def exports(folder,name,graph,*,visual_only=False):
    formats=[('mermaid','mmd'),('dot','dot')] if visual_only else [('json','json'),('mermaid','mmd'),('dot','dot')]
    if visual_only and (folder/(name+'.json')).exists():(folder/(name+'.json')).unlink()
    for format,suffix in formats:
        first=export_graph(graph,format)
        if first!=export_graph(graph,format):raise ValueError('non_deterministic_export')
        write(folder/(name+'.'+suffix),first)


def build(folder,evidence_path,coverage_paths):
    folder.mkdir(parents=True,exist_ok=True);scoped=folder/'reconstruction';scoped.mkdir(exist_ok=True)
    evidence=json.loads(evidence_path.read_text())
    base=extract_decisions();observations={}
    for path in coverage_paths:
        document=json.loads(path.read_text())
        apply_coverage(deepcopy(base),document)  # rejects stale/unknown observations
        for id,refs in document['transitions'].items():observations.setdefault(id,set()).update(refs)
    coverage={'schema_version':'0.1.0','implementation_digest':base['implementation_digest'],
              'transitions':{id:sorted(refs) for id,refs in sorted(observations.items())}}
    whole=extract_decisions(coverage=coverage,transition_evidence=evidence)
    report=audit_graph(whole)
    exports(folder,'decisions',whole)
    write(folder/'coverage.json',coverage)
    write(folder/'decision_audit.json',report);write(folder/'decision_audit.txt',audit_text(report))
    write(folder/'diagnostic_inventory.json',diagnostic_inventory(whole,report))
    baseline=folder/'baseline'
    if (baseline/'decisions.json').exists():
        previous=json.loads((baseline/'decisions.json').read_text())
        audit=json.loads((baseline/'decision_audit.json').read_text())
        write(baseline/'diagnostic_inventory.json',diagnostic_inventory(previous,audit))
        write(folder/'baseline_comparison.json',diff_graphs(previous,whole))
    release=extract_decisions(scope='exercise.reconstruct',transition_evidence=evidence)
    exports(scoped,'canonical',release)
    audit=audit_graph(release)
    write(scoped/'audit.json',audit);write(scoped/'audit.txt',audit_text(audit))
    write(scoped/'evidence.json',evidence)
    performance=measure()
    write(scoped/'responsiveness.json',performance)
    gate=release_gate(release,evidence,responsiveness=performance)
    write(scoped/'release_gate.json',gate)
    write(scoped/'release_gate.txt','RECONSTRUCTION RELEASE GATE: '+('PASS' if gate['passed'] else 'BLOCKED')+'\n'+
        '\n'.join(name+': '+('PASS' if result['passed'] else 'BLOCKED') for name,result in gate['criteria'].items())+
        '\n\nComplete application verified: false\n')
    for view,name in [('overview','application-overview'),('navigation','screen-navigation'),
                      ('decisions','decision-actions'),('lifecycle','transition-lifecycle')]:
        exports(folder,name,project_view(whole,view),visual_only=True)
        exports(scoped,name,project_view(release,view),visual_only=True)
    filtered=folder/'filters';filtered.mkdir(exist_ok=True)
    for filter in FILTERS:exports(filtered,filter,project_view(whole,'decisions',filters=[filter]),visual_only=True)
    focused=select_scope(release,scope='exercise.reconstruct.connect.recall')
    focused['audit_summary']={'metrics':audit['metrics'],'metric_scope':'complete reconstruction release contract','complete_application_verified':False}
    focused['limitations']=[*focused['limitations'],'Focused view; coverage counts describe the complete reconstruction release contract, not this cropped path.']
    exports(scoped,'recall-lifecycle',project_view(focused,'lifecycle'),visual_only=True)
    focused=select_scope(release,scope='exercise.reconstruct.connect')
    exports(folder,'reconstruction-connect',focused)
    samples=[]
    for row in evidence['transitions'].values():
        for observation in row['observations']:
            trace=observation['trace']
            if trace['outcome']=='committed' and trace['transition_id'].endswith('.recall'):
                samples.append(trace);break
        if samples:break
    write(scoped/'sample_trace.jsonl',''.join(json.dumps(r,sort_keys=True)+'\n' for r in samples))
    print('Baseline inventory preserved; full application remains unverified.')
    print(audit_text(audit),end='')
    print('Critical transitions:',sum(d['critical'] for d in release['contract']['definitions']))
    print('Technical release gate:', 'PASS' if gate['passed'] else 'BLOCKED')
    print('Local navigation p95:',performance['p95_ms'],'ms; people:',performance['fixture_people'])
    return gate


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('docs/decision-graphs'))
    parser.add_argument('--transition-evidence',type=Path,required=True)
    parser.add_argument('--coverage',type=Path,action='append',default=[])
    args=parser.parse_args()
    gate=build(args.output,args.transition_evidence,args.coverage)
    raise SystemExit(0 if gate['passed'] else 1)
