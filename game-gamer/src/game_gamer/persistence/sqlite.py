"""Authoritative command transactions: reload, resolve and append under one lock."""
from contextlib import closing
import json
import sqlite3
from pathlib import Path
from threading import RLock


class SQLiteStore:
    def __init__(self, path, engine_type):
        self.path = Path(path)
        self.engine_type = engine_type
        self._cached = None
        self._cache_lock = RLock()

    def initialise(self, game):
        from .log import save_log
        save_log(self.path, game.project('log'))

    def _restore(self, entries):
        # Read and compare the complete stored prefix before reusing its validated snapshot.
        with self._cache_lock:
            cached = self._cached
            if cached is not None and entries[:cached.revision] == cached._log:
                game = cached.snapshot()
                game._replay_events(entries[cached.revision:])
            else:
                game = self.engine_type.from_log(entries)
            if cached is None or cached._log != entries:
                self._cached = game.snapshot()
            return game

    def load(self):
        from .log import load_log
        return self._restore(load_log(self.path))

    def revision(self):
        if not self.path.is_file():
            raise ValueError('game_not_started')
        with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            return connection.execute('SELECT COALESCE(MAX(sequence), 0) FROM events').fetchone()[0]

    def submit(self, command, *, expected_version=None):
        return self.transact(lambda game: game.submit(command), command=command,
                             expected_version=expected_version)

    def transact(self, operation, *, command=None, expected_version=None):
        """Trusted local operations share the command lock and append-only log.

        This Python boundary is not exposed to remote players. Imports and pending
        identity requests use it without creating a separately authoritative store.
        """
        if not self.path.is_file():
            raise ValueError('game_not_started')
        with closing(sqlite3.connect(self.path, timeout=15)) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            entries = [json.loads(row[0]) for row in connection.execute(
                'SELECT payload FROM events ORDER BY sequence')]
            game = self._restore(entries)
            # Exact retries remain idempotent even if the caller's version is stale.
            prior = game._prior(command) if isinstance(command, dict) else None
            if expected_version is not None and expected_version != len(entries) and not prior:
                return {'ok': False, 'errors': ['stale_version'], 'mutations': [],
                        'version': len(entries)}
            result = operation(game)
            new_entries = []
            if result['ok']:
                new_entries = game.project('log')[len(entries):]
                connection.executemany('INSERT INTO events VALUES (?, ?)', [
                    (entry['sequence'], json.dumps(entry, sort_keys=True, ensure_ascii=False))
                    for entry in new_entries])
            return {**result, 'version': len(entries) + len(new_entries)}
