"""Loopback-only local play; simulated actor sessions, never production identity."""

import json
import re
import secrets
import threading
from functools import partial
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from game_gamer.tui.i18n import current_language, using_language

from commons_engine.store import SQLiteStore

from .engine import CommonsGame
from .i18n import browser_messages, t
from .scenario import SCENARIOS, definition, load_scenario

# Empirical play is terminal-only until the browser supports its onboarding and
# free proposals. Preserve the three existing browser fixtures and their flows.
BROWSER_SCENARIOS = tuple(name for name in SCENARIOS if definition(name)['proposal'] is not None)

WEB_ROOT = Path(__file__).parent / 'web'
PAGE_SLOT = re.compile(r'\{\{([a-z][a-z0-9_.-]*)\}\}')


def render_page(language):
    with using_language(language):
        def replace_slot(match):
            key = match[1]
            if key == 'lang':
                value = current_language()
            elif key.startswith('scenario.'):
                value = definition(key.removeprefix('scenario.'))['title']
            elif key == 'branding.title':
                first, separator, rest = t('branding.title').partition(' ')
                return escape(first) + ('<br><em>' + escape(rest) + '</em>' if separator else '')
            else:
                value = t(key)
            return escape(value)

        return PAGE_SLOT.sub(replace_slot, (WEB_ROOT / 'index.html').read_text(encoding='utf-8'))


class CommonsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions = {}
        self.session_lock = threading.Lock()
        for name in BROWSER_SCENARIOS:
            store = SQLiteStore(self.data_dir / f'{name}.sqlite', CommonsGame)
            if not store.path.exists():
                store.initialise(load_scenario(name))
        super().__init__(address, partial(Handler, directory=str(WEB_ROOT)))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        super().end_headers()

    def reply(self, value, status=200, cookie=None):
        payload = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)

    def selected_store(self, name):
        if name not in BROWSER_SCENARIOS:
            raise ValueError('unknown_scenario')
        return SQLiteStore(self.server.data_dir / f'{name}.sqlite', CommonsGame)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path in {'/', '/index.html', '/api/i18n'}:
            language = parse_qs(parsed.query).get('lang', [current_language()])[0]
            if parsed.path == '/api/i18n':
                return self.reply(browser_messages(language))
            payload = render_page(language).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif parsed.path == '/api/state':
            try:
                scenario = parse_qs(parsed.query).get('scenario', ['bilateral-logs'])[0]
                game = self.selected_store(scenario).load()
                self.reply({'ok': True, **game.project('now'), 'scenarios': list(BROWSER_SCENARIOS),
                            'commits': game.project('log')})
            except ValueError as error:
                self.reply({'ok': False, 'errors': [str(error)]}, 400)
        elif parsed.path.startswith('/api/'):
            self.reply({'ok': False, 'errors': ['not_found']}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        # Browser writes must originate in this loopback application.
        expected_origin = f'http://{self.headers.get("Host")}'
        if self.headers.get('Origin') != expected_origin:
            return self.reply({'ok': False, 'errors': ['same_origin_required']}, 403)
        if self.headers.get_content_type() != 'application/json':
            return self.reply({'ok': False, 'errors': ['json_required']}, 415)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                raise ValueError('invalid_body_size')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('invalid_body')
            scenario = body.get('scenario', 'bilateral-logs')
            store = self.selected_store(scenario)
            if self.path == '/api/session':
                actor = body.get('actor')
                if actor not in store.load().get_world()['actors']:
                    raise ValueError('unknown_actor')
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                with self.server.session_lock:
                    self.server.sessions[token] = {'actor': actor, 'scenario': scenario, 'csrf': csrf}
                self.reply({'ok': True, 'actor': actor, 'csrf': csrf, 'session_token': token,
                            'identity_method': 'local_simulated_identity'})
            elif self.path == '/api/command':
                with self.server.session_lock:
                    session = self.server.sessions.get(self.headers.get('X-Actor-Session', ''))
                if not session or session['scenario'] != scenario or self.headers.get('X-CSRF-Token') != session['csrf']:
                    return self.reply({'ok': False, 'errors': ['session_required']}, 403)
                command = body.get('command')
                if not isinstance(command, dict):
                    raise ValueError('invalid_command')
                if command.get('actor', session['actor']) != session['actor']:
                    return self.reply({'ok': False, 'errors': ['actor_mismatch']}, 403)
                result = store.submit({**command, 'actor': session['actor']}, expected_version=body.get('expected_version'))
                self.reply(result, 200 if result['ok'] else 409)
            else:
                self.reply({'ok': False, 'errors': ['not_found']}, 404)
        except (ValueError, TypeError, KeyError) as error:
            self.reply({'ok': False, 'errors': [str(error)]}, 400)


def serve(port=8765, data_dir='.commons-worlds'):
    with CommonsServer(('127.0.0.1', port), data_dir) as server:
        print(t('web.server.url', port=server.server_port), flush=True)
        print(t('web.server.local_only'), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
