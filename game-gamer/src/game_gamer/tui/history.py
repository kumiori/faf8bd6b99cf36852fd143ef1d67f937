"""Localized descriptions of detached history rows."""
import json

from .i18n import message_key, t

_SUMMARIES = {
    'mission_join': message_key('history.summary.mission_join'),
    'mission_propose': message_key('history.summary.mission_propose'),
    'mission_commit': message_key('history.summary.mission_commit'),
    'mission_challenge': message_key('history.summary.mission_challenge'),
    'mission_explore': message_key('history.summary.mission_explore'),
    'mission_accept': message_key('history.summary.mission_accept'),
    'mission_verify': message_key('history.summary.mission_verify'),
    'mission_revise': message_key('history.summary.mission_revise'),
    'recall_connection': message_key('history.summary.recall_connection'),
    'record_prior_relationship': message_key('history.summary.record_prior_relationship'),
    'send_contact': message_key('history.summary.send_contact'),
    'propose': message_key('history.summary.propose'),
    'accept': message_key('history.summary.accept'),
    'amend': message_key('history.summary.amend'),
    'activate': message_key('history.summary.activate'),
    'authorize': message_key('history.summary.authorize'),
    'initiate': message_key('history.summary.initiate'),
    'fulfill': message_key('history.summary.fulfill'),
    'verify': message_key('history.summary.verify'),
    'request_curation': message_key('history.summary.request_curation'),
    'clarify_curation_request': message_key('history.summary.clarify_curation_request'),
    'correct_profile': message_key('history.summary.correct_profile'),
    'set_profile_visibility': message_key('history.summary.set_profile_visibility'),
    'merge_profiles': message_key('history.summary.merge_profiles'),
    'reverse_profile_merge': message_key('history.summary.reverse_profile_merge'),
}
_REVIEWS = {
    'approve': message_key('history.summary.curation_approved'),
    'reject': message_key('history.summary.curation_rejected'),
    'request_clarification': message_key('history.summary.curation_clarification'),
}
_DETAIL_LEVELS = (
    message_key('history.detail.overview'),
    message_key('history.detail.detailed'),
    message_key('history.detail.technical'),
)


def detail_level(level):
    return t(_DETAIL_LEVELS[level])


def overview(row, label):
    action = row['action']
    event = row['event']
    if action == 'world.initialized':
        return t('history.summary.world_initialized')
    if action == 'ecosystem.imported':
        return t('history.summary.ecosystem_imported')
    actor = label(row['actor_id'])
    if action == 'review_curation_request':
        return t(_REVIEWS[event['command']['decision']], actor=actor)
    if action in {'respond_contact', 'respond_invitation'}:
        if event['command']['response'] == 'accept':
            return t('history.summary.invitation_accepted', actor=actor)
        return t('history.summary.invitation_declined', actor=actor)
    key = _SUMMARIES.get(action)
    summary = (t(key, actor=actor) if key else
               t('history.summary.other_action', actor=actor, action=action.replace('.', ' ').replace('_', ' ')))
    command = event.get('command') or {}
    target = next((command[key] for key in ('mission_id', 'target_id', 'recipient_id', 'agreement_id', 'invitation_id', 'claim_id')
                   if command.get(key)), None)
    return t('history.summary.with_target', summary=summary, target=label(target)) if target else summary


def detail_lines(row, level, label):
    lines = [overview(row, label)]
    if level >= 1:
        lines += [t('history.detail.actor', actor=label(row['actor_id'])),
                  t('history.detail.action', action=row['action']),
                  t('history.detail.affected', objects=', '.join(label(key) for key in row['affected_ids']))]
        if row['request_status']:
            lines.append(t('history.detail.request_outcome', status=row['request_status']))
        for change in row['changes']:
            status = ''
            if change['before_status'] != change['after_status']:
                status = t('history.detail.status_change', before=change['before_status'] or t('history.detail.new'),
                           after=change['after_status'])
            if change['outcome']:
                status += t('history.detail.outcome', outcome=change['outcome'])
            lines.append(label(change['id'])+' · '+', '.join(change['fields'])+status)
            for field, values in change['values'].items():
                lines.append('  '+field+': '+_short(values['before'])+' → '+_short(values['after']))
    if level >= 2:
        lines += json.dumps(row['event'], ensure_ascii=False, indent=2).splitlines()
    return lines


def _short(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 160 else t('history.detail.truncated', value=text[:160])
