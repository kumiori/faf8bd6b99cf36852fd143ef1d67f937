"""Detached, filterable views of the authoritative event history."""
from dataclasses import dataclass
from datetime import datetime

from ..model import require

DETAIL_LEVELS = ('Overview', 'Detailed', 'Technical')


@dataclass(frozen=True)
class HistoryFilters:
    actor_id: str | None = None
    object_id: str | None = None
    action: str | None = None
    mission_id: str | None = None
    since: str | None = None
    until: str | None = None


def instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        require(parsed.tzinfo is not None, 'history_time_requires_timezone')
        return parsed
    except (TypeError, ValueError):
        raise ValueError('history_time_requires_timezone') from None


def event_summary(event):
    command = event.get('command') or {}
    affected = []
    missions = []
    changes = []
    request_status = None
    for mutation in event['mutations']:
        before, after = mutation['before'], mutation['after']
        if mutation['entity_type'] != 'action':
            affected.append(mutation['entity_id'])
        if mutation['entity_type'] == 'action':
            affected.extend(after.get('target_ids', []))
        if after.get('objective_id'):
            missions.append(after['objective_id'])
        if mutation['entity_type'] == 'objective':
            missions.append(mutation['entity_id'])
        if mutation['entity_id'] == 'curation-requests':
            request_id = command.get('request_id')
            request = after['requests'].get(request_id) if request_id else next(
                (row for row in after['requests'].values() if row['history'][-1]['action_id'] == event['action_id']), None)
            if request:
                request_status = request['status']
        fields = [key for key, value in after.items() if before is None or before.get(key) != value]
        if mutation['entity_type'] != 'action':
            changes.append({'id': mutation['entity_id'], 'type': mutation['entity_type'],
                            'fields': fields, 'before_status': (before or {}).get('status'),
                            'after_status': after.get('status'), 'outcome': after.get('outcome_status'),
                            'values': {key: {'before': (before or {}).get(key), 'after': after[key]} for key in fields}})
    affected.extend(command[key] for key in ('target_id', 'source_id', 'agreement_id', 'invitation_id',
                                              'resource_id', 'request_id', 'related_id') if command.get(key))
    if command.get('objective_id'):
        missions.append(command['objective_id'])
    return {'event': event, 'actor_id': event['actor_id'], 'action': command.get('kind') or event['kind'],
            'affected_ids': list(dict.fromkeys(affected)), 'mission_ids': list(dict.fromkeys(missions)),
            'changes': changes, 'request_status': request_status}


def history_rows(events, filters=HistoryFilters()):
    since = instant(filters.since) if filters.since else None
    until = instant(filters.until) if filters.until else None
    require(since is None or until is None or since <= until, 'history_time_range_reversed')
    result = []
    for event in events:
        row = event_summary(event)
        if filters.actor_id and row['actor_id'] != filters.actor_id:
            continue
        if filters.object_id and filters.object_id not in row['affected_ids']:
            continue
        if filters.action and row['action'] != filters.action:
            continue
        if filters.mission_id and filters.mission_id not in row['mission_ids']:
            continue
        timestamp = instant(event['occurred_at'])
        if since and timestamp < since or until and timestamp > until:
            continue
        result.append(row)
    return result


def overview(row, label):
    from ..tui.history import overview as render
    return render(row, label)


def detail_lines(row, level, label):
    from ..tui.history import detail_lines as render
    return render(row, level, label)
