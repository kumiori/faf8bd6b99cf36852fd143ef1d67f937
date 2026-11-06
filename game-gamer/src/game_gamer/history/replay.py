"""Portable histories for scoped simulations and explicitly hypothetical forks."""
from ..model import DomainError, require
from ..runtime.engine import CollectiveEngine, digest
from ..schema.definitions import WORLD_SCHEMA

HISTORY_SCHEMA = 'game-gamer/history/v1'


def scope_of(game):
    configuration = game.get_world()['configuration'].get('world', {})
    require(configuration.get('schema_version') == WORLD_SCHEMA, 'unsupported_world_schema')
    require(configuration.get('execution_mode') == 'simulation', 'unsupported_execution_mode')
    scope = configuration.get('scope_id')
    require(isinstance(scope, str) and bool(scope.strip()) and scope == scope.strip(), 'invalid_scope')
    require(type(configuration.get('definition_revision')) is int and configuration['definition_revision'] > 0,
            'invalid_definition_revision')
    return scope


def restore(document):
    require(isinstance(document, dict) and document.get('schema') == HISTORY_SCHEMA, 'unsupported_history_schema')
    require(set(document) == {'schema', 'scope_id', 'events', 'history_digest', 'fork'}, 'invalid_history')
    events = document['events']
    require(isinstance(events, list) and events, 'empty_history')
    try:
        require(digest(events) == document['history_digest'], 'invalid_history_digest')
        require(events[0]['kind'] == 'world.initialized' and events[0]['command'] is None,
                'invalid_genesis')
        require(all(m.get('schema_version') == '0.1' for event in events for m in event['mutations']),
                'unsupported_mutation_schema')
        game = CollectiveEngine.from_log(events[:1])
        require(document['scope_id'] == scope_of(game), 'scope_mismatch')
        fork = document['fork']
        if fork is not None:
            require(isinstance(fork, dict) and set(fork) == {'id', 'revision', 'prefix_digest'} and
                    isinstance(fork['id'], str) and bool(fork['id'].strip()) and
                    type(fork['revision']) is int and 1 <= fork['revision'] <= len(events) and
                    digest(events[:fork['revision']]) == fork['prefix_digest'], 'invalid_fork')
        # A portable history is composed of genesis and reproducible accepted commands.
        for sequence, event in enumerate(events[1:], 2):
            command = event['command']
            branch_event = fork is not None and sequence > fork['revision']
            expected_scope = branch_scope(document['scope_id'], fork) if branch_event else document['scope_id']
            expected_provider = 'counterfactual_simulation' if branch_event else 'development_simulation'
            session = command['session']
            require(session['subject'] == expected_scope and session['provider'] == expected_provider,
                    'invalid_history_authority')
            result = game.submit(command)
            require(result['ok'] and event['sequence'] == sequence and
                    len(game._log) == sequence and game._log[-1] == event, 'invalid_transition_history')
        return game
    except DomainError:
        raise
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        raise DomainError('invalid_history') from error


def branch_scope(scope_id, fork):
    return 'fork:' + digest([scope_id, fork])
