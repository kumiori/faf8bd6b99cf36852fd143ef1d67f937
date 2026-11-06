"""Neutral actor-specific action and attention projections."""
from copy import deepcopy
from ..runtime.invitations import records


def action_options(game, actor, *, proposal=None, include_attendance=True):
    world = game.get_world()
    candidates = []
    if proposal and proposal['id'] not in world['agreements']:
        candidates.append({'kind': 'propose', **deepcopy(proposal)})
    for agreement in world['agreements'].values():
        version = agreement['versions'][agreement['current_version'] - 1]
        base = {'agreement_id': agreement['id'], 'version': version['number']}
        for kind in ('publish_proposal', 'accept', 'authorize', 'activate', 'initiate', 'fulfill', 'verify',
                     'reject', 'withdraw', 'suspend', 'resume', 'terminate', 'dispute', 'amend'):
            command = {'kind': kind, **base}
            if kind in {'initiate', 'fulfill', 'verify'}:
                command['reference'] = 'Pure availability probe; never submitted.'
            if kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
                command['reason'] = 'Pure availability probe; never submitted.'
            if kind == 'fulfill':
                command['criteria'] = deepcopy(version['verification']['criteria'])
            if kind == 'amend':
                command['terms'] = deepcopy(version['terms'])
            candidates.append(command)
    for invitation in records(world):
        base = {'invitation_id': invitation['id']}
        candidates.extend([{'kind': 'publish_contact', **base}, {'kind': 'withdraw_contact', **base},
                           {'kind': 'respond_contact', 'response': 'accept', **base},
                           {'kind': 'respond_contact', 'response': 'decline', **base}])
    if include_attendance:
        for invitation in world['relationships'].values():
            if invitation['kind'] == 'invited' and invitation['target_id'] == actor:
                candidates.extend({'kind': 'respond_invitation', 'invitation_id': invitation['id'],
                                   'response': response} for response in ('accept', 'decline'))
    result = []
    probe_key = 'projection-probe'
    keys = {e['command']['key'] for e in game.project('log') if e['command']}
    while probe_key in keys:
        probe_key += '-'
    for candidate in candidates:
        command = {**candidate, 'actor': actor, 'key': probe_key}
        errors = game.validate(command)
        action = {key: value for key, value in candidate.items()
                  if key in {'kind', 'agreement_id', 'version', 'invitation_id', 'response'}}
        result.append({'action': action, 'errors': errors})
    return result


def available_actions(game, actor, *, proposal=None, include_attendance=True):
    return [item['action'] for item in action_options(
        game, actor, proposal=proposal, include_attendance=include_attendance) if not item['errors']]


def inbox(game, actor):
    """Return objects with a pending decision or obligation for this actor."""
    attention = {'publish_proposal', 'accept', 'authorize', 'activate', 'initiate', 'fulfill', 'verify',
                 'publish_contact', 'respond_contact', 'respond_invitation'}
    items = {}
    for action in available_actions(game, actor):
        if action['kind'] not in attention:
            continue
        kind = 'agreement' if 'agreement_id' in action else 'invitation'
        target = action[kind + '_id']
        item = items.setdefault((kind, target), {'id': target, 'kind': kind, 'actions': []})
        item['actions'].append(action)
    return list(items.values())
