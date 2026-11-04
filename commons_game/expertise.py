"""Read-only expertise incidence and strict directed complementarity projections.

The source catalogue and answer states are observations, never permissions,
collaborations or a replacement for the authoritative event log.
"""
from copy import deepcopy

from .catalogue import people
from .model import require

SCHEMA = 'saddle-expertise/v1'
FIELDS = {'offer': 'knowledge_offer', 'need': 'knowledge_need'}
STATES = {'answered', 'partial', 'missing', 'skipped', 'deferred', 'ineligible', 'invalid', 'flagged', 'unresolved'}


def validate_expertise(value, actors):
    require(isinstance(value, dict) and value.get('schema_version') == SCHEMA, 'invalid_expertise_schema')
    require(set(value) == {'schema_version', 'vocabulary', 'participants', 'source_version'}, 'invalid_expertise_fields')
    require(isinstance(value['source_version'],str) and value['source_version'], 'invalid_expertise_source_version')
    vocabulary = value['vocabulary']
    require(isinstance(vocabulary, dict) and all(isinstance(k, str) and isinstance(v, str)
            and k and v and k not in {'other', '__empty__'} for k, v in vocabulary.items()), 'invalid_expertise_vocabulary')
    require(isinstance(value['participants'], dict), 'invalid_expertise_participants')
    for actor_id, profile in value['participants'].items():
        require(actor_id in actors and actors[actor_id]['kind'] == 'person', 'unresolved_expertise_actor')
        require(isinstance(profile, dict) and set(profile) == set(FIELDS), 'invalid_expertise_profile')
        for side, observation in profile.items():
            require(isinstance(observation, dict) and {'state', 'codes', 'source', 'unmapped_count'} <= set(observation)
                    and not (set(observation) - {'state', 'codes', 'source', 'unmapped_count', 'observed_absent_codes'}),
                    'invalid_expertise_observation')
            require(isinstance(observation['state'],str) and observation['state'] in STATES, 'invalid_expertise_state')
            require(isinstance(observation['codes'], list) and all(isinstance(code,str) for code in observation['codes'])
                    and len(set(observation['codes'])) == len(observation['codes'])
                    and all(code in vocabulary for code in observation['codes']), 'invalid_expertise_codes')
            require(observation['state'] in {'answered', 'partial'} or not observation['codes'], 'unanswered_expertise_values')
            absent = observation.get('observed_absent_codes', [])
            require(isinstance(absent, list) and all(isinstance(code, str) and code in vocabulary for code in absent)
                    and len(set(absent)) == len(absent) and not (set(absent) & set(observation['codes']))
                    and (observation['state'] in {'answered', 'partial'} or not absent), 'invalid_observed_absence')
            require(type(observation['unmapped_count']) is int and observation['unmapped_count'] >= 0, 'invalid_unmapped_count')
            source = observation['source']
            require(isinstance(source, dict) and set(source) == {'data_source_id', 'record_id', 'field', 'captured_at'},
                    'invalid_expertise_source')
            require(source['field'] == FIELDS[side] and all(isinstance(v, str) and v for v in source.values()),
                    'invalid_expertise_source')
    return deepcopy(value)


def matrix(world):
    """W = O N^T with per-domain missingness and a common declared vocabulary.

    Older snapshots have no answer coverage. Their positive records remain
    inspectable, but do not establish complete incidence vectors or known zeros.
    The raw diagonal is retained analytically; the interface forbids self-pair actions.
    """
    roster = people(world)
    source = world['configuration'].get('ecosystem-expertise', {}).get('assertions', {})
    vocabulary = source.get('vocabulary', {})
    domains = sorted(vocabulary)
    profiles = source.get('participants', {})
    offers, needs, observations = [], [], {}
    for actor in roster:
        profile = profiles.get(actor['id'], {})
        observations[actor['id']] = {}
        for side, rows in (('offer', offers), ('need', needs)):
            observed = profile.get(side, {'state': 'missing', 'codes': [], 'source': {}, 'unmapped_count': 0})
            observations[actor['id']][side] = deepcopy(observed)
            rows.append([1 if code in observed['codes'] else
                         0 if observed['state'] == 'answered' or code in observed.get('observed_absent_codes', []) else None
                         for code in domains])
    from .projections import complementarity
    bounds = complementarity(offers, needs)['W']
    # An absent vocabulary cannot establish an exact empty-vector zero.
    if not domains:
        bounds = [[{'value': None, 'lower': 0, 'upper': None, 'missing_terms': None}
                   for _ in roster] for _ in roster]
    values = [[item['value'] for item in row] for row in bounds]
    return {'actors': roster, 'domains': domains, 'vocabulary': deepcopy(vocabulary),
            'O': offers, 'N': needs, 'W': values, 'bounds': bounds, 'observations': observations,
            'mapped': bool(source), 'source_version': source.get('source_version'),
            'orientation': {'rows': 'provider', 'columns': 'requester'}}


def cell(projection, row, column):
    provider, requester = projection['actors'][row], projection['actors'][column]
    offer = projection['observations'][provider['id']]['offer']
    need = projection['observations'][requester['id']]['need']
    matches = [code for k, code in enumerate(projection['domains'])
               if projection['O'][row][k] == projection['N'][column][k] == 1]
    return {'provider': provider, 'requester': requester, 'value': projection['W'][row][column],
            **projection['bounds'][row][column],
            'matching_codes': matches, 'matching_domains': [projection['vocabulary'][code] for code in matches],
            'offer': deepcopy(offer), 'need': deepcopy(need), 'self_pairing': row == column,
            'meaning': 'Declared potential only; no agreement, competence certification or consent.'}


def potential_edges(world):
    projection = matrix(world)
    for i, provider in enumerate(projection['actors']):
        for j, requester in enumerate(projection['actors']):
            if i == j:
                continue
            detail = cell(projection, i, j)
            for code, domain in zip(detail['matching_codes'], detail['matching_domains']):
                yield {'id': f"potential:{provider['id']}:{requester['id']}:{code}",
                       'kind': 'potential_complementarity', 'source_id': provider['id'], 'target_id': requester['id'],
                       'domain': domain, 'status': 'inferred', 'generator': 'strict_expertise_matrix',
                       'score': detail['value'], 'lower': detail['lower'], 'upper': detail['upper'],
                       'directed': True, 'matrix_cell': [i, j],
                       'source_record_ids': [detail['offer']['source']['record_id'], detail['need']['source']['record_id']]}
