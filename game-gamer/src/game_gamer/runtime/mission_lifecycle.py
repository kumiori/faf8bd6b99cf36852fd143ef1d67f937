"""First-class mission definitions and declarative world/target-lock constraints."""
from copy import deepcopy

from ..model import require
from . import missions

SCHEMA = 'game-gamer/mission/v1'
GAMEPLAY_ID = 'game-gamer:gameplay'
FIELDS = {
    'mission_create': ({'mission_id', 'title', 'rationale', 'target', 'criteria', 'governance'}, set()),
    'mission_adopt': ({'mission_id', 'version'}, set()),
    'mission_verify_outcome': ({'mission_id', 'version', 'reference'}, set()),
    'mission_complete': ({'mission_id', 'version'}, set()),
    'mission_abandon': ({'mission_id', 'version', 'reason'}, set()),
    'mission_reopen': ({'mission_id', 'version', 'reason'}, set()),
}


def _text(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, 'mission_text_required')
    return value.strip()


def snapshot_version(mission):
    return {'number': mission['version'], **deepcopy({key: mission.get(key) for key in
            ('title', 'need', 'rationale', 'target', 'feasibility', 'requirements', 'criteria', 'governance', 'completion')})}


def create(world, command, *, actor, timestamp):
    ident = command['mission_id']
    require(isinstance(ident, str) and ident == ident.strip() and ident, 'invalid_mission_id')
    require(ident not in {'world', 'clock', 'curation', 'curation-requests', missions.CATALOGUE_ID,
                          GAMEPLAY_ID, 'game-gamer:extension'} and not ident.startswith(
        ('mission_contribution_', 'action_', 'evidence_', 'commit_', 'log_', 'mutation_', 'curation_request_')),
        'reserved_mission_id')
    require(not any(ident in table for table in world.values()), 'mission_id_conflict')
    governance = command['governance']
    require(isinstance(governance, dict) and set(governance) == {'adopters', 'verifiers', 'operators'},
            'invalid_mission_governance')
    for members in governance.values():
        require(isinstance(members, list) and members and len(members) == len(set(members))
                and all(missions.active_actor(world, member) for member in members), 'invalid_mission_governance')
    require(set(governance['verifiers']).isdisjoint({actor, *governance['adopters']}),
            'independent_mission_verifier_required')
    criteria = command['criteria']
    require(isinstance(criteria, dict) and 0 < len(criteria) <= 50, 'invalid_mission_criteria')
    require(all(isinstance(key, str) and key and key == key.strip()
                and isinstance(value, str) and 0 < len(value.strip()) <= 4000 for key, value in criteria.items()),
            'invalid_mission_criteria')
    catalogue = world['configuration'].setdefault(missions.CATALOGUE_ID, {
        'id': missions.CATALOGUE_ID, 'status': 'active', 'schema': missions.SCHEMA,
        'requirements': {}, 'catalogues': {'actor': {}, 'means': {}, 'finality': {}, 'result': {}},
    })
    require(catalogue.get('schema') == missions.SCHEMA, 'unsupported_mission_catalogue')
    for key in sorted(criteria):
        description = criteria[key]
        record = {'title': description}
        require(key not in catalogue['requirements'] or catalogue['requirements'][key] == record,
                'mission_criterion_conflict')
        catalogue['requirements'][key] = record
    title, rationale, target = (_text(command[field]) for field in ('title', 'rationale', 'target'))
    mission = {'id': ident, 'kind': 'mission_definition', 'lifecycle_schema': SCHEMA,
               'status': 'proposed', 'version': 1, 'title': title, 'need': rationale,
               'rationale': rationale, 'target': target, 'feasibility': None, 'requirements': sorted(criteria),
               'criteria': {key: criteria[key] for key in sorted(criteria)},
               'governance': deepcopy(governance), 'completion': {'type': 'all_verified_requirements'},
               'created_by': actor, 'created_at': timestamp, 'acceptances': {},
               'provenance': {'kind': 'participant_proposal'}}
    mission['versions'] = [snapshot_version(mission)]
    world['configuration'][ident] = mission
    return mission


def revised(mission):
    """A material revision requires renewed adoption of the new exact version."""
    if mission.get('lifecycle_schema') == SCHEMA:
        mission.update(status='proposed', acceptances={})
        mission['versions'].append(snapshot_version(mission))


def prepare(world, command, *, actor, timestamp, sequence, action):
    kind = command['kind']
    if kind == 'mission_create':
        mission = create(world, command, actor=actor, timestamp=timestamp)
    else:
        mission = missions.definitions(world).get(command['mission_id'])
        require(mission is not None and mission.get('lifecycle_schema') == SCHEMA, 'governed_mission_required')
        require(type(command['version']) is int and command['version'] == mission['version'], 'mission_version_conflict')
        governance = mission['governance']
        receipt = {'actor_id': actor, 'recorded_at': timestamp, 'event_ref': f'commit_{sequence:06}'}
        if kind == 'mission_adopt':
            require(mission['status'] == 'proposed', 'proposed_mission_required')
            require(actor in governance['adopters'], 'mission_adopter_required')
            require(actor not in mission['acceptances'], 'mission_already_adopted')
            mission['acceptances'][actor] = receipt
            if set(mission['acceptances']) == set(governance['adopters']):
                mission['status'] = 'adopted'
        elif kind == 'mission_verify_outcome':
            require(mission['status'] in {'adopted', 'pursued'}, 'open_mission_required')
            contributors = {record['actor_id'] for record in missions.contributions(world, mission['id'])
                            if record['type'] == 'commit'}
            require(actor in governance['verifiers'] and actor not in contributors,
                    'independent_mission_verifier_required')
            evidence = [record for record in world['evidence'].values()
                        if record['kind'] == 'mission_verification' and record['status'] == 'verified']
            require(set(mission['requirements']) <= {record['requirement_id'] for record in evidence},
                    'mission_criteria_unverified')
            reference = _text(command['reference'])
            ident = f'evidence_{sequence:06}'
            require(ident not in world['evidence'], 'mission_evidence_id_conflict')
            world['evidence'][ident] = {'id': ident, 'kind': 'mission_completion', 'status': 'verified',
                'mission_id': mission['id'], 'mission_version': mission['version'], 'reference': reference,
                'submitted_by': actor, 'submitted_at': timestamp, 'support_ids': [record['id'] for record in evidence
                if record['requirement_id'] in mission['requirements']], 'provenance': {'kind': 'independent_review'}}
            mission.update(status='verified', verification_id=ident)
            action['target_ids'].append(ident)
        elif kind == 'mission_complete':
            require(mission['status'] == 'verified', 'verified_mission_required')
            require(actor in governance['operators'], 'mission_operator_required')
            mission['status'] = 'completed'
        else:
            require(actor in governance['operators'], 'mission_operator_required')
            _text(command['reason'])
            if kind == 'mission_abandon':
                require(mission['status'] in {'proposed', 'adopted', 'pursued', 'verified'}, 'active_mission_required')
                mission['status'] = 'abandoned'
            else:
                require(mission['status'] in {'completed', 'abandoned', 'verified'}, 'closed_mission_required')
                mission['version'] += 1
                revised(mission)
        mission['last_transition'] = receipt
    action['target_ids'].append(mission['id'])


def configure_gameplay(world, configuration, available_actions):
    require(isinstance(configuration, dict) and configuration.get('mode') in {'world_driven', 'target_locked'},
            'invalid_gameplay_configuration')
    if configuration['mode'] == 'world_driven':
        require(set(configuration) == {'mode'}, 'invalid_gameplay_configuration')
    else:
        require(set(configuration) == {'mode', 'mission_id', 'allowed_actions'}, 'invalid_gameplay_configuration')
        require(configuration['mission_id'] in missions.definitions(world), 'unknown_locked_mission')
        allowed = configuration['allowed_actions']
        require(isinstance(allowed, list) and allowed and len(allowed) == len(set(allowed))
                and set(allowed) <= available_actions, 'invalid_locked_actions')
    world['configuration'][GAMEPLAY_ID] = {'id': GAMEPLAY_ID, 'status': 'active', **deepcopy(configuration)}


def constrain(world, command):
    configuration = world['configuration'].get(GAMEPLAY_ID, {})
    if configuration.get('mode') != 'target_locked':
        return
    require(command['kind'] in configuration['allowed_actions'], 'target_locked_action')
    if 'mission_id' in command:
        require(command['mission_id'] == configuration['mission_id'], 'target_locked_mission')
    mission = missions.definitions(world)[configuration['mission_id']]
    require(mission['status'] not in {'completed', 'abandoned'} or command['kind'] == 'mission_reopen',
            'target_locked_game_closed')
