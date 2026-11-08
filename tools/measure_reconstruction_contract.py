"""Disposable synthetic frame measurements for the reconstruction release gate."""
import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from commons_game import load_scenario
from commons_game.ecosystem_import import connector_people_snapshot,import_snapshot
from commons_game.fullscreen import FullScreenTerminal
from commons_game.reconstruction_transitions import REGISTRY,P
from game_gamer.transitions import TraceSession


def measure(*,people=200,samples=100):
    if people<2 or samples<20:raise ValueError('measurement_requires_two_people_and_twenty_samples')
    snapshot=connector_people_snapshot([
        {'url':'https://app.notion.com/'+f'{i+1:032x}','Name':f'Fixture {i:04} Person','institution':'Synthetic fixture'}
        for i in range(people)],captured_at='2026-11-07T00:00:00+00:00',data_source_id='release-fixture',database_id='release-fixture')
    game=load_scenario('montreal-commons')
    result=import_snapshot(game,snapshot)
    if result['rejected']:raise ValueError('synthetic_fixture_import_failed')
    ui=FullScreenTerminal(game,viewport=None,plain=True,explore=True,transition_trace=TraceSession())
    ui.width,ui.height=144,34
    ui.push('exercises');REGISTRY.execute(P+'enter',ui);ui.build_screen();REGISTRY.execute(P+'intro.begin',ui)
    ui.build_screen()
    before=game.project('log')
    values=[]
    for index in range(samples):
        start=perf_counter()
        ui.handle('down' if index%2==0 else 'up',ui.build_screen())
        ui.build_screen()
        values.append((perf_counter()-start)*1000)
    if game.project('log')!=before:raise ValueError('navigation_changed_fixture_history')
    values.sort()
    return {'schema_version':'game-gamer/responsiveness/v1','contract_digest':REGISTRY.digest(),
        'measurement':'handle_and_render','samples':samples,'fixture_people':people,'fixture_events':game.revision,
        'viewport':{'width':144,'height':34},'median_ms':round(statistics.median(values),3),
        'p95_ms':round(values[int((samples-1)*.95)],3),'max_ms':round(values[-1],3),
        'authoritative_history_unchanged':True,'limitations':'Synthetic local read-only frames with in-memory tracing; not deployment load or human usability acceptance.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--people',type=int,default=200);parser.add_argument('--samples',type=int,default=100)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=measure(people=args.people,samples=args.samples)
    text=json.dumps(report,sort_keys=True,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')
