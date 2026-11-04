"""Drive ordinary play using names/numbers only; source snapshot is explicit."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame,load_scenario
from commons_game.catalogue import people
from commons_game.ecosystem_import import connector_people_snapshot,import_snapshot,source_id
from commons_game.play import PlayableTerminal
from commons_game.presentation import display_label
from commons_game.trajectory import project_trajectory,trajectory_yaml,load_trajectory_yaml,reconstruct
from io import StringIO


def main():
    parser=argparse.ArgumentParser(description='SADDLE PATHWAYS / player-facing simulation acceptance')
    parser.add_argument('--snapshot',type=Path,help='Explicit private empirical snapshot; omitted means fictional records')
    parser.add_argument('--output',type=Path,required=True,help='New evidence directory; existing files are preserved')
    args=parser.parse_args();output=args.output.expanduser().resolve()
    if args.snapshot and output.is_relative_to(ROOT):raise ValueError('Empirical evidence must stay outside the public repository')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    if args.snapshot:
        snapshot=json.loads(args.snapshot.read_text());kind='EMPIRICAL SNAPSHOT / SIMULATION ONLY'
    else:
        snapshot=connector_people_snapshot([{'url':'https://app.notion.com/'+str(i)*32,
            'Name':('Alex Example' if i == 1 else 'Robin Example'),'institution':f'Fictional Organisation {i}'} for i in (1,2)],
            captured_at='2026-11-04T00:00:00+00:00',data_source_id='fictional',database_id='fictional')
        actors=[source_id(r['kind'],r['data_source_id'],r['record_id']) for r in snapshot['records'] if r['kind']=='person']
        for type_,actor in zip(('capacity','need'),actors):
            snapshot['records'].append({'kind':type_,'data_source_id':'fictional','record_id':type_,
                'fields':{'actor_id':actor,'domain':'Fictional shared interest','unit':'declared knowledge domain','quantity':None}})
        kind='FICTIONAL SOURCE RECORDS / SIMULATION ONLY'
    game=load_scenario('montreal-commons');report=import_snapshot(game,snapshot)
    if report['rejected']:raise ValueError('Snapshot contains rejected records; inspect the import report first')
    roster=people(game.get_world())
    degree=Counter(endpoint for p in game.derive_possibilities() for endpoint in (p['source_id'],p['target_id']))
    unique=[a for a in roster if len([p for p in roster if display_label(p)==display_label(a)])==1]
    a=max(unique or roster,key=lambda actor:degree[actor['id']])
    matches=Counter(p['target_id'] if p['source_id']==a['id'] else p['source_id'] for p in game.derive_possibilities() if a['id'] in (p['source_id'],p['target_id']))
    b=next((game.get_world()['actors'][id] for id,count in matches.most_common()
            if id in {p['id'] for p in roster} and len([p for p in roster if display_label(p)==display_label(game.get_world()['actors'][id])])==1),roster[1])
    preview=PlayableTerminal(game,source=StringIO(''),output=StringIO(),plain=True)
    neighbours=preview.neighbours(a['id'])
    index=next((i for i,n in enumerate(neighbours,1) if n['id']==b['id']),None)
    lines=['/'+display_label(a),'','open '+display_label(a)]
    if index:
        lines.extend(['>']*((index-1)//10)+[str(index)])
    else:
        lines+=['b','open '+display_label(b)]
    lines+=['a','1','A proposed commons collaboration','Explore a possible shared contribution',
            'Discuss the proposed collaboration','Review and discuss the proposal','','y','3',
            'p','/'+display_label(b),'','i','1','a','1','y','3',
            'p','/'+display_label(a),'','i','1','a','1','y','3',
            'open latest contract','h','1','','b','b','t','replay','q']
    entered='\n'.join(lines)+'\n';(output/'entered.stdin').write_text(entered)
    assert 'notion:' not in entered and 'contract-000' not in entered
    store=SQLiteStore(output/'world.sqlite',CommonsGame);store.initialise(game)
    cli=[sys.executable,'-B','-m','commons_game','--db',str(store.path),'play','--plain']
    result=subprocess.run(cli,input=entered,cwd=ROOT,capture_output=True,text=True,timeout=45)
    (output/'transcript.txt').write_text(result.stdout)
    assert result.returncode==0,result.stderr
    saved=store.load();agreements=saved.project('agreements')
    assert len(agreements)==1, 'The entered proposal did not create exactly one agreement'
    assert agreements[0]['status']=='accepted' and agreements[0]['outcome_status']=='unverified'
    assert len(agreements[0]['versions'][0]['acceptances'])==2
    assert 'REPLAY CONSISTENT: True' in result.stdout
    assert 'notion:person:' not in result.stdout, 'Opaque source IDs leaked into ordinary play'
    restart=subprocess.run(cli,input='/'+display_label(b)+'\n\nopen latest contract\nb\nreplay\nq\n',cwd=ROOT,capture_output=True,text=True,timeout=30)
    (output/'restart.txt').write_text(restart.stdout)
    assert restart.returncode==0 and 'REPLAY CONSISTENT: True' in restart.stdout
    document=project_trajectory(saved);encoded=trajectory_yaml(document)
    (output/'trajectory.yaml').write_text(encoded)
    assert reconstruct(load_trajectory_yaml(encoded)).get_world()==saved.get_world()
    assert saved.replay().project('network')==saved.project('network')
    for path in output.iterdir():
        if path.is_file():path.chmod(0o600)
    summary={'source_kind':kind,'eligible_people':len(roster),'contracts':len(agreements),
             'lifecycle':'accepted','outcome':'unverified','replay':True,'opaque_ids_required':False}
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n');(output/'result.json').chmod(0o600)
    print(json.dumps(summary,indent=2));print('Evidence:',output)


if __name__=='__main__':main()
