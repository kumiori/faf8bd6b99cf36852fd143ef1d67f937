"""Collect a correction without modifying the source or canonical profile."""

from uuid import uuid4

from game_gamer.runtime.curation import PROFILE_TOPICS, profile
from game_gamer.tui.errors import error_list
from game_gamer.tui.i18n import message_key

from .i18n import t

FIELDS = {
    'label': message_key('curation.fields.label'),
    'profile_organisation': message_key('identity_ui.organisation'),
    'profile_role': message_key('curation.fields.profile_role'),
    'profile_domains': message_key('identity_ui.domains'),
    'motivation': message_key('curation.fields.motivation'),
    'profile_offers': message_key('objects.offers'),
    'profile_needs': message_key('objects.need.plural'),
}


def propose(app, target):
    actor = profile(app.world(), target)
    version = app._frame_revision
    field = app.choose(t('identity_ui.edit_title'), list(FIELDS), lambda item: t(FIELDS[item]))
    previous = actor.get(field)
    if isinstance(previous, list):
        previous = ', '.join(previous)
    app.write(t('identity_ui.current_value', value=previous or t('common.not_recorded')))
    raw = app.read(t('identity_ui.topics_prompt') if field in PROFILE_TOPICS else
                   t('curation.corrected_field', field=t(FIELDS[field]).lower()))
    value = [item.strip() for item in raw.split(',') if item.strip()] if field in PROFILE_TOPICS else raw
    reason = app.read(t('curation.panel.reason_for_the_curation_request'))
    app.write(t('curation.target_prefix')+app.label(target)+' · '+target)
    app.write(t('identity_ui.proposed_value', value=raw or t('common.not_recorded')))
    if app.confirm(t('curation.panel.submit_this_curation_request')):
        result = app.submit({'kind': 'request_curation', 'key': 'profile-'+uuid4().hex, 'target_id': target,
                             'request_type': 'correction', 'reason': reason,
                             'proposed_changes': {field: value}}, version)
        app.reset_buffer()
        if result['ok'] and app.route.kind == 'curator' and app.route.extra.get('contextual'):
            app.route.extra['pinned_target'] = target
        app.notice = t('identity_ui.correction_pending') if result['ok'] else error_list(result['errors'])
