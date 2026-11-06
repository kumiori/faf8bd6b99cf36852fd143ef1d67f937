"""Append-only SQLite event storage. No separately persisted materialized world."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def save_log(path, entries):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        connection.execute('BEGIN IMMEDIATE')
        existing = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM events ORDER BY sequence')]
        if existing != entries[:len(existing)] or len(existing) > len(entries):
            raise ValueError('log_conflict')
        connection.executemany('INSERT INTO events VALUES (?, ?)',
                               [(e['sequence'], json.dumps(e, sort_keys=True, ensure_ascii=False))
                                for e in entries[len(existing):]])


def load_log(path):
    if not Path(path).is_file():
        raise ValueError('game_not_started')
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        return [json.loads(row[0]) for row in connection.execute('SELECT payload FROM events ORDER BY sequence')]
