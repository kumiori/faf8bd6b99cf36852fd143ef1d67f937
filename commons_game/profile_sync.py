"""Replayable profile approvals and explicitly configured Notion write-through."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from game_gamer.runtime.curation import PROFILE_FIELDS, PROFILE_TOPICS, apply_profile, canonical, profile

from .model import require
from .source_review import notion_identity


def ledger(world):
    return world['configuration'].setdefault('profile-sync', {
        'id': 'profile-sync', 'status': 'active', 'jobs': {}, 'bindings': {},
    })


def stage_approval(world, request_id):
    request = world['configuration']['curation-requests']['requests'][request_id]
    changes = request['proposed_changes']
    if not changes:
        return
    target = request['target_id']
    require(target in world['actors'] and canonical(world, target) == target, 'canonical_target_required')
    current = profile(world, target)
    require(current['status'] != 'archived', 'archived_target')
    previous = {field: deepcopy(current.get(field)) for field in changes}
    require(previous == request.get('previous_values', previous), 'profile_review_stale')
    approval = request['history'][-1]
    audit = {'actor_id': approval['actor_id'], 'reference': approval['reason'],
             'recorded_at': approval['recorded_at'], 'event_ref': approval['event_ref'],
             'requester_id': request['requester_id'], 'request_id': request_id}
    remote = notion_identity(world, target)
    if remote:
        jobs = ledger(world)['jobs']
        require(not any(job['actor_id'] == target and job['status'] != 'synced' for job in jobs.values()),
                'profile_sync_pending')
        jobs[request_id] = {'kind': 'update', 'actor_id': target, 'remote': remote,
                            'previous': previous, 'changes': deepcopy(changes), 'approval': audit,
                            'status': 'pending', 'attempts': []}
    else:
        require(current['status'] != 'provisional', 'provisional_profile_sync_required')
        apply_profile(world, target, changes, audit)


def uuid_text(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('invalid_notion_identifier') from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class NotionFailure(ValueError):
    pass


class NotionProfiles:
    def __init__(self, token, mapping):
        require(isinstance(token, str) and token.strip() and token.isascii() and token.isprintable(),
                'notion_write_token_required')
        self.data_source_id = uuid_text(mapping['data_source_id'])
        self.fields = mapping['properties']
        self.marker = mapping.get('actor_id_property')
        require(self.fields.keys() <= PROFILE_FIELDS and 'label' in self.fields, 'invalid_profile_sync_mapping')
        used = set()
        for field, spec in self.fields.items():
            expected = 'title' if field == 'label' else 'multi_select' if field in PROFILE_TOPICS else 'rich_text'
            name = spec.get('name')
            require(spec.get('type') == expected and isinstance(name, str) and bool(name.strip()) and name not in used,
                    'invalid_profile_sync_mapping')
            used.add(name)
        require(self.marker is None or isinstance(self.marker, str) and self.marker.strip() and self.marker not in used,
                'invalid_profile_sync_mapping')
        self._headers = {'Authorization': 'Bearer '+token, 'Notion-Version': '2025-09-03',
                         'Content-Type': 'application/json'}
        self._opener = build_opener(_NoRedirect)

    def request(self, method, endpoint, payload=None):
        req = Request('https://api.notion.com/v1/'+endpoint, method=method, headers=self._headers,
                      data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with self._opener.open(req, timeout=5) as response:
                return json.load(response)
        except HTTPError as error:
            raise NotionFailure(f'notion_http_{error.code}') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise NotionFailure('notion_transport_failure') from None

    def page(self, value, record_id=None):
        require(isinstance(value, dict) and value.get('object') == 'page' and not value.get('archived')
                and not value.get('in_trash'), 'notion_page_unavailable')
        parent = value.get('parent', {})
        require(parent.get('type') == 'data_source_id' and uuid_text(parent.get('data_source_id')) == self.data_source_id,
                'notion_page_outside_profile_source')
        require(record_id is None or uuid_text(value['id']) == record_id, 'notion_page_identity_mismatch')
        return value

    @staticmethod
    def value(property_, kind):
        require(isinstance(property_, dict) and property_.get('type') == kind
                and not property_.get('has_more'), 'notion_property_type_or_truncation')
        items = property_.get(kind, [])
        require(isinstance(items, list) and all(isinstance(item, dict) for item in items), 'notion_invalid_response')
        if kind == 'multi_select':
            return sorted(item['name'] for item in items)
        require(len(items) < 25 and all(item.get('type') == 'text' and not item.get('href') for item in items),
                'notion_property_type_or_truncation')
        return ''.join(item.get('plain_text', item.get('text', {}).get('content', '')) for item in items)

    @staticmethod
    def encode(kind, value):
        if kind == 'multi_select':
            return {kind: [{'name': name} for name in value or []]}
        text = value or ''
        return {kind: [{'type': 'text', 'text': {'content': text[offset:offset+2000]}}
                       for offset in range(0, len(text), 2000)]}

    def properties(self, changes):
        require(changes.keys() <= self.fields.keys(), 'notion_field_not_mapped')
        return {self.fields[field]['name']: self.encode(self.fields[field]['type'], value)
                for field, value in changes.items()}

    def values(self, page, fields):
        return {field: self.value(page['properties'].get(self.fields[field]['name'], {}), self.fields[field]['type'])
                for field in fields}

    def update(self, job):
        remote = job['remote']
        require(uuid_text(remote['data_source_id']) == self.data_source_id, 'notion_page_outside_profile_source')
        record_id = uuid_text(remote['record_id'])
        changes = job['changes']
        payload = self.properties(changes)
        current = self.values(self.page(self.request('GET', 'pages/'+record_id), record_id), changes)

        def normalise(values):
            return {field: sorted(value or []) if field in PROFILE_TOPICS else value or ''
                    for field, value in values.items()}

        desired = normalise(changes)
        if current != desired:
            require(current == normalise(job['previous']), 'notion_profile_conflict')
            result = self.page(self.request('PATCH', 'pages/'+record_id, {'properties': payload}), record_id)
            require(self.values(result, changes) == desired, 'notion_update_unconfirmed')
        return remote

    def find_created(self, actor_id):
        require(self.marker, 'notion_actor_id_property_required')
        query = {'filter': {'property': self.marker, 'rich_text': {'equals': actor_id}}, 'page_size': 2}
        response = self.request('POST', f'data_sources/{self.data_source_id}/query', query)
        matches = response['results']
        require(len(matches) <= 1 and not response.get('has_more'), 'notion_duplicate_profile')
        if not matches:
            return None
        page = self.page(matches[0])
        require(self.value(page['properties'][self.marker], 'rich_text') == actor_id, 'notion_page_identity_mismatch')
        return {'record_id': uuid_text(page['id']), 'data_source_id': self.data_source_id}

    def check_create(self, job):
        label = job['changes']['label']
        title = self.fields['label']['name']
        response = self.request('POST', f'data_sources/{self.data_source_id}/query',
                                {'filter': {'property': title, 'title': {'equals': label}}, 'page_size': 2})
        require(not response['results'] and not response.get('has_more'), 'notion_duplicate_profile')
        self.properties(job['changes'])

    def create(self, job):
        actor_id = job['actor_id']
        properties = self.properties(job['changes'])
        properties[self.marker] = self.encode('rich_text', actor_id)
        page = self.page(self.request('POST', 'pages', {
            'parent': {'type': 'data_source_id', 'data_source_id': self.data_source_id}, 'properties': properties,
        }))
        require(self.value(page['properties'][self.marker], 'rich_text') == actor_id, 'notion_page_identity_mismatch')
        return {'record_id': uuid_text(page['id']), 'data_source_id': self.data_source_id}


def _error_code(error):
    code = str(error)
    return code if code.replace('_', '').isalnum() and code.startswith(
        ('notion_', 'profile_', 'canonical_', 'invalid_notion_')) else 'notion_invalid_response'


def sync_one(store, job_id, client):
    """Run one authenticated operation with a persistent no-repost guard for creation."""
    def reserve(game):
        before = game.get_world()
        after = deepcopy(before)
        job = ledger(after)['jobs'].get(job_id)
        require(job is not None, 'unknown_profile_sync_job')
        if job['kind'] != 'create' or job['status'] == 'synced' or job.get('creation_attempted'):
            return {'ok': True, 'reserved': False}
        try:
            if client.find_created(job['actor_id']):
                return {'ok': True, 'reserved': False}
            client.check_create(job)
        except (ValueError, KeyError, TypeError) as error:
            attempt = {'attempted_at': datetime.now(timezone.utc).isoformat(), 'error': _error_code(error)}
            job['attempts'].append(attempt)
            game.record_transition(before, after, 'profile_sync.failed', actor=job['approval']['actor_id'])
            return {'ok': True, 'reserved': False, 'status': 'pending', 'job_id': job_id, **attempt}
        job['creation_attempted'] = True
        job['creation_data_source_id'] = client.data_source_id
        game.record_transition(before, after, 'profile_sync.creation_reserved', actor=job['approval']['actor_id'])
        return {'ok': True, 'reserved': True}

    reservation = store.transact(reserve)
    if 'status' in reservation:
        return reservation

    def deliver(game):
        before = game.get_world()
        after = deepcopy(before)
        state = ledger(after)
        job = state['jobs'][job_id]
        if job['status'] == 'synced':
            return {'ok': True, 'status': 'synced', 'job_id': job_id, 'duplicate': True}
        target = job['actor_id']
        audit = {'attempted_at': datetime.now(timezone.utc).isoformat()}
        try:
            require(canonical(after, target) == target and profile(after, target)['status'] != 'archived',
                    'canonical_target_required')
            if job['kind'] == 'create':
                source = job.get('creation_data_source_id')
                require(source is None or source == client.data_source_id, 'notion_page_outside_profile_source')
                remote = client.find_created(target)
                if not remote:
                    require(reservation['reserved'], 'notion_create_unconfirmed')
                    try:
                        remote = client.create(job)
                    except NotionFailure as error:
                        if str(error) in {'notion_http_400', 'notion_http_401', 'notion_http_403',
                                          'notion_http_404', 'notion_http_429'}:
                            job.pop('creation_attempted')
                            job.pop('creation_data_source_id')
                        raise
                duplicates = [ident for ident, actor in after['actors'].items() if ident != target and actor['kind'] == 'person'
                              and notion_identity(after, ident) == remote]
                require(not duplicates, 'notion_duplicate_profile')
                state['bindings'][target] = remote
            else:
                require(notion_identity(after, target) == job['remote'], 'notion_page_identity_mismatch')
                canonical_now = profile(after, target)
                require(all(canonical_now.get(key) == value for key, value in job['previous'].items()), 'profile_review_stale')
                client.update(job)
                apply_profile(after, target, job['changes'], job['approval'])
            job['status'] = 'synced'
        except (ValueError, KeyError, TypeError) as error:
            audit['error'] = _error_code(error)
            job['status'] = 'pending'
        job['attempts'].append(audit)
        game.record_transition(before, after, 'profile_sync.succeeded' if job['status'] == 'synced' else 'profile_sync.failed',
                     actor=job['approval']['actor_id'])
        return {'ok': True, 'status': job['status'], 'job_id': job_id, **audit}

    return store.transact(deliver)
