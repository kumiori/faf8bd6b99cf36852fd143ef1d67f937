"""Permission-aware curator controls. All writes use the bound engine session."""
import json
from uuid import uuid4

from game_gamer.runtime.curation import canonical, merge_preview, profile, state
from game_gamer.tui.screen import Screen


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
        return Screen('CURATOR UNAVAILABLE', ['This role requires an active curator permission.'])
    world = app.world()
    if route.kind == 'curator_provenance':
        actor = route.target
        details = {'original_actor': world['actors'][actor],
                   'correction': state(world).get('profiles', {}).get(actor),
                   'visibility': state(world).get('visibility', {}).get(actor),
                   'canonical_id': canonical(world, actor),
                   'merges': [row for row in state(world).get('merges', {}).values()
                              if actor in (row['source_id'], row['target_id'])]}
        return Screen('CURATOR / PROVENANCE', json.dumps(details, ensure_ascii=False, indent=2).splitlines(),
                      footer='PgUp/PgDn Scroll · b Curator', scroll=route.scroll)
    if route.kind == 'curator_merge_preview':
        preview = route.extra['preview']
        lines = ['Identity must have been explicitly checked with the participant or an authoritative source.',
                 'Source identity: '+preview['source_id'], 'Canonical identity: '+preview['target_id'],
                 f"Relationships touched: {preview['relationships']}",
                 f"Self-links suppressed in projections: {preview['self_links_hidden']}",
                 'Historical records retain their original identifiers.', *preview['blocked']]
        entries = [] if preview['blocked'] else [('CONFIRM VERIFIED IDENTITY AND MERGE', 'merge')]
        entries += [('CANCEL', 'cancel')]
        return Screen('CURATOR / MERGE PREVIEW', lines, entries, 'Enter Choose · b Cancel', route.index)
    target = route.target or app.playing_actor
    return Screen('CURATOR / PROFILE', [profile(world, target)['label'], 'Stable ID: '+target,
                  'Canonical ID: '+canonical(world, target)],
                  [('Inspect provenance', 'provenance'), ('Correct profile', 'correct'),
                   ('Hide / archive / restore', 'visibility'), ('Preview verified identity merge', 'preview'),
                   ('Reverse an identity merge', 'reverse'), ('Choose another profile', 'choose'),
                   ('Inspect event history', 'history')], 'Enter Choose · b Return', route.index, route.scroll)


def write(app, command, version):
    command['key'] = 'curator-'+uuid4().hex
    result = app.submit(command, version)
    app.reset_buffer()
    app.notice = 'CURATOR CHANGE RECORDED' if result['ok'] else 'ACTION FAILED · '+', '.join(result['errors'])
    if result['ok'] and command['kind'] in {'correct_profile', 'set_profile_visibility', 'merge_profiles', 'reverse_profile_merge'}:
        root = next((r for r in reversed(app.stack) if r.kind == 'curator' and r.extra.get('contextual')), None)
        if root:
            root.extra['pinned_target'] = command.get('target_id', root.target)
    return result


def handle(app, key, screen):
    if not allowed(app):
        app.notice = 'Curator permission required.'
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
        reference = app.read('Reference for the verified identity check')
        app.write('Merge '+app.label(preview['source_id'])+' ['+preview['source_id']+'] into '+
                  app.label(preview['target_id'])+' ['+preview['target_id']+']')
        if app.confirm('MERGE THESE VERIFIED IDENTITIES?'):
            result = write(app, {'kind': 'merge_profiles', 'source_id': preview['source_id'],
                                'target_id': preview['target_id'], 'preview_digest': preview['digest'],
                                'identity_confirmed': True, 'reference': reference}, route.extra['version'])
            if result['ok']:
                app.back()
                app.route.target = preview['target_id']
        return True
    target = route.target
    if action == 'choose':
        route.target = choose_actor(app, 'CURATOR / SELECT PROFILE')
    elif action == 'provenance':
        app.push('curator_provenance', target)
    elif action == 'history':
        app.push('history', target)
    elif action == 'preview':
        canonical_id = choose_actor(app, 'SELECT VERIFIED CANONICAL IDENTITY', exclude=target)
        app.push('curator_merge_preview', target, preview=merge_preview(world, target, canonical_id), version=version)
    elif action in {'correct', 'visibility'}:
        command = {'kind': 'correct_profile' if action == 'correct' else 'set_profile_visibility', 'target_id': target}
        if action == 'correct':
            field = app.choose('PROFILE FIELD', ['label', 'motivation', 'profile_role'], lambda key: key.replace('_', ' ').title())
            command['changes'] = {field: app.read('Corrected '+field.replace('_', ' '))}
        else:
            command['visibility'] = app.choose('PROFILE VISIBILITY', ['visible', 'hidden', 'archived'], str.title)
        command['reference'] = app.read('Source or reason for this correction')
        app.write('Target: '+app.label(target)+' · Actor · '+target)
        if app.confirm('SAVE THIS CURATOR CORRECTION?'):
            write(app, command, version)
    elif action == 'reverse':
        merges = [row for row in state(world).get('merges', {}).values() if row['status'] == 'active'
                  and target in (row['source_id'], row['target_id'])]
        if not merges:
            app.notice = 'No active identity merges.'
        else:
            merge = app.picker('REVERSE IDENTITY MERGE', merges,
                               render=lambda row: row['source_id']+' → '+row['target_id'])
            reference = app.read('Reference for the corrected identity decision')
            app.write('Reverse '+merge['source_id']+' → '+merge['target_id'])
            if app.confirm('REVERSE THIS IDENTITY MERGE?'):
                write(app, {'kind': 'reverse_profile_merge', 'merge_id': merge['id'], 'reference': reference}, version)
    return True
