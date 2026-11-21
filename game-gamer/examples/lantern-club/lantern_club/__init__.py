"""Fictional world-driven application using only Game-Gamer's public API."""
import json

from game_gamer import ActionSubmission, Collective, CommandDefinition, DomainError, Extension, PolicyHook, SimulationBinding


def record_visit(world, command, *, actor, timestamp, sequence, action):
    if command['shelf_id'] != 'reading-room':
        raise DomainError('unknown_shelf')
    visits = world['configuration'].setdefault('visits', {'id': 'visits', 'status': 'active', 'count': 0})
    visits['count'] += 1
    action['target_ids'] = ['visits']


def members_only(world, command, **context):
    if command['kind'] == 'record_visit':
        if 'member' not in world['actors'][context['actor']]['roles']:
            raise DomainError('club_member_required')


def visit_count(world):
    return world['configuration'].get('visits', {}).get('count', 0)


EXTENSION = Extension(
    id='fictional.lantern-club', version='1.0.0',
    commands={'record_visit': CommandDefinition(required={'shelf_id'}, handler=record_visit, target_field='shelf_id')},
    policies=(PolicyHook(before=members_only),), projections={'visit_count': visit_count},
)


def definition():
    return {'schema': 'game-gamer/world/v1', 'scope_id': 'lantern-club', 'revision': 1,
            'execution_mode': 'simulation', 'world_time': '2030-01-01T00:00:00+00:00',
            'title': 'The fictional Lantern Club',
            'actors': [{'id': 'lee', 'label': 'Lee', 'roles': ['member']},
                       {'id': 'kim', 'label': 'Kim', 'roles': ['guest']}]}


def visit(game, *, actor='lee', key='first-visit'):
    return ActionSubmission(action_id=key, actor_id=actor, scope_id=game.scope_id,
                            target_id='reading-room', expected_revision=game.revision,
                            action_type='record_visit', payload={'shelf_id': 'reading-room'})


def main():
    game = Collective.start(definition(), extension=EXTENSION)
    result = game.submit(visit(game), binding=SimulationBinding(scope_id=game.scope_id, actor_id='lee'))
    assert result['ok'], result
    print(json.dumps({'visits': game.project('visit_count'), 'revision': game.revision}))
