"""Public reproducible CLI playtest using FICTIONAL source-shaped records only."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

# Running this repository tool does not require installing the editable package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commons_game import CommonsGame
from commons_game.ecosystem_import import connector_people_snapshot
from commons_game.trajectory import load_trajectory_yaml, reconstruct


def main():
    parser = argparse.ArgumentParser(description='SADDLE PATHWAYS / fictional two-player acceptance demonstration')
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing results are preserved')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.output.resolve()
    rows = [{'url': 'https://app.notion.com/' + str(i)*32, 'Name': f'Fictional person {i}',
             'institution': f'Fictional organisation {i}'} for i in (1,2)]
    snapshot = connector_people_snapshot(rows, captured_at='2026-11-04T00:00:00+00:00',
                                         data_source_id='fictional-source', database_id='fictional-database')
    source = root/'fictional-snapshot.json'; source.write_text(json.dumps(snapshot, indent=2))
    prefix = [sys.executable, '-B', '-m', 'commons_game', '--db', str(root/'world.sqlite')]
    transcript = []
    def cli(arguments, entered=''):
        result = subprocess.run(prefix+arguments, input=entered, text=True, capture_output=True, cwd=ROOT, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)
        transcript.append('COMMAND: ' + ' '.join(arguments) + '\n' + result.stdout)
        return result.stdout
    cli(['start', 'montreal-commons']); cli(['import-ecosystem', str(source)])
    game = CommonsGame.load(root/'world.sqlite')
    people = [a['id'] for a in game.project('actors') if a['kind']=='person' and a['provenance']['kind']=='notion_snapshot']
    manifest = {'mode':'simulation','players':{subject: {'label':f'Player {subject.upper()} (mock)',
        'bindings':[{'actor_id':actor}]} for subject,actor in zip(('a','b'), people)}}
    identities = root/'mock-identities.json'; identities.write_text(json.dumps(manifest,indent=2))
    targets = [a for a in game.project('actors') if a['id']!=people[0]]
    target = next(i for i,a in enumerate(targets,1) if a['id']==people[1])
    proposal = ['1','a','1',str(target),'1','','Discuss possible collaboration','Review the proposed discussion','','','','y','o','g','b','h','b','q']
    flags = ['play','--mock-identities',str(identities),'--mock-player']
    entered = '\n'.join(proposal)+'\n'; (root/'player-a-proposal.stdin').write_text(entered)
    assert 'NEIGHBOURHOOD' in cli(flags+['a','--plain'], entered)
    reply = 'n\nopen contract-0001\nact contract-0001\n1\ny\nb\nq\n'
    (root/'player-b-response.stdin').write_text(reply)
    assert 'Proposal awaiting your response' in cli(flags+['b','--plain'], reply)
    finish = 'n\nact contract-0001\n1\ny\nb\n4\nt\nr\nb\nq\n'
    (root/'player-a-accept.stdin').write_text(finish)
    assert 'REPLAY CONSISTENT: True' in cli(flags+['a','--plain'], finish)
    cli(flags+['b','--plain'], 'g\nopen contract-0001\nb\nq\n')
    cli(['trajectory','--export',str(root/'trajectory.yaml')])
    saved = CommonsGame.load(root/'world.sqlite'); agreement = saved.project('agreements')[0]
    assert agreement['status']=='accepted' and agreement['outcome_status']=='unverified'
    assert reconstruct(load_trajectory_yaml((root/'trajectory.yaml').read_text())).get_world()==saved.get_world()
    (root/'transcript.txt').write_text('\n'.join(transcript))
    print('FICTIONAL SOURCE RECORDS / MOCK IDENTITIES / SIMULATION ONLY')
    print('Proposal → graph → second-player inbox → acceptance → restart → native trajectory replay: passed')
    print('Lifecycle: accepted. Outcome: unverified. No genuine consent or fulfilment recorded.')
    print('Evidence:',root)


if __name__=='__main__':
    main()
