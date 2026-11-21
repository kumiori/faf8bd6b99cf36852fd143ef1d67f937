"""Read-only Notion snapshots → conservative, replayable Commons assertions."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from uuid import UUID

from game_gamer.runtime.reconstruction import CLAIM_KINDS

from .engine import digest, instant, text
from .model import Actor, Resource, require
from dataclasses import asdict

SCHEMA = 'saddle-ecosystem-snapshot/v1'
KINDS = {'person': 'actors', 'organisation': 'actors', 'relationship': 'relationships',
         'affiliation': 'relationships', 'capacity': 'capacities', 'need': 'needs', 'resource': 'resources'}
FIELDS = {'person': {'label'}, 'organisation': {'label'},
          'relationship': {'source_id', 'target_id', 'relation', 'directed'},
          'affiliation': {'source_id', 'target_id'},
          'capacity': {'actor_id', 'domain', 'quantity', 'unit'},
          'need': {'actor_id', 'domain', 'quantity', 'unit'},
          'resource': {'owner_id', 'label', 'quantity', 'unit'}}


def source_id(kind, data_source_id, record_id):
    """Source identity, never a display-name join."""
    return 'notion:' + kind + ':' + digest([data_source_id, record_id])[:24]


def property_value(prop):
    # Same conservative property boundary as app_protocol_hack's normaliser.
    kind = prop.get('type')
    value = prop.get(kind)
    if kind in {'title', 'rich_text'}:
        return ''.join(x.get('plain_text') or x.get('text', {}).get('content', '') for x in value or [])
    if kind in {'select', 'status'}:
        return value.get('name') if value else None
    if kind == 'relation':
        return [x['id'] for x in value or []]
    return deepcopy(value)


def capture_snapshot(client, sources, *, captured_at=None):
    """Use the sibling's read-only client; persist only explicitly mapped fields.

    Mappings use {kind, data_source_id, database_id?, properties: {field: name},
    references: {field: {kind, data_source_id}}}. Full pagination is mandatory.
    """
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    instant(captured_at)
    records = []
    for spec in sources:
        kind = spec['kind']
        require(kind in KINDS and set(spec['properties']) <= FIELDS[kind], 'invalid_source_mapping')
        cursor = None; seen = set()
        while True:
            batch = client.query(spec['data_source_id'], page_size=100,
                                 **({'start_cursor': cursor} if cursor else {}))
            for page in batch['results']:
                values = {}; original = {}
                for field, name in spec['properties'].items():
                    prop = deepcopy(page.get('properties', {}).get(name, {}))
                    if prop.get('has_more') or (prop.get('type') in {'relation', 'people', 'rich_text', 'title'}
                                                and len(prop.get(prop['type'], [])) >= 25):
                        items = []; property_cursor = None; property_seen = set()
                        while True:
                            part = client.property(page['id'], prop['id'], page_size=100,
                                      **({'start_cursor': property_cursor} if property_cursor else {}))
                            items.extend(part['results'])
                            if not part.get('has_more'):
                                break
                            property_cursor = part.get('next_cursor')
                            require(property_cursor and property_cursor not in property_seen, 'invalid_property_pagination')
                            property_seen.add(property_cursor)
                        prop[prop['type']] = [item[prop['type']] for item in items]
                    value = property_value(prop)
                    original[name] = deepcopy(value)
                    if field in spec.get('references', {}):
                        require(isinstance(value, list) and len(value) == 1, 'ambiguous_source_reference')
                        ref = spec['references'][field]
                        value = source_id(ref['kind'], ref['data_source_id'], value[0])
                    values[field] = value
                records.append({'kind': kind, 'record_id': page['id'], 'data_source_id': spec['data_source_id'],
                    'database_id': spec.get('database_id'), 'created_at': page.get('created_time'),
                    'last_edited_at': page.get('last_edited_time'), 'fields': values,
                    'source_properties': original, 'epistemic_status': 'source_assertion',
                    'archived': bool(page.get('archived') or page.get('in_trash'))})
            if not batch.get('has_more'):
                break
            cursor = batch.get('next_cursor')
            require(cursor and cursor not in seen, 'invalid_source_pagination')
            seen.add(cursor)
    return {'schema_version': SCHEMA, 'world': 'Montréal Commons', 'captured_at': captured_at, 'records': records}


def sibling_client(project, token):
    """Load the independent existing transport without importing Streamlit/analysis."""
    path = Path(project) / 'temporal_graph/ingestion/notion_client.py'
    require(path.is_file(), 'read_only_notion_adapter_not_found')
    spec = importlib.util.spec_from_file_location('commons_notion_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from notion_client import Client
    return module.ReadOnlyNotionClient(Client(auth=token, notion_version='2025-09-03', timeout_ms=30000))


def connector_people_snapshot(rows, *, captured_at, data_source_id, database_id):
    """Allowlisted SQL connector export; institution text remains a source assertion.

    An organisation mentioned in a profile has no independent Notion page here.
    Give that source-local mention its own identity, without merging names across
    people or fabricating an organisation database identifier.
    """
    records = []
    for row in rows:
        page_id = str(UUID(row['url'].rstrip('/').rsplit('/', 1)[-1].split('?')[0]))
        person_id = source_id('person', data_source_id, page_id)
        common = {'data_source_id': data_source_id, 'database_id': database_id,
                  'created_at': row.get('createdTime'), 'last_edited_at': row.get('lastEditedTime'),
                  'epistemic_status': 'source_assertion'}
        records.append({**common, 'kind': 'person', 'record_id': page_id,
                        'fields': {'label': row.get('Name')}, 'source_properties': {'Name': row.get('Name')}})
        institution = row.get('institution')
        if institution:
            mention = page_id + '#institution:' + digest(institution)[:16]
            organisation_id = source_id('organisation', data_source_id, mention)
            records.append({**common, 'kind': 'organisation', 'record_id': mention,
                            'fields': {'label': institution}, 'source_properties': {'institution': institution}})
            records.append({**common, 'kind': 'affiliation', 'record_id': mention + ':affiliation',
                            'fields': {'source_id': person_id, 'target_id': organisation_id},
                            'source_properties': {'institution': institution}})
    return {'schema_version': SCHEMA, 'world': 'Montréal Commons', 'captured_at': captured_at, 'records': records}


def import_snapshot(game, snapshot):
    """Trusted local import. It cannot import agreements, roles or identity grants.

    Every accepted record and the import report enter one ordinary engine event.
    An identical snapshot is a no-op. Absence never deletes a previous assertion.
    """
    require(snapshot.get('schema_version') == SCHEMA, 'unsupported_ecosystem_snapshot')
    captured_at = snapshot['captured_at']; instant(captured_at)
    require(isinstance(snapshot.get('records'), list), 'invalid_snapshot_records')
    before = game.get_world(); after = deepcopy(before)
    report = {'ok': True, 'created': [], 'updated': [], 'skipped': [], 'rejected': []}
    bindings = before['configuration'].get('profile-sync', {}).get('bindings', {})
    actor_ids = {source_id('person', remote['data_source_id'], remote['record_id']): target
                 for target, remote in bindings.items()}
    seen = set()
    # Endpoints must resolve regardless of the ordering of snapshot records.
    require(all(isinstance(r, dict) for r in snapshot['records']), 'invalid_snapshot_record')
    records = sorted(snapshot['records'], key=lambda r: r.get('kind') not in {'person', 'organisation'})
    for raw in records:
        try:
            kind = raw['kind']; require(kind in KINDS, 'unsupported_source_kind')
            rid = source_id(kind, text(raw['data_source_id']), text(raw['record_id']))
            require(rid not in seen, 'duplicate_source_record'); seen.add(rid)
            if raw.get('archived'):
                report['skipped'].append({'id': rid, 'reason': 'archived_source_requires_review'}); continue
            fields = deepcopy(raw['fields'])
            require(isinstance(fields, dict) and set(fields) <= FIELDS[kind], 'unsupported_source_field')
            status = raw.get('epistemic_status', 'source_assertion')
            require(status in {'source_assertion', 'documented', 'inferred', 'unknown'}, 'invalid_epistemic_status')
            original = raw.get('source_properties', {})
            require(isinstance(original, dict), 'invalid_source_properties')
            # Raw properties never cross into the world: keep property names and a
            # fingerprint, while values must pass the explicit domain allowlist.
            provenance = {'kind': 'notion_snapshot', 'record_id': raw['record_id'],
                'data_source_id': raw['data_source_id'], 'database_id': raw.get('database_id'),
                'created_at': raw.get('created_at'), 'last_edited_at': raw.get('last_edited_at'),
                'captured_at': captured_at, 'epistemic_status': status,
                'property_names': sorted(original), 'source_fingerprint': digest({
                    'fields': fields, 'epistemic_status': status, 'property_names': sorted(original),
                    'created_at': raw.get('created_at'), 'last_edited_at': raw.get('last_edited_at')}),
                'import_version': SCHEMA, 'synchronisation_status': 'read_only_snapshot'}
            for value in (provenance['created_at'], provenance['last_edited_at']):
                if value:
                    require(instant(value) <= instant(captured_at), 'source_timestamp_after_capture')
            base = {'id': rid, 'provenance': provenance}
            if kind == 'person' and rid in actor_ids:
                report['skipped'].append({'id': actor_ids[rid], 'reason': 'already_bound_canonical_profile'})
                continue
            for field in ('source_id', 'target_id', 'actor_id', 'owner_id'):
                if field in fields and isinstance(fields[field], str):
                    fields[field] = actor_ids.get(fields[field], fields[field])
            if kind in {'person', 'organisation'}:
                record = asdict(Actor(**base, label=text(fields.get('label')), kind=kind))
            elif kind in {'affiliation', 'relationship'}:
                for field in ('source_id', 'target_id'):
                    require(fields.get(field) in after['actors'], 'unresolved_source_reference')
                relation = 'affiliated_with' if kind == 'affiliation' else text(fields.get('relation'))
                require(relation not in {'authorised_to_represent', 'authorized_to_represent', 'party_to', 'has_party', *CLAIM_KINDS}, 'authority_not_importable')
                record = {**base, 'source_id': fields['source_id'], 'target_id': fields['target_id'],
                    'kind': relation, 'directed': fields.get('directed'), 'status': 'inferred' if status == 'inferred' else 'reported'}
            elif kind in {'capacity', 'need'}:
                require(fields.get('actor_id') in after['actors'], 'unresolved_source_reference')
                quantity = fields.get('quantity')
                require(quantity is None or type(quantity) is int and quantity >= 0, 'invalid_quantity')
                record = {**base, 'actor_id': fields['actor_id'], 'domain': text(fields.get('domain')),
                          'quantity': quantity, 'unit': fields.get('unit'), 'status': 'inferred' if status == 'inferred' else 'reported'}
            else:
                require(fields.get('owner_id') in after['actors'], 'unresolved_source_reference')
                require(type(fields.get('quantity')) is int and fields['quantity'] >= 0, 'documented_quantity_required')
                record = asdict(Resource(**base, owner_id=fields['owner_id'], label=text(fields.get('label')),
                    quantity=fields['quantity'], unit=text(fields.get('unit')), control='external', status='reported'))
            table = KINDS[kind]; previous = after[table].get(rid)
            if previous:
                require(previous.get('provenance', {}).get('kind') == 'notion_snapshot', 'source_identity_conflict')
                require(instant(previous['provenance']['captured_at']) <= instant(captured_at), 'stale_snapshot')
                if table == 'actors':
                    # Authority is assigned by the local host, independently of source metadata.
                    record['roles'] = deepcopy(previous['roles'])
                # Identical assertion observations do not reset gameplay state.
                if previous['provenance']['source_fingerprint'] == provenance['source_fingerprint']:
                    report['skipped'].append({'id': rid, 'reason': 'unchanged'}); continue
                if table == 'resources':
                    require(not any(r['resource_id'] == rid for a in after['agreements'].values()
                        for v in a['versions'] for r in v['resources']), 'contract_resource_requires_review')
            after[table][rid] = record
            report['updated' if previous else 'created'].append(rid)
        except (ValueError, KeyError, TypeError) as error:
            report['rejected'].append({'record_id': raw.get('record_id'), 'reason': str(error)})
    snapshot_id = digest(snapshot)
    if 'expertise' in snapshot:
        from .expertise import validate_expertise
        expertise = snapshot['expertise']
        if actor_ids and isinstance(expertise, dict) and isinstance(expertise.get('participants'), dict):
            participants = {actor_ids.get(key, key): row for key, row in expertise['participants'].items()}
            require(len(participants) == len(expertise['participants']), 'duplicate_canonical_expertise_actor')
            expertise = {**expertise, 'participants': participants}
        assertions = validate_expertise(expertise, after['actors'])
        previous = before['configuration'].get('ecosystem-expertise')
        require(not previous or instant(previous['captured_at']) <= instant(captured_at), 'stale_expertise_snapshot')
        after['configuration']['ecosystem-expertise'] = {'id':'ecosystem-expertise','status':'recorded',
            'captured_at':captured_at,'assertions':assertions}
    if snapshot.get('coverage'):
        # A coverage summary contains counts/source metadata, never raw responses.
        coverage = snapshot['coverage']
        require(isinstance(coverage,dict) and all(isinstance(k,str) for k in coverage), 'invalid_source_coverage')
        after['configuration']['ecosystem-coverage'] = {'id':'ecosystem-coverage','status':'recorded',
            'snapshot_id':snapshot_id,'summary':deepcopy(coverage)}
    import_id = 'ecosystem-import:' + snapshot_id
    if import_id not in after['configuration']:
        after['configuration'][import_id] = {'id': import_id, 'status': 'recorded', 'snapshot_id': snapshot_id,
            'captured_at': captured_at, 'report': deepcopy(report)}
    if after != before:
        event = game.record_transition(before, after, 'ecosystem.imported')
        report['commit_id'] = event['commit']['id']
    return report


def import_reconstruction_sources(game, document):
    """Trusted local import. References and transcriptions are preserved verbatim."""
    from game_gamer.schema.reconstruction_sources import prepare_reconstruction_sources

    require(isinstance(document, dict) and set(document) == {'schema', 'records'}
            and document['schema'] == 'game-gamer/reconstruction-sources/v1', 'invalid_reconstruction_source_document')
    before = game.get_world()
    records = prepare_reconstruction_sources(document['records'], before['actors'].keys())
    after = deepcopy(before)
    added = []
    for ident, record in records.items():
        existing = before['evidence'].get(ident)
        if existing is not None:
            require(existing == record, 'reconstruction_source_conflict')
            continue
        require(not any(ident in table for table in before.values()), 'reconstruction_source_id_conflict')
        after['evidence'][ident] = record
        added.append(ident)
    if added:
        game.record_transition(before, after, 'reconstruction.sources_imported')
    return {'ok': True, 'imported': added, 'unchanged': len(records)-len(added)}
