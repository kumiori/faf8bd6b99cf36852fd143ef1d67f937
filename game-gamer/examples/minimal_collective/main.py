"""A fictional collective using only the installed game-gamer package."""
from pathlib import Path
import json

from game_gamer import ActionSubmission, Collective, SimulationBinding, epistemic_status


def main():
    world = json.loads(Path(__file__).with_name('world.json').read_text())
    collective = Collective.start(world)

    def submit(actor, action_type, target_id, **payload):
        revision = collective.project()['version']
        action = ActionSubmission(action_id=f'example-{revision}', actor_id=actor, scope_id=collective.scope_id,
                                  expected_revision=revision, target_id=target_id, action_type=action_type,
                                  payload=payload)
        result = collective.submit(action, binding=SimulationBinding(actor_id=actor, scope_id=collective.scope_id))
        if not result['ok']:
            raise ValueError(result['errors'])

    # Ecosystem supplies the initial possibility; Gathering and Scenarios act on that world.
    inferred = collective.project()['possibilities'][0]
    submit('sam', 'invite', 'run-rehearsal', recipient_id='jo', objective_id='run-rehearsal')
    invitation = collective.project('relationships')[0]['id']
    submit('jo', 'respond_invitation', invitation, invitation_id=invitation, response='accept')
    submit('sam', 'propose', 'rehearsal', id='rehearsal', label='Rehearsal plan',
           objective_id='run-rehearsal', parties=['sam', 'jo'],
           terms={'purpose': 'Run a short rehearsal', 'conditions': [],
                  'responsibilities': [{'actor_id': 'sam', 'description': 'Lead rehearsal'},
                                       {'actor_id': 'jo', 'description': 'Provide the room'}]},
           resources=[{'resource_id': 'room', 'quantity': 1}], valid_until='2030-01-02T00:00:00+00:00',
           policy_id='steward-approval', verification={'verifier_ids': ['pat'], 'independent': True,
                                                       'criteria': ['Rehearsal completed']})
    contract = {'agreement_id': 'rehearsal', 'version': 1}
    for actor in ('sam', 'jo'):
        submit(actor, 'accept', 'rehearsal', **contract)
    submit('pat', 'authorize', 'rehearsal', **contract)
    submit('sam', 'activate', 'rehearsal', **contract)
    for actor in ('sam', 'jo'):
        submit(actor, 'initiate', 'rehearsal', reference='Rehearsal note', **contract)
        submit(actor, 'fulfill', 'rehearsal', reference='Delivery note', criteria=['Rehearsal completed'], **contract)
    submit('pat', 'verify', 'rehearsal', reference='Steward review', **contract)

    replayed = Collective.from_history(json.loads(json.dumps(collective.history())))
    assert replayed.project() == collective.project()
    print(json.dumps({'scope': collective.scope_id, 'events': len(replayed.project('log')),
                      'initial_match': epistemic_status(inferred),
                      'agreement': epistemic_status(replayed.project('agreements')[0]),
                      'objective': replayed.project('objectives')[0]['status']}))


if __name__ == '__main__':
    main()
