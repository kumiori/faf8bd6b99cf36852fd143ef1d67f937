"""Trusted import of the supplied Montréal topology and participant statements."""

from collections import Counter, defaultdict
import csv
from copy import deepcopy
import hashlib
import io
import unicodedata

from game_gamer.runtime.curation import canonical
from .model import require

LAYER = 'montreal_2026_reconstructed'
SCHEMA = 'commons/montreal-network/v1'
PROFILE_FIELDS = ('Nom', 'Titre / fonction', 'Organisation', 'Pourquoi suis-je ici ?', 'Remarque')
EDGE_FIELDS = ('source', 'cible', 'remarque')


def _normalise(name):
    return ''.join(character for character in unicodedata.normalize('NFKD', name.casefold())
                   if character.isalnum())


def _identity(name):
    return 'montreal-2026:person:' + hashlib.sha256(unicodedata.normalize('NFC', name.strip()).encode()).hexdigest()[:24]


def _read(path, delimiter, fields):
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''), delimiter=delimiter, strict=True)
    require(tuple(reader.fieldnames or ()) == fields, 'invalid_montreal_source_columns')
    rows = []
    while True:
        line = reader.line_num + 1
        row = next(reader, None)
        if row is None:
            break
        require(set(row) == set(fields) and all(isinstance(value, str) for value in row.values()),
                'invalid_montreal_source_row')
        rows.append({'id': f'montreal-2026:{digest[:20]}:{line}', 'raw': row,
                     'provenance': {'kind': 'historical_transcription', 'file': path.name,
                                    'sha256': digest, 'line': line}})
    return digest, rows


def read_sources(connections, statements):
    topology_digest, connections = _read(connections, ',', EDGE_FIELDS)
    profile_digest, statements = _read(statements, '\t', PROFILE_FIELDS)
    names = defaultdict(set)
    for row in connections:
        for field in ('source', 'cible'):
            name = row['raw'][field]
            require(bool(_normalise(name)), 'missing_montreal_endpoint')
            ident = _identity(name)
            names[ident].add(name)
            row['source_id' if field == 'source' else 'target_id'] = ident
    for row in statements:
        name = row['raw']['Nom']
        require(bool(_normalise(name)), 'missing_montreal_profile_name')
        row['person_id'] = _identity(name)
        names[row['person_id']].add(name)
    return {'id': LAYER, 'schema': SCHEMA, 'status': 'recorded',
            'digests': {'connections': topology_digest, 'statements': profile_digest},
            'connections': connections, 'statements': statements,
            'names': {key: sorted(values) for key, values in sorted(names.items())}}


def import_montreal_network(game, sources, *, identities=None, dry_run=False):
    """Persist original rows and reviewed bindings together in one replayable event."""
    before = game.get_world()
    require(before['configuration']['world']['scenario'] == 'montreal-commons', 'montreal_world_required')
    saved = before['configuration'].get(LAYER)
    require(saved is None or saved['digests'] == sources['digests'], 'montreal_source_snapshot_conflict')
    if saved is not None:
        sources = {key: value for key, value in saved.items() if key != 'identities'}
    overrides = identities if identities is not None else {}
    require(isinstance(overrides, dict) and overrides.keys() <= sources['names'].keys(),
            'unknown_montreal_source_identity')
    people = {key: actor for key, actor in before['actors'].items() if actor['kind'] == 'person'}
    matches = defaultdict(set)
    for key, actor in people.items():
        if actor['status'] == 'active':
            matches[_normalise(actor['label'])].add(canonical(before, key))

    bindings = {}
    for key, names in sources['names'].items():
        candidates = sorted(matches[_normalise(names[0])])
        if key in overrides:
            actor = overrides[key]
            previous = saved['identities'][key] if saved else {}
            if previous.get('review_status') in {'matched', 'created', 'rejected'}:
                require(previous['actor_id'] == actor, 'source_review_is_final')
                bindings[key] = previous
                continue
            require(actor is None or isinstance(actor, str) and actor in people
                    and canonical(before, actor) == actor and people[actor]['status'] == 'active',
                    'invalid_montreal_actor_binding')
            bindings[key] = {'actor_id': actor, 'method': 'operator_review', 'candidates': candidates}
        elif saved is not None:
            bindings[key] = saved['identities'][key]
        else:
            bindings[key] = {'actor_id': None, 'method': 'pending_review',
                             'candidates': candidates}

    dataset = {**sources, 'identities': bindings}
    unresolved = [{'source_id': key, 'names': sources['names'][key], 'candidate_actor_ids': value['candidates'],
                   'status': 'ambiguous' if len(value['candidates']) > 1 else
                   'suggested' if value['candidates'] else 'unmatched'}
                  for key, value in bindings.items() if resolved_actor(value) is None
                  and value.get('review_status') != 'rejected']
    connections = sources['connections']
    statements = sources['statements']
    pairs = Counter((row['source_id'], row['target_id']) for row in connections)
    profile_counts = Counter(row['person_id'] for row in statements)
    report = {'ok': True, 'layer': LAYER, 'nodes': len(bindings), 'edges': len(connections),
              'statements': len(statements), 'matched': sum(resolved_actor(value) is not None for value in bindings.values()),
              'unmatched': sum(row['status'] == 'unmatched' for row in unresolved),
              'ambiguous': sum(row['status'] == 'ambiguous' for row in unresolved),
              'duplicate_edges': sum(count-1 for count in pairs.values()),
              'duplicate_profiles': sum(count-1 for count in profile_counts.values()),
              'shared_actor_bindings': sum(count-1 for count in Counter(
                  canonical(before, value['actor_id']) for value in bindings.values() if value['actor_id']).values()),
              'review': unresolved, 'changed': dataset != saved, 'dry_run': dry_run}
    if report['changed'] and not dry_run:
        after = deepcopy(before)
        after['configuration'][LAYER] = dataset
        event = game.record_transition(before, after, 'reconstruction.sources_imported')
        report['commit_id'] = event['commit']['id']
    return report


def resolved_actor(binding):
    """Historic name-only suggestions remain available as evidence for review."""
    return None if binding.get('method') == 'unique_full_name' else binding['actor_id']


def project_topology(world, graph):
    """Use roster IDs where resolved and source-only IDs for unresolved participants."""
    dataset = world['configuration'].get(LAYER)
    if dataset is None:
        return graph
    roster = {node['id']: node for node in graph['nodes']}
    nodes, edges, omitted = [], [], []
    endpoints = {}
    for source_id, binding in dataset['identities'].items():
        actor = resolved_actor(binding)
        if binding.get('review_status') == 'rejected':
            continue
        if actor is None:
            name = dataset['names'][source_id][0]
            nodes.append({'id': source_id, 'kind': 'person', 'label': name,
                          'display_name': name, 'source_only': True, 'status': 'reported'})
            endpoints[source_id] = source_id
        elif canonical(world, actor) in roster:
            endpoints[source_id] = canonical(world, actor)
    for record in dataset['connections']:
        source, target = (endpoints.get(record[field]) for field in ('source_id', 'target_id'))
        if source is None or target is None or source == target:
            omitted.append({'source_record_id': record['id'], 'reason': 'endpoint_hidden_or_archived'
                            if source is None or target is None else 'same_resolved_identity'})
            continue
        raw = record['raw']
        edges.append({'id': record['id'], 'kind': 'montreal_transcription', 'layer': LAYER,
                      'source_id': source, 'target_id': target, 'directed': True, 'status': 'reported',
                      'observation': 'transcribed', 'remarks': raw['remarque'],
                      'source_name': raw['source'], 'target_name': raw['cible'],
                      'source_identity_id': record['source_id'], 'target_identity_id': record['target_id'],
                      'source_record_ids': [record['id']], 'provenance': deepcopy(record['provenance'])})
    return {**graph, 'nodes': [*graph['nodes'], *nodes], 'edges': [*graph['edges'], *edges],
            'montreal_omissions': omitted}


def profile_statements(world, participant):
    dataset = world['configuration'].get(LAYER, {})
    bindings = dataset.get('identities', {})
    sources = {key for key, binding in bindings.items()
               if binding.get('review_status') != 'rejected'
               and canonical(world, resolved_actor(binding) or key) == participant}
    return [row for row in dataset.get('statements', ()) if row['person_id'] in sources]
