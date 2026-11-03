"""Declarative fictional worlds, separate from shared transition rules."""
from dataclasses import asdict
import json
from pathlib import Path
from .engine import CommonsGame
from .model import Actor, Resource, GovernancePolicy, require

SCENARIOS = ('bilateral-logs', 'montreal-geneva', 'commons-gathering')


def definition(name):
    require(name in SCENARIOS, 'unknown_scenario')
    return json.loads((Path(__file__).parent / 'scenarios' / f'{name}.json').read_text())


def load_scenario(name='bilateral-logs'):
    spec = definition(name)
    game = CommonsGame()
    world = game.get_world()
    for item in spec['actors']:
        world['actors'][item['id']] = asdict(Actor(**item))
    for item in spec['resources']:
        world['resources'][item['id']] = asdict(Resource(**item))
    for item in spec['governance']:
        world['governance'][item['id']] = asdict(GovernancePolicy(**item))
    for table in ('relationships', 'capacities', 'needs', 'objectives'):
        for item in spec.get(table, []):
            world[table][item['id']] = item
    world['configuration']['world'] = {'id': 'world', 'status': 'active', 'scenario': name,
        'title': spec['title'], 'description': spec['description'], 'synthetic': True,
        'mode': spec['mode'], 'proposal': spec['proposal'], 'schema_version': 'commons.0.1'}
    world['configuration']['clock'] = {'id': 'clock', 'status': 'active', 'now': spec['world_time']}
    game._commit(game.get_world(), world, 'world.initialized')
    return game


def demo_commands(name='bilateral-logs'):
    """A transparent command script; interactive play never calls it implicitly."""
    spec = definition(name)
    proposal = spec['proposal']
    first, second = proposal['parties'][:2]
    commands = []
    def add(kind, actor, **payload):
        command = {'kind': kind, 'actor': actor, 'key': f'demo-{name}-{len(commands) + 1:03}', **payload}
        commands.append(command)
    if spec['mode'] == 'gathering':
        for i, actor in enumerate(proposal['parties'][1:]):
            add('invite', first, recipient_id=actor, objective_id=proposal['objective_id'])
            # Initial world is T1, invitations are T2 and T4.
            add('respond_invitation', actor, invitation_id=f'invitation_{2 + i * 2:06}', response='accept')
    add('propose', first, **proposal)
    terms = json.loads(json.dumps(proposal['terms']))
    terms['conditions'].append('All parties review the revised delivery note before activation.')
    target = {'agreement_id': proposal['id']}
    add('amend', second, **target, version=1, terms=terms)
    for actor in proposal['parties']:
        add('accept', actor, **target, version=2)
    for actor in spec['demo_authorizers']:
        add('authorize', actor, **target, version=2)
    add('activate', first, **target, version=2)
    for actor in proposal['parties']:
        add('initiate', actor, **target, version=2, reference=f'Synthetic execution record by {actor}.')
        add('fulfill', actor, **target, version=2, reference=f'Synthetic delivery report by {actor}.',
            criteria=proposal['verification']['criteria'])
    add('verify', proposal['verification']['verifier_ids'][0], **target, version=2,
        reference='Independent review of synthetic artefacts against the agreed criteria.')
    return commands


def run_demo(name='bilateral-logs'):
    game = load_scenario(name)
    for command in demo_commands(name):
        result = game.submit(command)
        if not result['ok']:
            raise RuntimeError(f"Demo failed at {command['kind']}: {result['errors']}")
    return game
