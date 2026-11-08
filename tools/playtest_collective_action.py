"""Fictional dual-pathway acceptance in a real terminal or loopback ttyd.

No source IDs are typed. Captures, saved state and native trajectory exports go
into a fresh explicit output directory. No live saved world is opened.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from playtest_matrix import Driver,PTY,WebTerminal,fictional_world
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.expertise import matrix
from commons_game.trajectory import project_trajectory,trajectory_yaml,load_trajectory_yaml,reconstruct


async def player(d,name):
    await d.send('p');await d.expect('WHO WILL YOU PLAY?');await d.choose(name)
    await d.expect('Playing as: '+name)


async def agreement(d,title,other,offered,requested):
    for prompt,value in [('Contract title?',title),('Purpose of this agreement?','Explore a common learning project'),
        ('Your offered contribution?',offered),('Contribution requested from '+other+'?',requested),('Optional conditions','')]:
        await d.answer(prompt,value)
    await d.expect('AGREEMENT SETTINGS');await d.enter()
    await d.answer('Continue?','y');await d.expect('POTENTIAL COMPLEMENTARITY')
    await d.enter();await d.expect('CONTRACT INSPECTOR')


async def exercise(d):
    await d.expect('SADDLE PATHWAYS');d.snapshot('01-splash');await d.enter()
    await d.expect('WHO WILL YOU PLAY?');await d.choose('Alex')
    await d.expect('CHOOSE YOUR PATH');await d.enter();await d.expect('HEATMAP')
    await d.send('O');await d.expect('OFFERS O');d.snapshot('02-offers')
    await d.enter();await d.expect('DECLARED OFFER');await d.send('b')
    await d.send('N');await d.expect('NEEDS N');d.snapshot('03-needs')
    await d.send('W');await d.expect('COMPLEMENTARITY MATRIX')
    await d.send('\x1bOC');await d.expect('Selected: Alex -> Casey');await d.enter()
    await d.expect('POTENTIAL COMPLEMENTARITY');await d.expect('Reverse: Casey');d.snapshot('04-potential')
    await d.send('j');await d.answer('Invitation message?','Could we explore a learning exchange?')
    await d.answer('Optional invitation purpose','Learn together')
    await d.expect('INVITATION DELIVERY');await d.enter();await d.answer('Continue?','y')
    await d.expect('INVITATION SENT');d.snapshot('05-invitation-sent')
    await player(d,'Casey');await d.send('i');await d.expect('INBOX / INVITATIONS AND CONTRACTS');d.snapshot('06-incoming')
    await d.enter();await d.expect('INVITATION / CONNECT')
    await d.send('y');await d.answer('Optional response message','Happy to explore');await d.answer('Continue?','y')
    await d.expect('Connection acknowledged');d.snapshot('07-contact-accepted')
    await d.send('w');await d.expect('HACK RENDERER');await d.expect('Showing ')
    await d.send('S');await d.expect('NETWORK SCOPE');await d.choose('Invitation and connection network')
    await d.expect('Scope: Invitation and connection network');d.snapshot('08-connection-network')
    await d.send('\t');await d.expect('NETWORK / OBJECT LIST')
    await d.enter();await d.expect('INSPECT / PERSON')
    await d.send('b');await d.expect('NETWORK / OBJECT LIST')
    await d.expect('Scope: Invitation and connection network')
    await d.send('\t');await d.expect('HACK RENDERER')
    await d.send('3');await d.send('r');await d.send('}');await d.expect('EXPERIMENTAL 3D');d.snapshot('09-experimental-camera')
    await d.send('3');await d.send('b');await d.expect('INVITATION / CONNECT')
    # Pending decisions have gone; sender, recipient, then direct proposal link.
    await d.send('3')
    await agreement(d,'Learning exchange','Alex','Offer a workshop','Review a policy')
    await d.expect('DECISIONS');await d.expect('EXPLORE')
    await d.send('y');await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR')
    await player(d,'Alex');await d.send('j')
    for prompt,value in [('Revised shared purpose?','Learn through a jointly reviewed workshop'),
        ('Proposed contribution from Casey?','Deliver a workshop'),('Proposed contribution from Alex?','Review a policy'),
        ('Conditions for this revision?','Both parties review the common version')]:
        await d.answer(prompt,value)
    await d.answer('Continue?','y');await d.expect('Terms version: 2');d.snapshot('10-negotiated')
    await d.send('y');await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR')
    await player(d,'Casey');await d.send('y');await d.answer('Continue?','y')
    await d.expect('Status: ACCEPTED');await d.expect('Outcome: UNVERIFIED');d.snapshot('11-accepted-contract')
    await d.send('h');await d.expect('HISTORY /');d.snapshot('12-history')
    await d.send('b');await d.send('x');await d.expect('ECOSYSTEM VIEWS');await d.choose('Matrix')
    await d.expect('COMPLEMENTARITY MATRIX')
    # Independent alternative: Alex -> Morgan, with no invitation or connection.
    await player(d,'Alex')
    await d.send('/');await d.answer('Search by first name','Morgan');await d.expect('FIND MATRIX PARTICIPANT');await d.enter()
    await d.send('o');await d.expect('Selected: Alex -> Morgan');await d.enter();await d.expect('POTENTIAL COMPLEMENTARITY')
    await d.send('k')
    await agreement(d,'Direct agreement','Morgan','Offer a second review','Review a direct proposal')
    await d.send('y');await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR')
    await player(d,'Morgan');await d.send('i');await d.expect('INBOX / INVITATIONS AND CONTRACTS');d.snapshot('13-direct-proposal-inbox')
    await d.enter();await d.expect('CONTRACT INSPECTOR');await d.expect('Direct agreement')
    await d.send('y');await d.answer('Continue?','y');await d.expect('Status: ACCEPTED');d.snapshot('14-direct-accepted')
    await d.send('w');await d.expect('HACK RENDERER');await d.expect('Showing ');d.snapshot('15-final-network')
    await d.send('t');await d.expect('RECORDED TRAJECTORY');await d.send('v');await d.expect('Replay consistent: True')
    d.snapshot('16-replay');await d.send('q');d.save()


async def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    store=SQLiteStore(output/'world.sqlite',CommonsGame);store.initialise(fictional_world(third_needs=['x']))
    command=[sys.executable,'-B','-m','commons_game','--db',str(store.path),'play','--plain']
    server=None;connection=None
    async def transport():
        if not args.ttyd:return PTY(command)
        import websockets
        for _ in range(50):
            try:
                ws=await websockets.connect(f'ws://127.0.0.1:{port}/ws',subprotocols=['tty'],origin=f'http://127.0.0.1:{port}')
                await ws.send(json.dumps({'AuthToken':'','columns':100,'rows':32}));return WebTerminal(ws)
            except OSError:await asyncio.sleep(.1)
        raise RuntimeError('ttyd failed to start')
    if args.ttyd:
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        log=(output/'ttyd.log').open('w')
        server=subprocess.Popen([str(args.ttyd),'-i','127.0.0.1','-p',str(port),'-W','-O',*command],cwd=ROOT,stdout=log,stderr=log)
    port_transport=await transport();d=Driver(port_transport,output)
    try:
        await exercise(d);await port_transport.close()
        restart_output=output/'restart';restart_output.mkdir()
        port_transport=await transport();restart=Driver(port_transport,restart_output)
        await restart.expect('SADDLE PATHWAYS');await restart.enter()
        await restart.expect('WHO WILL YOU PLAY?');await restart.choose('Alex')
        await restart.expect('CHOOSE YOUR PATH');await restart.enter();await restart.send('i')
        await restart.expect('INBOX / INVITATIONS AND CONTRACTS');await restart.expect('Outcome unverified')
        restart.snapshot('17-restarted-inbox');await restart.send('q');restart.save()
    finally:
        d.save();await port_transport.close()
        if server:server.terminate();server.wait(timeout=5);log.close()
    game=store.load();world=game.get_world();invites=[r for r in world['relationships'].values() if r['kind']=='contact_invitation']
    assert len(invites)==1 and invites[0]['status']=='accepted'
    assert len(world['agreements'])==2 and all(a['status']=='accepted' and a['outcome_status']=='unverified' for a in world['agreements'].values())
    assert sorted(a['current_version'] for a in world['agreements'].values())==[1,2]
    assert game.replay().get_world()==world
    encoded=trajectory_yaml(project_trajectory(game));(output/'trajectory.yaml').write_text(encoded)
    assert reconstruct(load_trajectory_yaml(encoded)).get_world()==world
    result={'transport':'ttyd' if args.ttyd else 'PTY','fictional_only':True,'invitation_path':True,'independent_direct_path':True,
            'contracts':2,'accepted_contact_invitations':1,'matrix_switching':True,'network_scope_and_3d':True,
            'restart':True,'replay_and_native_trajectory':True,'state_version':len(game.project('log'))}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ttyd',type=Path);asyncio.run(run(parser.parse_args()))
