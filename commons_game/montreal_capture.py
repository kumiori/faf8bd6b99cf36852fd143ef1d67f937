"""Complete scoped read-only capture, emitting only minimal ecosystem assertions."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import UUID

from .ecosystem_import import connector_people_snapshot, property_value, source_id
from .engine import digest
from .model import require
from .expertise import SCHEMA as EXPERTISE_SCHEMA
from .presentation import folded

VERSION = 'saddle-montreal-capture/v2'


def page_id(value):
    return str(UUID(value.rstrip('/').rsplit('/',1)[-1].split('?')[0]))


def pages(client, source, *, properties):
    """Complete query and selected-property pagination; no raw page cache."""
    cursor = None; seen = set()
    while True:
        batch = client.query(source, page_size=100, **({'start_cursor':cursor} if cursor else {}))
        for raw in batch['results']:
            page = {key: raw.get(key) for key in ('id','created_time','last_edited_time','archived','in_trash')}
            page['properties'] = {}
            for name in properties:
                prop = deepcopy(raw.get('properties',{}).get(name,{})); kind = prop.get('type')
                if prop.get('has_more') or (kind in {'rich_text','title','relation'} and len(prop.get(kind,[])) >= 25):
                    items = []; pcursor = None; pseen = set()
                    while True:
                        result = client.property(raw['id'],prop['id'],page_size=100,**({'start_cursor':pcursor} if pcursor else {}))
                        items.extend(result['results'])
                        if not result.get('has_more'):
                            break
                        pcursor = result.get('next_cursor')
                        require(pcursor and pcursor not in pseen,'property_pagination_did_not_advance'); pseen.add(pcursor)
                    prop[kind] = [item[kind] for item in items]
                    prop['has_more'] = False
                page['properties'][name] = prop
            yield page
        if not batch.get('has_more'):
            return
        cursor = batch.get('next_cursor')
        require(cursor and cursor not in seen, 'source_pagination_did_not_advance'); seen.add(cursor)


def declared_topics(envelope, field, allowed, *, details=False):
    """The sibling export's precedence, restricted to one permitted choice field.

    Free text, contact fields and Other text never leave this function. A skipped
    or deferred latest answer remains unknown, never an empty negative assertion.
    """
    payload = envelope.get('payload') or {}
    answers = {**(payload.get('answers') or {}), **(envelope.get('responses') or {}),
               **((envelope.get('player') or {}).get('profile_answers') or {})}
    value = answers.get(field); state = 'answered' if field in answers else 'missing'
    explicit_state = (payload.get('states') or {}).get(field)
    if explicit_state is not None:
        state = explicit_state if explicit_state in {'answered','partial','missing','skipped','deferred','ineligible','flagged','unresolved'} else 'invalid'
    if field in (payload.get('skips') or {}):
        value, state = None, 'skipped'
    trajectory = envelope.get('trajectory') or payload.get('trajectory') or {}
    for event in trajectory.get('events', []):
        if event.get('question_id') == field and event.get('kind') in {'answered','skipped','deferred'}:
            state = event['kind']; value = event.get('value') if state == 'answered' else None
    selected = value.get('selected') if isinstance(value,dict) else value
    if isinstance(selected,str):
        selected = [selected]
    unmapped = 0
    codes = []
    if state in {'answered','partial'}:
        if not isinstance(selected,list) or not all(isinstance(code,str) for code in selected):
            state = 'invalid'
        elif '__empty__' in selected and len(set(selected)) > 1:
            state = 'invalid'
        else:
            codes = sorted({code for code in selected if code in allowed and code not in {'other','__empty__'}})
            unmapped = len({code for code in selected if code not in allowed and code != '__empty__'})
    return (codes, state, unmapped) if details else (codes, state)


def capture_montreal(client, scope, *, captured_at=None):
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    people_source = scope['people_data_source_id']; responses_source = scope['responses_data_source_id']
    people_pages = list(pages(client, people_source, properties=('Name','institution','participant_uuid','participant_id','status')))
    source_people = {}; identity_index = defaultdict(set); duplicates = []
    for page in people_pages:
        pid = page_id(page['id'])
        if pid in source_people:
            duplicates.append(pid)
        source_people[pid] = page
        for field in ('participant_uuid','participant_id'):
            value = property_value(page['properties'][field])
            if value:
                identity_index[value].add(pid)
    responses = list(pages(client, responses_source, properties=('value_json','player')))
    skipped = Counter(); issues = []; submitted = []; scoped = 0; legacy = 0
    for page in responses:
        try:
            envelope = json.loads(property_value(page['properties']['value_json']) or '{}')
            if not isinstance(envelope,dict):
                raise ValueError
        except (ValueError,TypeError):
            skipped['invalid_response_json'] += 1; continue
        if envelope.get('probe_id') != scope['probe_id'] or (envelope.get('event_id') or envelope.get('scope_id')) != scope['session_id']:
            skipped['outside_approved_scope'] += 1; continue
        scoped += 1
        if envelope.get('record_type') != 'probe_submission' or envelope.get('state') != 'submitted':
            legacy += 1; skipped['not_a_submitted_inventory'] += 1; continue
        if page.get('archived') or page.get('in_trash'):
            skipped['archived_response'] += 1; continue
        links = property_value(page['properties']['player']) or []
        pid = page_id(links[0]) if len(links) == 1 else None
        source_identity = envelope.get('participant_id') or envelope.get('participant_uuid')
        if pid is not None and identity_index.get(source_identity) and pid not in identity_index[source_identity]:
            skipped['conflicting_person_identity'] += 1
            issues.append({'record_id':page['id'],'reason':'conflicting_person_identity'}); continue
        if not links and len(identity_index.get(source_identity,())) == 1:
            pid = next(iter(identity_index[source_identity]))
        if len(links) > 1:
            skipped['ambiguous_person_relation'] += 1
            issues.append({'record_id':page['id'],'reason':'ambiguous_person_relation'}); continue
        submitted.append((pid, page, envelope, source_identity))
    eligible = defaultdict(list); missing = []; missing_counts = Counter()
    for pid,page,envelope,identity in submitted:
        if pid not in source_people:
            missing.append({'record_id':page['id'],'reason':'submitted_inventory_without_resolvable_person_record'})
            skipped['missing_person_record'] += 1; continue
        eligible[pid].append((page,envelope))
    rows = []; chosen = {}; name_groups = defaultdict(list); organisation_groups = defaultdict(list)
    excluded = []
    for pid,inventories in sorted(eligible.items()):
        page = source_people[pid]; props = page['properties']
        name = property_value(props['Name']); institution = property_value(props['institution'])
        if page.get('archived') or page.get('in_trash') or property_value(props['status']) == 'revoked':
            excluded.append({'record_id':pid,'reason':'inactive_source_person'}); continue
        if not isinstance(name,str) or not name.strip():
            excluded.append({'record_id':pid,'reason':'missing_usable_name'}); continue
        rows.append({'url':'https://app.notion.com/'+pid,'Name':name,'institution':institution,
                     'createdTime':page.get('created_time'),'lastEditedTime':page.get('last_edited_time')})
        name_groups[folded(name)].append(pid)
        if institution and institution.strip():
            organisation_groups[folded(institution)].append(pid)
        else:
            missing_counts['affiliation'] += 1
        # Explicit source revision, then source record creation, then stable ID.
        # This is current inventory selection, not invented intermediate history.
        def order(item):
            raw_revision = item[1].get('revision',0)
            try: revision = int(raw_revision or 0)
            except (ValueError,TypeError): revision = 0
            return revision, item[0].get('created_time') or '', item[0]['id']
        chosen[pid] = max(inventories,key=order)
    snapshot = connector_people_snapshot(rows,captured_at=captured_at,data_source_id=people_source,
                                         database_id=scope.get('people_database_id'))
    topics = {k:v for k,v in scope.get('topics',{}).items() if k not in {'other','__empty__'}}
    topic_counts = Counter()
    expertise = {'schema_version':EXPERTISE_SCHEMA,'source_version':digest(scope),
                 'vocabulary':topics,'participants':{}}
    for pid,(page,envelope) in chosen.items():
        profile = {}
        for field,kind in (('knowledge_offer','capacity'),('knowledge_need','need')):
            selected,state,unmapped = declared_topics(envelope,field,topics,details=True)
            profile['offer' if kind=='capacity' else 'need'] = {'state':state,'codes':selected,
                'unmapped_count':unmapped,'source':{'data_source_id':responses_source,'record_id':page['id'],
                    'field':field,'captured_at':captured_at}}
            if state != 'answered':
                missing_counts[field + ':' + state] += 1
            for topic in selected:
                snapshot['records'].append({'kind':kind,'record_id':page['id']+'#'+field+':'+topic,
                    'data_source_id':responses_source,'database_id':scope.get('responses_database_id'),
                    'created_at':page.get('created_time'),'last_edited_at':page.get('last_edited_time'),
                    'fields':{'actor_id':source_id('person',people_source,pid),'domain':topics[topic],
                              'quantity':None,'unit':'declared knowledge domain'},
                    'source_properties':{field:[topic]},'epistemic_status':'source_assertion'})
                topic_counts[kind] += 1
        expertise['participants'][source_id('person',people_source,pid)] = profile
    snapshot['expertise'] = expertise
    report = {'capture_version':VERSION,'captured_at':captured_at,'source_version':digest(scope),
        'probe_id':scope['probe_id'],'session_id':scope['session_id'],
        'source_records_inspected':len(people_pages)+len(responses),'person_source_records':len(people_pages),
        'response_source_records':len(responses),'scoped_response_records':scoped,
        'submitted_inventories':len(submitted),'unique_linked_people':len(eligible),
        'eligible_people':len(rows),'canonical_organisations':0,
        'source_local_organisation_mentions':sum(len(ids) for ids in organisation_groups.values()),
        'distinct_organisation_labels':len(organisation_groups),
        'affiliations':sum(len(ids) for ids in organisation_groups.values()),
        'capacities':topic_counts['capacity'],'needs':topic_counts['need'],
        'repeated_submitted_inventories':sum(max(0,len(items)-1) for items in eligible.values()),
        'legacy_trajectory_records':legacy,'skipped':dict(skipped),'missing_fields':dict(missing_counts),
        'unresolved_identity_records':missing+issues,'excluded_people':excluded,
        'duplicate_source_pages':duplicates,
        'duplicate_name_candidates':[ids for ids in name_groups.values() if len(ids)>1],
        'organisation_reconciliation_candidates':[ids for ids in organisation_groups.values() if len(ids)>1],
        'organisation_identity_policy':'Source-local mentions; no canonical organisation relation in approved source schema; names never merge identities.'}
    # Safe counts only in the gameplay world. Detailed reconciliation stays private.
    snapshot['coverage'] = {key:value for key,value in report.items() if type(value) in {int,str,dict}
                            and key not in {'organisation_identity_policy'}}
    snapshot['coverage']['unresolved_identity_count'] = len(missing)+len(issues)
    snapshot['coverage']['excluded_people_count'] = len(excluded)
    return snapshot, report
