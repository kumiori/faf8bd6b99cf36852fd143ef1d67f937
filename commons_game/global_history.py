"""History navigation and filters over the current authoritative log."""

import json
from dataclasses import replace

from game_gamer.projections.history import (
    HistoryFilters,
    event_summary,
    history_rows,
    instant,
)
from game_gamer.runtime.curation_requests import records
from game_gamer.tui.history import detail_level, detail_lines, overview
from game_gamer.tui.i18n import current_language
from game_gamer.tui.screen import Screen

from .i18n import t


def label(app, key):
    if key == 'system':
        return t('history.system')
    definition = app.world()['configuration'].get(key, {})
    if definition.get('kind') == 'mission_definition':
        return key + ' · ' + definition['title']
    if definition.get('kind') == 'mission_contribution':
        return definition['id']
    request = records(app.world()).get(key)
    if request:
        return t('history.curation_request')+app.label(request['target_id'])
    return app.label(key) if any(key in table for table in app.world().values()) else key


def settings(route):
    return route.extra.setdefault('history_settings', {'level': 0})


def rows(app, filters=HistoryFilters()):
    key = ('history_rows', filters)
    if key not in app._projection_cache:
        app._projection_cache[key] = history_rows(app._projection_cache['history_events'], filters)
    return app._projection_cache[key]


def details(app, row, level):
    key = ('history_detail', row['event']['id'], level, current_language())
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
        return Screen(t('history.views.historical_object')+label(app, route.target),
                      [t('history.views.recorded_state_after_event', sequence=sequence), t('history.views.read_only')]+
                      json.dumps(record, ensure_ascii=False, indent=2).splitlines(),
                      footer=t('history.views.pgup_pgdn_scroll_b_event'), scroll=route.scroll)
    if route.kind == 'history_event':
        event = next(event for event in events if event['sequence'] == route.extra['sequence'])
        row = event_summary(event)
        entries = [(label(app, ident), ident) for ident in row['affected_ids']]
        return Screen(t('history.views.history_event')+detail_level(level), details(app, row, level),
                      entries, t('history.views.detail_enter_affected_object_b'), route.index, route.scroll,
                      wrap_entries=True)
    filters = route.extra.get('history_filters', HistoryFilters(object_id=route.target))
    selected_rows = rows(app, filters)
    route.index = min(route.index, max(0, len(selected_rows)-1))
    if 'history_anchor' in route.extra:
        anchor = route.extra.pop('history_anchor')
        route.index = next((i for i, row in enumerate(selected_rows) if row['event']['sequence'] == anchor),
                           route.index)
    active = [key.replace('_id', '') for key, value in vars(filters).items() if value is not None]
    lines = [t('history.views.events_filters', selected_rows_count=len(selected_rows), detail_levels=detail_level(level))+(', '.join(active) or t('history.views.all_collective_events'))]
    if selected_rows and level >= 1:
        lines += details(app, selected_rows[route.index], level)
    entries = [(f"{row['event']['sequence']:03} · "+overview(row, lambda key: label(app, key)),
                row['event']['sequence']) for row in selected_rows]
    return Screen(t('line.cmd_history.history')+(t('history.views.object') if route.target else t('history.views.collective'))+' / '+detail_level(level), lines, entries,
                  t('history.views.detail_f_filters_enter_event'), route.index, route.scroll, wrap_entries=True)


def filter_history(app, screen):
    route = app.route
    filters = route.extra.get('history_filters', HistoryFilters(object_id=route.target))
    field = app.choose(t('history.filters.history_filter'), ['actor_id', 'object_id', 'action', 'mission_id', 'since', 'until', 'clear'],
                       lambda name: {'since': t('history.filters.from_time'), 'until': t('history.filters.until_time'), 'clear': t('history.filters.clear_all')}.get(
                           name, name.replace('_id', '').title()))
    if field == 'clear':
        updated = HistoryFilters()
    elif field in {'since', 'until'}:
        value = app.read(t('history.filters.iso_timestamp_with_timezone_blank'))
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
        chosen = app.choose(t('history.filters.choose_history')+field.replace('_id', '').upper(), [None, *values],
                            lambda value: t('controls.all') if value is None else value if field == 'action' else label(app, value))
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
