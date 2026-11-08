"""Validation and materialisation of portable simulation definitions."""
from copy import deepcopy
from dataclasses import asdict
import json

from ..model import Actor, DomainError, GovernancePolicy, Resource, require
from .reconstruction_sources import prepare_reconstruction_sources
from ..runtime.reconstruction import CLAIM_KINDS
from ..runtime.engine import CollectiveEngine, instant, text

WORLD_SCHEMA = 'game-gamer/world/v1'
_SEED_TABLES = ('actors', 'resources', 'governance', 'relationships', 'capacities', 'needs', 'objectives')
_MODELS = {'actors': Actor, 'resources': Resource, 'governance': GovernancePolicy}


def _build_world(game, spec, configuration):
    world = game.get_world()
    for table in _SEED_TABLES:
        for item in spec.get(table, []):
            record = asdict(_MODELS[table](**item)) if table in _MODELS else deepcopy(item)
            world[table][record['id']] = record
    world['configuration']['world'] = configuration
    world['configuration']['clock'] = {'id': 'clock', 'status': 'active', 'now': spec['world_time']}
    return world


def initialise_legacy(game, spec, name):
    """Materialise the original Commons fixture schema without changing its log."""
    configuration = {'id': 'world', 'status': 'active', 'scenario': name,
                     'title': spec['title'], 'description': spec['description'],
                     'synthetic': spec.get('synthetic', True), 'mode': spec['mode'],
                     'proposal': deepcopy(spec['proposal']), 'schema_version': 'commons.0.1'}
    game._commit(game.get_world(), _build_world(game, spec, configuration), 'world.initialized')
    return game


def _validate_references(world):
    actors = world['actors']
    for actor in actors.values():
        text(actor['label'])
        text(actor['category'])
        require(actor['kind'] in {'person', 'organisation'}, 'invalid_actor_kind')
        require(isinstance(actor['roles'], list) and all(isinstance(r, str) for r in actor['roles']),
                'invalid_actor_roles')
    for resource in world['resources'].values():
        require(resource['owner_id'] in actors, 'unknown_resource_owner')
        require(type(resource['quantity']) is int and resource['quantity'] >= 0, 'invalid_quantity')
        text(resource['unit'])
    for policy in world['governance'].values():
        eligible = policy['eligible_actors']
        require(isinstance(eligible, list) and len(eligible) == len(set(eligible)) and
                set(eligible) <= actors.keys(), 'invalid_eligible_actors')
        require(type(policy['threshold']) is int and 0 <= policy['threshold'] <= len(eligible),
                'invalid_policy_threshold')
        require(isinstance(policy['required_actors'], list) and
                set(policy['required_actors']) <= set(eligible), 'invalid_required_actors')
        require(isinstance(policy['required_categories'], list) and
                set(policy['required_categories']) <= {actors[a]['category'] for a in eligible},
                'invalid_required_categories')
    for table in ('capacities', 'needs'):
        for record in world[table].values():
            require(record['actor_id'] in actors, 'unknown_actor')
            text(record['domain'])
            require(record['unit'] is None or isinstance(record['unit'], str), 'invalid_unit')
    for relation in world['relationships'].values():
        require(relation['source_id'] in actors and relation['target_id'] in actors, 'unknown_actor')
        require(relation['kind'] not in {'contact_invitation', 'acknowledged_connection', 'invited', *CLAIM_KINDS},
                'relationship_requires_action')
    for objective in world['objectives'].values():
        success = objective['success']
        require(set(success) == {'verified_agreements', 'minimum_parties', 'minimum_attendees'} and
                all(type(n) is int for n in success.values()) and success['verified_agreements'] > 0
                and success['minimum_parties'] >= 2 and success['minimum_attendees'] >= 0,
                'invalid_objective_criteria')
        require(objective['mode'] in {'ecosystem', 'gathering', 'scenarios'}, 'invalid_objective_mode')
        require(objective.get('status') == 'open' and objective.get('support_ids') == [],
                'invalid_initial_objective')


def initialise(definition):
    """Create the canonical genesis event from a JSON-compatible definition."""
    require(isinstance(definition, dict) and definition.get('schema') == WORLD_SCHEMA, 'unsupported_world_schema')
    try:
        require(set(definition) <= {*_SEED_TABLES, 'schema', 'scope_id', 'revision', 'execution_mode',
                                    'world_time', 'title', 'reconstruction_sources'}, 'unknown_world_field')
        require(json.loads(json.dumps(definition, sort_keys=True, allow_nan=False)) == definition,
                'invalid_world_definition')
        scope = text(definition['scope_id'], 'scope_required')
        require(scope == definition['scope_id'], 'invalid_scope')
        require(type(definition['revision']) is int and definition['revision'] > 0, 'invalid_definition_revision')
        require(definition['execution_mode'] == 'simulation', 'unsupported_execution_mode')
        instant(definition['world_time'])
        title = text(definition['title'])
        ids = {'world', 'clock'}
        for table in _SEED_TABLES:
            records = definition.get(table, [])
            require(isinstance(records, list), 'invalid_seed_table')
            for record in records:
                ident = text(record['id'], 'id_required')
                require(ident == record['id'] and ident not in ids, 'invalid_seed_id')
                ids.add(ident)
                if table not in _MODELS:
                    text(record['status'], 'status_required')
                    text(record['provenance']['kind'], 'provenance_required')
        game = CollectiveEngine()
        configuration = {'id': 'world', 'status': 'active', 'scope_id': scope, 'title': title,
                         'definition_revision': definition['revision'], 'execution_mode': 'simulation',
                         'schema_version': WORLD_SCHEMA}
        world = _build_world(game, definition, configuration)
        _validate_references(world)
        sources = definition.get('reconstruction_sources', [])
        require(isinstance(sources, list), 'invalid_reconstruction_sources')
        world['evidence'].update(prepare_reconstruction_sources(sources, world['actors'].keys()))
        require(not world['evidence'].keys() & ids, 'invalid_seed_id')
        game._commit(game.get_world(), world, 'world.initialized')
        return game
    except DomainError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise DomainError('invalid_world_definition') from error
