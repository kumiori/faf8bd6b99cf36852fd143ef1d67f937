"""Reproducible full-screen acceptance through a real PTY or ttyd WebSocket.

Uses fictional records only. Install the terminal-test extra for pyte/websockets.
Every command is a displayed key or choice; no internal actor/contract IDs are
entered. Terminal snapshots, keystrokes and a replayable world are retained.
"""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import struct
import subprocess
import sys
import termios
import time
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.ecosystem_import import connector_people_snapshot, import_snapshot, source_id
from commons_game.expertise import SCHEMA
from commons_game.trajectory import load_trajectory_yaml, project_trajectory, reconstruct, trajectory_yaml


def fictional_world(*, names=('Alex Example','Casey Example','Morgan Example'), third_needs=None):
    snapshot = connector_people_snapshot([
        {'url':'https://app.notion.com/'+str(UUID(int=i)), 'Name':name, 'institution':'Fictional Research Commons'}
        for i, name in enumerate(names, 1)],
        captured_at='2026-11-04T00:00:00+00:00',data_source_id='fictional-people',database_id='fictional-people')
    participants = {}
    for i, (offers, needs) in enumerate(((['x'], ['y']), (['y'], ['x']), ([], third_needs)), 1):
        actor = source_id('person', 'fictional-people', str(UUID(int=i))); profile = {}
        for side, codes in (('offer', offers), ('need', needs)):
            profile[side] = {'state':'answered' if codes is not None else 'skipped','codes':codes or [],'unmapped_count':0,
                'source':{'data_source_id':'fictional-responses','record_id':f'fictional-response-{i}',
                          'field':'knowledge_'+side,'captured_at':snapshot['captured_at']}}
            for code in codes or []:
                snapshot['records'].append({'kind':'capacity' if side=='offer' else 'need',
                    'data_source_id':'fictional-responses','record_id':f'{i}:{side}:{code}',
                    'fields':{'actor_id':actor,'domain':{'x':'Data stewardship','y':'Coalition building'}[code],
                              'quantity':None,'unit':'declared knowledge domain'}})
        participants[actor] = profile
    snapshot['expertise'] = {'schema_version':SCHEMA,'source_version':'fictional-matrix-playtest/v1',
        'vocabulary':{'x':'Data stewardship','y':'Coalition building'},'participants':participants}
    game = load_scenario('montreal-commons');assert not import_snapshot(game,snapshot)['rejected']
    return game


class PTY:
    def __init__(self, command, *, colour=False):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',32,100,0,0))
        import_env={**os.environ,'TERM':'xterm-256color','LC_ALL':'en_US.UTF-8'}
        if colour:import_env.pop('NO_COLOR',None)
        self.process = subprocess.Popen(command,stdin=slave,stdout=slave,stderr=slave,cwd=ROOT,
            env=import_env,start_new_session=True)
        os.close(slave)

    async def send(self, value): os.write(self.master,value)

    async def receive(self):
        def read():
            if select.select([self.master],[],[],.1)[0]:
                try: return os.read(self.master,65536)
                except OSError: return b''
            return b''
        return await asyncio.to_thread(read)

    async def resize(self, width, height):
        fcntl.ioctl(self.master,termios.TIOCSWINSZ,struct.pack('HHHH',height,width,0,0))
        os.kill(self.process.pid,signal.SIGWINCH)

    async def close(self):
        try: self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        os.close(self.master)


class WebTerminal:
    def __init__(self, socket): self.socket=socket
    async def send(self, value): await self.socket.send(b'0'+value)
    async def receive(self):
        from websockets.exceptions import ConnectionClosed
        try:
            value = await asyncio.wait_for(self.socket.recv(),.1)
            value = value.encode() if isinstance(value,str) else value
            return value[1:] if value[:1]==b'0' else b''
        except (asyncio.TimeoutError,ConnectionClosed): return b''
    async def resize(self, width, height):
        await self.socket.send(b'1'+json.dumps({'columns':width,'rows':height}).encode())
    async def close(self): await self.socket.close()


class Driver:
    def __init__(self, transport, output):
        import pyte
        self.transport,self.output = transport,output
        self.screen=pyte.Screen(100,32);self.stream=pyte.ByteStream(self.screen)
        self.raw=bytearray();self.keys=[];self.snapshots=[]

    def text(self): return '\n'.join(self.screen.display)

    async def expect(self, value, timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            data=await self.transport.receive()
            if data: self.raw.extend(data);self.stream.feed(data)
            if value in self.text(): return
        self.save()
        raise AssertionError(f'Expected {value!r} in current viewport:\n{self.text()}')

    async def send(self, value):
        self.keys.append(value);await self.transport.send(value.encode())
        # Drain rendered diffs before evaluating the next input. This is bounded
        # transport settling, not a replacement for matching the next screen.
        deadline=time.monotonic()+.12
        while time.monotonic()<deadline:
            data=await self.transport.receive()
            if data:self.raw.extend(data);self.stream.feed(data)

    async def enter(self, value=''): await self.send(value+'\r')

    async def choose(self, query):
        await self.send('/');await self.expect('Search by name or organisation')
        await self.enter(query);await self.expect('Search: '+query)
        await self.enter()

    async def answer(self, prompt, value):
        await self.expect(prompt);await self.enter(value)

    def snapshot(self, name):
        text=self.text();self.snapshots.append(name)
        assert 'notion:person:' not in text and 'Example' not in text
        (self.output/(name+'.txt')).write_text(text+'\n')

    def save(self):
        (self.output/'terminal.ansi').write_bytes(self.raw)
        (self.output/'keys.json').write_text(json.dumps(self.keys,indent=2)+'\n')
        (self.output/'last-viewport.txt').write_text(self.text()+'\n')


async def exercise(driver):
    d=driver
    await d.expect('SADDLE PATHWAYS');d.snapshot('01-splash')
    await d.enter();await d.expect('WHO WILL YOU PLAY?');await d.choose('Alex')
    await d.expect('CHOOSE YOUR PATH');await d.enter();await d.expect('COMPLEMENTARITY MATRIX')
    await d.send('\x1bOC');await d.expect('Selected: Alex -> Casey');d.snapshot('02-matrix')
    await d.enter();await d.expect('POTENTIAL COMPLEMENTARITY');d.snapshot('03-opportunity')
    await d.send('a');await d.expect('WHAT CAN I DO?');await d.enter()
    for prompt,value in [('Contract title?','Commons learning exchange'),('Purpose of this agreement?','Exchange expertise'),
                         ('Your offered contribution?','Offer a stewardship review'),('Contribution requested from Casey?','Propose a workshop'),
                         ('Optional conditions','')]:
        await d.answer(prompt,value)
    await d.expect('AGREEMENT SETTINGS');await d.enter()
    await d.answer('Continue?','y');await d.expect('POTENTIAL COMPLEMENTARITY')
    await d.enter();await d.expect('CONTRACT INSPECTOR');d.snapshot('04-proposed')
    await d.send('a');await d.expect('WHAT CAN I DO?');await d.choose('Accept this exact version')
    await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR')
    await d.send('b');await d.expect('POTENTIAL COMPLEMENTARITY')
    await d.send('b');await d.expect('COMPLEMENTARITY MATRIX')
    await d.send('p');await d.expect('WHO WILL YOU PLAY?');await d.choose('Casey')
    await d.expect('Playing: Casey');await d.send('i');await d.expect('INBOX / INVITATIONS AND CONTRACTS');d.snapshot('05-received')
    await d.enter();await d.expect('CONTRACT INSPECTOR')
    await d.send('a');await d.expect('WHAT CAN I DO?');await d.choose('Negotiate revised terms')
    for prompt,value in [('Revised shared purpose?','Exchange expertise through a workshop'),
                         ('Proposed contribution from Alex?','Offer a stewardship review'),
                         ('Proposed contribution from Casey?','Offer a jointly planned workshop'),
                         ('Conditions for this revision?','Every party reviews the revised terms')]:
        await d.answer(prompt,value)
    await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR');d.snapshot('06-negotiated')
    await d.send('a');await d.expect('WHAT CAN I DO?');await d.choose('Accept this exact version')
    await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR')
    await d.send('p');await d.expect('WHO WILL YOU PLAY?');await d.choose('Alex')
    await d.send('a');await d.expect('WHAT CAN I DO?');await d.choose('Accept this exact version')
    await d.answer('Continue?','y');await d.expect('CONTRACT INSPECTOR');d.snapshot('07-accepted')
    await d.send('h');await d.expect('HISTORY /');d.snapshot('08-history')
    await d.enter();await d.expect('Historical view');await d.send('a');await d.expect('Historical views are read-only')
    await d.send('b');await d.expect('HISTORY /');await d.send('b');await d.expect('CONTRACT INSPECTOR')
    await d.send('t');await d.expect('RECORDED TRAJECTORY');d.snapshot('09-trajectory')
    await d.send('v');await d.expect('Replay consistent: True')
    await d.send('g');await d.expect('GATHERING / CONDITIONS');d.snapshot('10-gathering')
    await d.send('s');await d.expect('SCENARIOS / CATALOGUE');d.snapshot('11-scenarios')
    await d.send('e');await d.expect('COMPLEMENTARITY MATRIX');await d.expect('Selected: Alex -> Casey')
    await d.transport.resize(52,18);d.screen.resize(lines=18,columns=52)
    await d.expect('COMPLEMENTARITY MATRIX');d.snapshot('12-resized')
    await d.send('q');d.save()


async def main_async(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    store=SQLiteStore(output/'world.sqlite',CommonsGame);store.initialise(fictional_world())
    command=[sys.executable,'-B','-m','commons_game','--db',str(store.path),'play','--plain']
    server=None
    if args.ttyd:
        import websockets
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        log=(output/'ttyd.log').open('w')
        server=subprocess.Popen([str(args.ttyd),'-i','127.0.0.1','-p',str(port),'-W','-O',*command],cwd=ROOT,stdout=log,stderr=log)
        for attempt in range(50):
            try:
                connection=await websockets.connect(f'ws://127.0.0.1:{port}/ws',subprotocols=['tty'],origin=f'http://127.0.0.1:{port}')
                break
            except OSError: await asyncio.sleep(.1)
        else: raise RuntimeError('ttyd did not start; see its log')
        await connection.send(json.dumps({'AuthToken':'','columns':100,'rows':32}))
        transport=WebTerminal(connection)
    else:
        transport=PTY(command)
    driver=Driver(transport,output)
    try:
        await exercise(driver)
        await transport.close()
        if args.ttyd:
            connection=await websockets.connect(f'ws://127.0.0.1:{port}/ws',subprotocols=['tty'],origin=f'http://127.0.0.1:{port}')
            await connection.send(json.dumps({'AuthToken':'','columns':100,'rows':32}))
            transport=WebTerminal(connection)
        else:
            transport=PTY(command)
        restart_output=output/'restart';restart_output.mkdir()
        restart=Driver(transport,restart_output)
        await restart.expect('SADDLE PATHWAYS');await restart.enter()
        await restart.expect('WHO WILL YOU PLAY?');await restart.choose('Alex')
        await restart.expect('CHOOSE YOUR PATH');await restart.enter()
        await restart.expect('COMPLEMENTARITY MATRIX');await restart.send('c')
        await restart.expect('CONTRACT REGISTRY');await restart.expect('ACCEPTED')
        restart.snapshot('13-restarted-contracts');await restart.send('q');restart.save()
    finally:
        driver.save();await transport.close()
        if server:
            server.terminate();server.wait(timeout=5);log.close()
    game=store.load();agreements=game.project('agreements');assert len(agreements)==1
    agreement=agreements[0]
    assert agreement['status']=='accepted' and agreement['outcome_status']=='unverified'
    assert agreement['current_version']==2 and len(agreement['versions'][0]['acceptances'])==1
    assert len(agreement['versions'][1]['acceptances'])==2
    assert game.replay().project('network')==game.project('network')
    encoded=trajectory_yaml(project_trajectory(game));(output/'trajectory.yaml').write_text(encoded)
    assert reconstruct(load_trajectory_yaml(encoded)).get_world()==game.get_world()
    summary={'transport':'ttyd WebSocket' if args.ttyd else 'local PTY','snapshots':driver.snapshots,
        'contracts':len(agreements),'versions':2,'lifecycle':agreement['status'],'outcome':agreement['outcome_status'],
        'amendment_cleared_current_acceptances':True,'replay_and_trajectory':True,'restart':True,'resize':[52,18]}
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ttyd',type=Path,help='Optional real ttyd binary; otherwise a local PTY is used')
    asyncio.run(main_async(parser.parse_args()))
