from contextlib import contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from commons_game.scenario import definition, demo_commands
from commons_game.server import CommonsServer


@contextmanager
def running_server(path):
    server = CommonsServer(('127.0.0.1', 0), path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def request(server, path, body=None, session=None, origin=True):
    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    headers = {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
    if session:
        headers.update({'X-Actor-Session': session['session_token'], 'X-CSRF-Token': session['csrf']})
    connection.request('POST' if body is not None else 'GET', path,
                       body=json.dumps(body) if body is not None else None, headers=headers)
    response = connection.getresponse()
    data = response.read()
    result = (response.status, json.loads(data) if response.headers.get_content_type() == 'application/json' else data)
    connection.close()
    return result


def session_for(server, actor, scenario='bilateral-logs'):
    status, session = request(server, '/api/session', {'actor': actor, 'scenario': scenario})
    assert status == 200
    return session


def test_real_http_playthrough_persists_and_verifies(tmp_path):
    with running_server(tmp_path) as server:
        sessions = {}
        version = 1
        for command in demo_commands():
            actor = command['actor']
            sessions.setdefault(actor, session_for(server, actor))
            status, result = request(server, '/api/command', {'command': command,
                'scenario':'bilateral-logs', 'expected_version':version}, sessions[actor])
            assert status == 200, result
            assert result['commit_id'].startswith('commit_')
            version = result['version']
        status, state = request(server, '/api/state')
        assert status == 200 and state['world']['objectives']['objective-main']['status'] == 'verified'
        assert state['world']['agreements']['agreement-main']['outcome_status'] == 'verified'
        assert all(r['status'] == 'released' for r in state['world']['reservations'].values())
    with running_server(tmp_path) as restored:
        status, state = request(restored, '/api/state')
        assert status == 200 and state['version'] == version


def test_per_tab_sessions_remain_independent_and_cannot_forge_other_actors(tmp_path):
    with running_server(tmp_path) as server:
        mira = session_for(server, 'researcher')
        atlas = session_for(server, 'custodian')
        proposal = {'key':'p','kind':'propose','actor':'researcher',**definition('bilateral-logs')['proposal']}
        status, result = request(server, '/api/command', {'command':proposal}, mira)
        assert status == 200, result
        acceptance = {'key':'a','kind':'accept','agreement_id':'agreement-main','version':1}
        status, result = request(server, '/api/command', {'command':acceptance}, atlas)
        assert status == 200, result
        status, result = request(server, '/api/command', {'command':{**acceptance,'key':'forge','actor':'officer'}}, mira)
        assert status == 403 and result['errors'] == ['actor_mismatch']
        # A second tab never invalidates the first tab's selected actor session.
        status, result = request(server, '/api/command', {'command':{**acceptance,'key':'mira-accept'}}, mira)
        assert status == 200, result


def test_browser_writes_require_same_origin_session_and_csrf(tmp_path):
    with running_server(tmp_path) as server:
        status, result = request(server, '/api/session', {'actor':'researcher'}, origin=False)
        assert status == 403 and result['errors'] == ['same_origin_required']
        status, result = request(server, '/api/command', {'command':{}})
        assert status == 403 and result['errors'] == ['session_required']
        session = session_for(server, 'researcher')
        session['csrf'] = 'wrong'
        status, result = request(server, '/api/command', {'command':{}}, session)
        assert status == 403 and result['errors'] == ['session_required']


def test_splash_and_real_midi_assets_are_served(tmp_path):
    with running_server(tmp_path) as server:
        status, html = request(server, '/')
        assert status == 200 and b'I HEREBY DECLARE' in html and b'OF THE COMMONS' in html and b'SADDLE' in html and b'PATHWAYS' in html
        status, midi = request(server, '/commons.mid')
        assert status == 200 and midi[:4] == b'MThd' and midi.count(b'MTrk') == 4
        status, result = request(server, '/api/state?scenario=not-a-world')
        assert status == 400 and result['errors'] == ['unknown_scenario']


def test_browser_midi_parser_reads_the_actual_downloadable_score():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed only for browser MIDI-parser verification')
    root = Path(__file__).resolve().parents[1]
    code = '''
import {readFileSync} from 'node:fs';
import {parseMidi} from './commons_game/web/music.js';
const file=readFileSync('./commons_game/web/commons.mid');
const score=parseMidi(file.buffer.slice(file.byteOffset,file.byteOffset+file.byteLength));
if(score.notes.length!==216 || score.duration<43 || score.duration>44)throw Error('Unexpected score');
if(score.notes.some((n,i)=>i&&n.time<score.notes[i-1].time))throw Error('Unordered notes');
if(score.notes.some(n=>n.duration<=0))throw Error('Invalid note duration');
console.log(JSON.stringify({notes:score.notes.length,duration:score.duration}));
'''
    result = subprocess.run([node, '--input-type=module', '-e', code], cwd=root, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
