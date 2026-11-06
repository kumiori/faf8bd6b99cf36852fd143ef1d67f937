"""Contact invitations in the existing event-backed relationships table.

Gathering attendance remains the separate ``invited`` relationship. No new
canonical store, migration or authentication authority is introduced.
"""
from copy import deepcopy
from ..model import require

KINDS = {'draft_contact', 'send_contact', 'publish_contact', 'respond_contact', 'withdraw_contact'}
FIELDS = {
    'draft_contact': ({'id', 'recipient_id', 'message'}, {'purpose', 'context', 'expires_at'}),
    'send_contact': ({'id', 'recipient_id', 'message'}, {'purpose', 'context', 'expires_at'}),
    'publish_contact': ({'invitation_id'}, set()),
    'respond_contact': ({'invitation_id', 'response'}, {'response_message'}),
    'withdraw_contact': ({'invitation_id'}, set()),
}


def records(world):
    return [r for r in world['relationships'].values() if r['kind'] == 'contact_invitation']


def validate_context(world, context, sequence):
    """Origin is bounded source metadata, never executable terms or authority."""
    require(isinstance(context, dict) and not (set(context) -
            {'provider_id', 'requester_id', 'matching_codes', 'source_version', 'world_version'}), 'invalid_invitation_context')
    if context:
        require(set(context) == {'provider_id', 'requester_id', 'matching_codes', 'source_version', 'world_version'},
                'invalid_invitation_context')
        require(context['provider_id'] in world['actors'] and context['requester_id'] in world['actors'], 'unknown_actor')
        require(isinstance(context['matching_codes'], list) and
                all(isinstance(code, str) for code in context['matching_codes']), 'invalid_invitation_context')
        require(context['source_version'] is None or isinstance(context['source_version'], str), 'invalid_invitation_context')
        require(type(context['world_version']) is int and 0 < context['world_version'] < sequence, 'invalid_invitation_context')



def prepare(world, command, *, actor, timestamp, sequence, action):
    from .engine import instant, text
    kind = command['kind']; commit = f'commit_{sequence:06}'
    if kind in {'draft_contact', 'send_contact'}:
        iid = text(command['id'])
        # Relationship IDs share a table with connections and source assertions.
        require(not any(iid in world[table] for table in world), 'invitation_exists')
        recipient = world['actors'].get(command['recipient_id'], {})
        require(recipient.get('status') == 'active' and recipient['id'] != actor, 'invalid_recipient')
        require(world['actors'][actor]['kind'] == recipient.get('kind') == 'person', 'person_required')
        message = text(command['message']); require(len(message) <= 2000, 'invitation_message_too_long')
        purpose = command.get('purpose', '')
        require(isinstance(purpose, str) and len(purpose) <= 500, 'invalid_invitation_purpose')
        context = command.get('context', {})
        validate_context(world, context, sequence)
        expiry = command.get('expires_at')
        if expiry is not None:
            require(instant(expiry) > instant(world['configuration']['clock']['now']), 'invitation_expired')
        invitation = {'id': iid, 'kind': 'contact_invitation', 'label': 'Invitation to connect',
            'source_id': actor, 'target_id': recipient['id'], 'message': message, 'purpose': purpose,
            'context': deepcopy(context), 'status': 'draft' if kind == 'draft_contact' else 'sent',
            'created_by': actor, 'created_at': timestamp, 'expires_at': expiry, 'response': None,
            'directed': True, 'event_refs': [commit],
            'provenance': {'kind': 'simulation', 'authenticated': False, 'delivery': 'in_game_only',
                           'session': deepcopy(command.get('session'))}}
        world['relationships'][iid] = invitation
        event = 'invitation.drafted' if kind == 'draft_contact' else 'invitation.sent'
    else:
        invitation = world['relationships'].get(command['invitation_id'])
        require(invitation is not None and invitation['kind'] == 'contact_invitation', 'unknown_contact_invitation')
        require(invitation.get('expires_at') is None or
                instant(invitation['expires_at']) > instant(world['configuration']['clock']['now']), 'invitation_expired')
        if kind == 'publish_contact':
            require(invitation['source_id'] == actor, 'sender_required')
            require(invitation['status'] == 'draft', 'draft_invitation_required')
            invitation['status'] = 'sent'; event = 'invitation.sent'
        elif kind == 'withdraw_contact':
            require(invitation['source_id'] == actor, 'sender_required')
            require(invitation['status'] in {'draft', 'sent'}, 'pending_contact_invitation_required')
            invitation['status'] = 'withdrawn'; event = 'invitation.withdrawn'
        else:
            require(invitation['target_id'] == actor, 'recipient_required')
            require(invitation['status'] == 'sent', 'pending_contact_invitation_required')
            require(command['response'] in {'accept', 'decline'}, 'invalid_response')
            note = command.get('response_message', '')
            require(isinstance(note, str) and len(note) <= 2000, 'invalid_invitation_response')
            invitation['status'] = 'accepted' if command['response'] == 'accept' else 'declined'
            invitation['response'] = {'decision': command['response'], 'message': note,
                                      'actor_id': actor, 'recorded_at': timestamp}
            event = 'invitation.' + invitation['status']
            if command['response'] == 'accept':
                rid = f'acknowledged:{invitation["id"]}'
                require(rid not in world['relationships'], 'connection_exists')
                world['relationships'][rid] = {'id': rid, 'kind': 'acknowledged_connection',
                    'source_id': invitation['source_id'], 'target_id': actor, 'status': 'acknowledged',
                    'directed': False, 'invitation_id': invitation['id'], 'created_by': actor,
                    'created_at': timestamp, 'event_refs': [commit],
                    'provenance': deepcopy(invitation['provenance'])}
                action['target_ids'].append(rid)
                # The one atomic commit records both the response and connection.
                action['effects'] = ['invitation.responded', 'connection.acknowledged']
        invitation['event_refs'].append(commit)
    action['target_ids'].append(invitation['id'])
    return event


def expire(world, time, commit):
    from .engine import instant
    for item in records(world):
        if item['status'] in {'draft', 'sent'} and item.get('expires_at') and instant(item['expires_at']) <= instant(time):
            item['status'] = 'expired'; item['event_refs'].append(commit)
