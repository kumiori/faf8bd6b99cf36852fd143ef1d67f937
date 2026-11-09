"""Permission-aware curator controls. All writes use the bound engine session."""

import json
from uuid import uuid4

from game_gamer.runtime.curation import canonical, merge_preview, profile, state
from game_gamer.tui.errors import error_list
from game_gamer.tui.screen import Screen

from .i18n import t


def allowed(app):
    actor = app.playing_actor
    return bool(actor and 'curator' in app.world()['actors'][actor]['roles']
                and canonical(app.world(), actor) == actor
                and state(app.world()).get('visibility', {}).get(actor, {}).get('value') != 'archived')


def choose_actor(app, title, *, exclude=None):
    actors = [profile(app.world(), key) for key in app.world()['actors'] if key != exclude]
    return app.picker(title, actors, render=lambda actor: actor['label']+' · '+actor['id'])['id']


def screen(app):
    route = app.route
    if not allowed(app):
        return Screen(t('curation.curator_unavailable'), [t('curation.this_role_requires_an_active')])
    world = app.world()
    if route.kind == 'curator_provenance':
        actor = route.target
        details = {'original_actor': world['actors'][actor],
                   'correction': state(world).get('profiles', {}).get(actor),
                   'visibility': state(world).get('visibility', {}).get(actor),
                   'canonical_id': canonical(world, actor),
                   'merges': [row for row in state(world).get('merges', {}).values()
                              if actor in (row['source_id'], row['target_id'])]}
        return Screen(t('curation.curator_provenance'), json.dumps(details, ensure_ascii=False, indent=2).splitlines(),
                      footer=t('curation.pgup_pgdn_scroll_b_curator'), scroll=route.scroll)
    if route.kind == 'curator_merge_preview':
        preview = route.extra['preview']
        lines = [t('curation.identity_must_have_been_explicitly'),
                 t('curation.source_identity')+preview['source_id'], t('curation.canonical_identity')+preview['target_id'],
                 t('curation.relationships_touched', relationships=preview['relationships']),
                 t('curation.self_links_suppressed_in_projections', self_links_hidden=preview['self_links_hidden']),
                 t('curation.historical_records_retain_their_original'), *preview['blocked']]
        entries = [] if preview['blocked'] else [(t('curation.confirm_verified_identity_and_merge'), 'merge')]
        entries += [(t('controls.cancel_button'), 'cancel')]
        return Screen(t('curation.curator_merge_preview'), lines, entries, t('curation.enter_choose_b_cancel'), route.index)
    target = route.target or app.playing_actor
    return Screen(t('curation.curator_profile'), [profile(world, target)['label'], t('common.stable_id_prefix')+target,
                  t('curation.canonical_id')+canonical(world, target)],
                  [(t('curation.inspect_provenance'), 'provenance'), (t('curation.correct_profile'), 'correct'),
                   (t('curation.hide_archive_restore'), 'visibility'), (t('curation.preview_verified_identity_merge'), 'preview'),
                   (t('curation.reverse_an_identity_merge'), 'reverse'), (t('curation.choose_another_profile'), 'choose'),
                   (t('curation.inspect_event_history'), 'history')], t('curation.enter_choose_b_return'), route.index, route.scroll)


def write(app, command, version):
    command['key'] = 'curator-'+uuid4().hex
    result = app.submit(command, version)
    app.reset_buffer()
    app.notice = t('curation.curator_change_recorded') if result['ok'] else t('curation.action_failed')+error_list(result['errors'])
    if result['ok'] and command['kind'] in {'correct_profile', 'set_profile_visibility', 'merge_profiles', 'reverse_profile_merge'}:
        root = next((r for r in reversed(app.stack) if r.kind == 'curator' and r.extra.get('contextual')), None)
        if root:
            root.extra['pinned_target'] = command.get('target_id', root.target)
    return result


def handle(app, key, screen):
    if not allowed(app):
        app.notice = t('curation.permission_required')
        return True
    route = app.route
    if route.kind == 'curator_provenance':
        return False
    if key in {'up', 'down'}:
        route.index = min(max(0, route.index+(-1 if key == 'up' else 1)), max(0, len(screen.entries)-1))
        route.reveal = True
        return True
    if key != 'enter' or not screen.entries:
        return False
    action = screen.entries[route.index][1]
    world = app.world()
    version = app._frame_revision
    if route.kind == 'curator_merge_preview':
        if action == 'cancel':
            app.back()
            return True
        preview = route.extra['preview']
        reference = app.read(t('curation.reference_for_the_verified_identity'))
        app.write(t('curation.merge_preview_statement', source=app.label(preview['source_id']), source_id=preview['source_id'],
                    target=app.label(preview['target_id']), target_id=preview['target_id']))
        if app.confirm(t('curation.merge_these_verified_identities')):
            result = write(app, {'kind': 'merge_profiles', 'source_id': preview['source_id'],
                                'target_id': preview['target_id'], 'preview_digest': preview['digest'],
                                'identity_confirmed': True, 'reference': reference}, route.extra['version'])
            if result['ok']:
                app.back()
                app.route.target = preview['target_id']
        return True
    target = route.target
    if action == 'choose':
        route.target = choose_actor(app, t('curation.curator_select_profile'))
    elif action == 'provenance':
        app.push('curator_provenance', target)
    elif action == 'history':
        app.push('history', target)
    elif action == 'preview':
        canonical_id = choose_actor(app, t('curation.select_verified_canonical_identity'), exclude=target)
        app.push('curator_merge_preview', target, preview=merge_preview(world, target, canonical_id), version=version)
    elif action in {'correct', 'visibility'}:
        command = {'kind': 'correct_profile' if action == 'correct' else 'set_profile_visibility', 'target_id': target}
        if action == 'correct':
            fields = {'label': t('curation.fields.label'), 'motivation': t('curation.fields.motivation'),
                      'profile_role': t('curation.fields.profile_role')}
            field = app.choose(t('curation.profile_field'), list(fields), fields.__getitem__)
            command['changes'] = {field: app.read(t('curation.corrected_field', field=fields[field].lower()))}
        else:
            visibility = {'visible': t('curation.fields.visible'), 'hidden': t('curation.fields.hidden'),
                          'archived': t('curation.fields.archived')}
            command['visibility'] = app.choose(t('curation.profile_visibility'), list(visibility), visibility.__getitem__)
        command['reference'] = app.read(t('curation.source_or_reason_for_this'))
        app.write(t('curation.target_prefix')+app.label(target)+t('curation.actor')+target)
        if app.confirm(t('curation.save_this_curator_correction')):
            write(app, command, version)
    elif action == 'reverse':
        merges = [row for row in state(world).get('merges', {}).values() if row['status'] == 'active'
                  and target in (row['source_id'], row['target_id'])]
        if not merges:
            app.notice = t('curation.no_active_identity_merges')
        else:
            merge = app.picker(t('curation.reverse_identity_merge'), merges,
                               render=lambda row: row['source_id']+' → '+row['target_id'])
            reference = app.read(t('curation.reference_for_the_corrected_identity'))
            app.write(t('curation.reverse')+merge['source_id']+' → '+merge['target_id'])
            if app.confirm(t('curation.reverse_this_identity_merge')):
                write(app, {'kind': 'reverse_profile_merge', 'merge_id': merge['id'], 'reference': reference}, version)
    return True
