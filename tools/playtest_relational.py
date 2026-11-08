"""Jeanne → counterpart → Hack Network → contract → scenario → Back acceptance.

Fictional by default. --world clones an explicit private saved world outside the
repository, preserving its entire history. The acceptance itself is read-only.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from playtest_matrix import Driver,PTY,WebTerminal,fictional_world
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.catalogue import people
from commons_game.expertise import matrix
from commons_game.fullscreen import FullScreenTerminal
from commons_game.network_view import focus_graph
from commons_game.player import ActorSession
from commons_game.presentation import display_label
from commons_game.trajectory import project_trajectory,trajectory_yaml,load_trajectory_yaml,reconstruct


def setup(args):
    if args.world:
        if args.output.resolve().is_relative_to(ROOT):raise ValueError('Private evidence must remain outside the repository')
        game=SQLiteStore(args.world.expanduser(),CommonsGame).load()
    else:
        game=fictional_world(names=('Jeanne Example','Casey Example','Morgan Example'))
        roster=people(game.get_world());a,b=roster[:2]
        payload={'kind':'propose','id':'fixture-relationship','label':'Stewardship exchange',
            'parties':[a['id'],b['id']],'objective_id':'montreal-collaboration',
            'terms':{'purpose':'Review an exchange of expertise','responsibilities':[
                {'actor_id':a['id'],'description':'Offer a stewardship review'},
                {'actor_id':b['id'],'description':'Propose a workshop'}],'conditions':['Fictional simulation only']},
            'resources':[],'valid_until':'2026-12-01T00:00:00+00:00','policy_id':'simulation-personal',
            'verification':{'verifier_ids':['simulation-verifier'],'independent':True,'criteria':['Review supplied evidence']}}
        assert ActorSession(game,a['id']).submit(payload)['ok']
    projection=matrix(game.get_world());roster=projection['actors']
    jeanne=[a for a in roster if display_label(a)=='Jeanne']
    if len(jeanne)!=1:raise ValueError('This acceptance requires one unambiguous Jeanne source identity')
    jeanne=jeanne[0];row=next(i for i,a in enumerate(roster) if a['id']==jeanne['id'])
    parties={p for agreement in game.get_world()['agreements'].values() for p in agreement['parties']}
    partners=[a for j,a in enumerate(roster) if j!=row and projection['W'][row][j] is not None
              and projection['W'][row][j]>0 and a['id'] in parties
              and sum(display_label(b)==display_label(a) for b in roster)==1]
    if not partners:raise ValueError('No positive Jeanne relation has an existing contract party; no contract will be invented')
    return game,jeanne,partners[0]


async def exercise(d,game,jeanne,partner):
    other=display_label(partner)
    await d.expect('SADDLE PATHWAYS');await d.enter()
    await d.expect('WHO WILL YOU PLAY?');await d.choose('Jeanne')
    await d.expect('CHOOSE YOUR PATH');await d.enter();await d.expect('HEATMAP')
    await d.send('o');await d.send('n');await d.expect('Selected: Jeanne');d.snapshot('01-own-row-column')
    await d.send('z');await d.expect('NUMERIC');await d.send('z');await d.expect('HEATMAP')
    await d.send('/');await d.answer('Search by first name',other)
    await d.expect('FIND MATRIX PARTICIPANT');await d.enter()
    await d.send('o');await d.expect('Selected: Jeanne');d.snapshot('02-selected-relation')
    await d.enter();await d.expect('POTENTIAL COMPLEMENTARITY');await d.expect('Reverse:')
    d.snapshot('03-both-directions')
    await d.send('2');await d.expect('INSPECT / PERSON');await d.expect('Focus: '+other)
    assert 'Playing as: Jeanne' in d.text();d.snapshot('04-counterparty-profile')
    await d.send('b');await d.expect('POTENTIAL COMPLEMENTARITY');await d.expect('Reverse:')
    await d.send('w');await d.expect('HACK RENDERER');await d.expect('Centre: Jeanne');d.snapshot('05-hack-network')
    visual=focus_graph(game.project('network'),jeanne['id'],related=partner['id'],limit=8)
    index=next(i for i,n in enumerate(visual['nodes']) if n['kind']=='agreement')
    contract=visual['nodes'][index]['id']
    for _ in range(index):await d.send('\t')
    await d.enter();await d.expect('CONTRACT INSPECTOR');await d.expect('Governing policy');d.snapshot('06-existing-contract')
    assert 'Playing as: Jeanne' in d.text()
    preview=FullScreenTerminal(game,viewport=None,plain=True)
    preview.push('inspect',contract);entries=preview.build_screen().entries
    agreement=game.get_world()['agreements'][contract];version=agreement['versions'][agreement['current_version']-1]
    # Numbered graph links are the displayed navigation, not typed source IDs.
    async def follow(target,expected):
        i=next(i for i,(_,key) in enumerate(entries) if key==target)
        if i>=9:raise AssertionError('Fixture has too many links for this entered acceptance; use arrows')
        await d.send(str(i+1));await d.expect(expected)
        assert 'Playing as: Jeanne' in d.text()
    for party in agreement['parties']:
        await follow(party,'INSPECT / '+('PERSON' if game.get_world()['actors'][party]['kind']=='person' else 'ORGANISATION'))
        await d.send('b');await d.expect('CONTRACT INSPECTOR')
    await follow(version['policy_id'],'RULE ENFORCED');d.snapshot('07-policy')
    await d.send('b');await d.expect('CONTRACT INSPECTOR')
    await follow(agreement['objective_id'],'INSPECT / OBJECTIVE')
    # The scenario link is first in an objective inspector, distinct from the
    # objective itself. Workshop framing is explicitly preparatory.
    await d.send('1');await d.expect('SCENARIO / INSPECT');await d.expect('SOURCE MATERIAL')
    d.snapshot('08-workshop-scenario')
    await d.send('b');await d.expect('INSPECT / OBJECTIVE')
    await d.send('b');await d.expect('CONTRACT INSPECTOR')
    await d.send('b');await d.expect('HACK RENDERER')
    await d.send('b');await d.expect('POTENTIAL COMPLEMENTARITY')
    await d.send('b');await d.expect('HEATMAP');await d.expect('Selected: Jeanne')
    assert other in d.text() and 'Playing as: Jeanne' in d.text()
    d.snapshot('09-restored-context');await d.send('q');d.save()


async def run(args):
    game,jeanne,partner=setup(args);before=game.get_world(),game.project('log')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False,mode=0o700 if args.world else 0o755)
    store=SQLiteStore(output/'world.sqlite',CommonsGame);store.initialise(game)
    command=[sys.executable,'-B','-m','commons_game','--db',str(store.path),'play']+([] if args.colour else ['--plain'])
    server=None
    if args.ttyd:
        import websockets
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        log=(output/'ttyd.log').open('w')
        import_env=dict(os.environ)
        if args.colour:import_env.pop('NO_COLOR',None)
        server=subprocess.Popen([str(args.ttyd),'-i','127.0.0.1','-p',str(port),'-W','-O',*command],cwd=ROOT,stdout=log,stderr=log,env=import_env)
        for _ in range(50):
            try:
                ws=await websockets.connect(f'ws://127.0.0.1:{port}/ws',subprotocols=['tty'],origin=f'http://127.0.0.1:{port}');break
            except OSError:await asyncio.sleep(.1)
        else:raise RuntimeError('ttyd failed to start')
        await ws.send(json.dumps({'AuthToken':'','columns':100,'rows':32}));transport=WebTerminal(ws)
    else:transport=PTY(command,colour=args.colour)
    driver=Driver(transport,output)
    try:await exercise(driver,game,jeanne,partner)
    finally:
        driver.save();await transport.close()
        if server:server.terminate();server.wait(timeout=5);log.close()
    after=store.load();assert before==(after.get_world(),after.project('log'))
    assert after.replay().project('network')==game.project('network')
    encoded=trajectory_yaml(project_trajectory(after));assert reconstruct(load_trajectory_yaml(encoded)).get_world()==game.get_world()
    (output/'trajectory.yaml').write_text(encoded)
    colour_seen=b'48;5;' in driver.raw
    if args.colour:assert colour_seen,'No 256-colour heatmap backgrounds were rendered'
    result={'source':'private existing world clone' if args.world else 'fictional fixture',
            'transport':'ttyd' if args.ttyd else 'local PTY','playing_actor':'Jeanne','participants':len(people(game.get_world())),
            'existing_contracts':len(game.get_world()['agreements']),'world_and_log_unchanged':True,
            'bidirectional_inspection':True,'hack_network':True,'scenario_navigation':True,'back_restored_context':True,
            'heatmap_colour_verified':colour_seen,'replay_and_trajectory':True}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if args.world:
        for path in output.iterdir():
            if path.is_file():path.chmod(0o600)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--world',type=Path,help='Explicit existing private world to clone, never change')
    parser.add_argument('--ttyd',type=Path)
    parser.add_argument('--colour',action='store_true',help='Require real colour backgrounds rather than the monochrome fallback')
    asyncio.run(run(parser.parse_args()))
