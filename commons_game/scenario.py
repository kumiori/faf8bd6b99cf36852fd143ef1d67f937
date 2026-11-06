"""Declarative fictional worlds, separate from shared transition rules."""
import json
from pathlib import Path
from .engine import CommonsGame
from game_gamer.schema.definitions import initialise_legacy
from .model import require

SCENARIOS = ('bilateral-logs', 'montreal-geneva', 'commons-gathering', 'montreal-commons')


def definition(name):
    require(name in SCENARIOS, 'unknown_scenario')
    return json.loads((Path(__file__).parent / 'scenarios' / f'{name}.json').read_text())


def load_scenario(name='bilateral-logs'):
    return initialise_legacy(CommonsGame(), definition(name), name)


def demo_commands(name='bilateral-logs'):
    """A transparent command script; interactive play never calls it implicitly."""
    spec = definition(name)
    require(spec['proposal'] is not None, 'empirical_world_requires_explicit_play')
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
