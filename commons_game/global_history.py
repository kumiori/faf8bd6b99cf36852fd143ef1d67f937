"""History navigation and filters over the current authoritative log."""
from dataclasses import replace
import json

from game_gamer.projections.history import HistoryFilters, DETAIL_LEVELS, history_rows, event_summary, overview, detail_lines, instant
from game_gamer.runtime.curation_requests import records
from game_gamer.tui.screen import Screen


def label(app, key):
    if key == 'system':
        return 'System'
    request = records(app.world()).get(key)
    if request:
        return 'Curation request · '+app.label(request['target_id'])
    return app.label(key) if any(key in table for table in app.world().values()) else key


def settings(route):
    return route.extra.setdefault('history_settings', {'level': 0})


def rows(app, filters=HistoryFilters()):
    key = ('history_rows', filters)
    if key not in app._projection_cache:
        app._projection_cache[key] = history_rows(app._projection_cache['history_events'], filters)
    return app._projection_cache[key]


def details(app, row, level):
    key = ('history_detail', row['event']['id'], level)
    if key not in app._projection_cache:
        app._projection_cache[key] = detail_lines(row, level, lambda ident: label(app, ident))
    return app._projection_cache[key]


def history_screen(app):
    route = app.route
    config = settings(route)
    level = config['level']
    if 'history_events' not in app._projection_cache:
        app._projection_cache['history_events'] = app.current().project('log')
    events = app._projection_cache['history_events']
    if route.kind == 'history_object':
        sequence = route.extra['sequence']
        world = app.current().world_at(event=sequence)
        request = records(world).get(route.target)
        record = request or next((table[route.target] for table in world.values() if route.target in table), None)
        return Screen('HISTORICAL OBJECT / '+label(app, route.target),
                      [f'Recorded state after event {sequence}', 'Read-only']+
                      json.dumps(record, ensure_ascii=False, indent=2).splitlines(),
                      footer='PgUp/PgDn Scroll · b Event', scroll=route.scroll)
    if route.kind == 'history_event':
        event = next(event for event in events if event['sequence'] == route.extra['sequence'])
        row = event_summary(event)
        entries = [(label(app, ident), ident) for ident in row['affected_ids']]
        return Screen('HISTORY / EVENT / '+DETAIL_LEVELS[level], details(app, row, level),
                      entries, '+/- Detail · Enter Affected object · b History', route.index, route.scroll,
                      wrap_entries=True)
    filters = route.extra.get('history_filters', HistoryFilters(object_id=route.target))
    selected_rows = rows(app, filters)
    route.index = min(route.index, max(0, len(selected_rows)-1))
    if 'history_anchor' in route.extra:
        anchor = route.extra.pop('history_anchor')
        route.index = next((i for i, row in enumerate(selected_rows) if row['event']['sequence'] == anchor),
                           route.index)
    active = [key.replace('_id', '') for key, value in vars(filters).items() if value is not None]
    lines = [f"{len(selected_rows)} events · {DETAIL_LEVELS[level]} · Filters: "+(', '.join(active) or 'All collective events')]
    if selected_rows and level >= 1:
        lines += details(app, selected_rows[route.index], level)
    entries = [(f"{row['event']['sequence']:03} · "+overview(row, lambda key: label(app, key)),
                row['event']['sequence']) for row in selected_rows]
    return Screen('HISTORY / '+('OBJECT' if route.target else 'COLLECTIVE')+' / '+DETAIL_LEVELS[level], lines, entries,
                  '+/- Detail · f Filters · Enter Event · b Back', route.index, route.scroll, wrap_entries=True)


def filter_history(app, screen):
    route = app.route
    filters = route.extra.get('history_filters', HistoryFilters(object_id=route.target))
    field = app.choose('HISTORY FILTER', ['actor_id', 'object_id', 'action', 'mission_id', 'since', 'until', 'clear'],
                       lambda name: {'since': 'From time', 'until': 'Until time', 'clear': 'CLEAR ALL'}.get(
                           name, name.replace('_id', '').title()))
    if field == 'clear':
        updated = HistoryFilters()
    elif field in {'since', 'until'}:
        value = app.read('ISO timestamp with timezone (blank clears)')
        if value:
            instant(value)
        updated = replace(filters, **{field: value or None})
    else:
        available = rows(app)
        if field == 'actor_id':
            values = sorted({row['actor_id'] for row in available})
        elif field == 'action':
            values = sorted({row['action'] for row in available})
        else:
            values = sorted({ident for row in available for ident in row['mission_ids' if field == 'mission_id' else 'affected_ids']})
        chosen = app.choose('CHOOSE HISTORY '+field.replace('_id', '').upper(), [None, *values],
                            lambda value: 'All' if value is None else value if field == 'action' else label(app, value))
        updated = replace(filters, **{field: chosen})
    rows(app, updated)
    if screen.entries:
        route.extra['history_anchor'] = screen.entries[route.index][1]
    route.extra['history_filters'] = updated
    route.scroll = 0


def history_key(app, key, screen):
    route = app.route
    if key in {'+', '-'} and route.kind != 'history_object':
        config = settings(route)
        config['level'] = min(2, max(0, config['level']+(1 if key == '+' else -1)))
        return True
    if key == 'f' and route.kind == 'history':
        filter_history(app, screen)
        return True
    if key == 'enter' and screen.entries:
        if route.kind == 'history':
            sequence = screen.entries[route.index][1]
            app.push('history_event', sequence=sequence, at=sequence, history_settings=settings(route))
        elif route.kind == 'history_event':
            app.push('history_object', screen.entries[route.index][1], sequence=route.extra['sequence'], at=route.extra['sequence'])
        return True
    return False
