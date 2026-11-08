"""Practice progression over an isolated authoritative collective."""
from copy import deepcopy
from importlib.resources import files
import json
from uuid import uuid4

from ..runtime.actions import ActionSubmission, SimulationBinding
from ..runtime.runner import Collective
from ..model import require


def catalogue():
    library = json.loads(files(__package__).joinpath('tutorials.json').read_text())
    return [{**definition, 'world': deepcopy(library['world'])} for definition in library['tutorials']]


class TutorialSession:
    def __init__(self, definition):
        require(definition['schema'] == 'game-gamer/tutorial/v1', 'unsupported_tutorial_schema')
        self.definition = deepcopy(definition)
        world = deepcopy(definition['world'])
        world['scope_id'] = 'practice-'+uuid4().hex
        self.collective = Collective.start(world)
        self.index = 0
        self.results = {}

    @property
    def complete(self):
        return self.index == len(self.definition['steps'])

    def perform(self, step_index):
        if step_index in self.results:
            return deepcopy(self.results[step_index])
        require(step_index == self.index and not self.complete, 'tutorial_step_conflict')
        step = self.definition['steps'][step_index]
        command = step.get('action')
        if command is None:
            result = {'ok': True, 'errors': [], 'observation': True}
        else:
            actor = step['actor_id']
            payload = deepcopy(command['payload'])
            target = next((payload[key] for key in ('agreement_id', 'invitation_id', 'resource_id', 'id',
                                                     'objective_id', 'claim_id', 'target_id') if key in payload), None)
            result = self.collective.submit(ActionSubmission(
                action_id=f'tutorial-step-{step_index}', actor_id=actor, scope_id=self.collective.scope_id,
                target_id=target, expected_revision=self.collective.project()['version'],
                action_type=command['kind'], payload=payload),
                binding=SimulationBinding(scope_id=self.collective.scope_id, actor_id=actor))
        expected = step.get('expected_errors', [])
        if result['errors'] == expected:
            self.results[step_index] = deepcopy(result)
            self.index += 1
        return result
