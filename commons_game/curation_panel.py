"""A contextual side panel sharing the focused screen and bound action session."""

import json
from dataclasses import replace

from game_gamer.runtime.curation import canonical
from game_gamer.runtime.curation_requests import find_object, records
from game_gamer.tui.errors import error_list
from game_gamer.tui.screen import Screen

from . import curator
from .i18n import t


def candidates(app, screen):
    route = app.route
    if route.kind == 'matrix':
        from .expertise import matrix
        view = matrix(app.world())
        actors = view['actors']
        if not actors:
            return []
        return list(dict.fromkeys([actors[route.row]['id'], actors[route.column]['id']])) if route.extra.get('matrix_kind', 'W') == 'W' else [actors[route.row]['id']]
    if route.kind in {'inspect', 'history_object', 'reconstruction', 'reconstruction_graph'}:
        return [route.target] if route.target else []
    if route.kind not in {'network', 'history', 'history_event'} and route.target and find_object(app.world(), route.target):
        return [route.target]
    if screen.entries:
        value = screen.entries[min(route.index, len(screen.entries)-1)][1]
        if isinstance(value, str) and find_object(app.world(), value):
            return [value]
    return []


def open_panel(app, screen):
    app.push('curator', contextual=True, panel_focus=True)
    app.route.extra['panel_page'] = 'object'


def underlying(app):
    index = next(i for i in reversed(range(len(app.stack)))
                 if app.stack[i].kind == 'curator' and app.stack[i].extra.get('contextual'))
    saved = app.stack
    original_width, original_view_width = app.width, app.view.width
    if app.width >= 90:
        app.width -= min(52, max(32, app.width//3))+1
        app.view.width = max(16, app.width-2)
    app.stack = saved[:index]
    try:
        base = app.build_screen()
        focus = candidates(app, base)
        base.region = app.route.region
        base.reveal = app.route.reveal
        historical_at = app.route.extra.get('at')
    finally:
        app.stack = saved
        app.width, app.view.width = original_width, original_view_width
    root = saved[index]
    root.extra['historical_at'] = historical_at
    if root.extra.get('pinned_target'):
        root.target = root.extra['pinned_target']
        root.extra['focus_signature'] = focus
    elif root.extra.get('focus_signature') != focus:
        root.extra['focus_signature'] = focus
        root.target = focus[0] if len(focus) == 1 else None
        root.index = root.scroll = 0
        root.extra['panel_page'] = 'object'
    return base, focus


def panel_screen(app):
    base, choices = underlying(app)
    route = app.route
    if route.kind != 'curator':
        panel = curator.screen(app)
    else:
        panel = contents(app, choices)
    route.index = min(route.index, max(0, len(panel.entries)-1))
    panel.selected = route.index
    panel.reveal = route.reveal
    return replace(base, panel=panel, panel_focused=route.extra.get('panel_focus', True),
                   footer=base.footer+t('curation.panel.tab_main_panel_u_close'))


def contents(app, choices):
    route, world = app.route, app.world()
    historical = route.extra.get('historical_at') is not None
    if historical:
        world = app.current().world_at(event=route.extra['historical_at'])
    page = route.extra.get('panel_page', 'object')
    if page == 'queue':
        rows = [request for request in records(world).values()
                if curator.allowed(app) or canonical(world, request['requester_id']) == app.playing_actor]
        entries = [(app.label(row['target_id'])+' · '+row['request_type'].replace('_', ' ')+' · '+row['status'],
                    ('review', row['id'])) for row in rows]
        return Screen(t('curation.panel.curation_review_queue'), [t('curation.panel.all_recorded_requests') if curator.allowed(app) else t('curation.panel.your_requests')],
                      entries, t('curation.panel.enter_review_b_object'), route.index, route.scroll, navigation=False, wrap_entries=True)
    if page == 'review':
        request = records(world).get(route.extra['request_id'])
        if request is None:
            return Screen(t('curation.panel.curation_request'), [t('curation.panel.request_unavailable')], navigation=False)
        entries = []
        if not historical and curator.allowed(app) and request['status'] == 'submitted':
            entries = [(t('curation.panel.approve_request'), ('decision', 'approve')), (t('curation.panel.reject_request'), ('decision', 'reject')),
                       (t('curation.panel.request_clarification'), ('decision', 'request_clarification'))]
        if not historical and request['status'] == 'needs_clarification' and canonical(world, request['requester_id']) == app.playing_actor:
            entries.append((t('curation.panel.add_clarification'), ('clarify', request['id'])))
        if not historical and curator.allowed(app) and request['status'] == 'approved':
            entries.append((t('curation.panel.open_target_apply_separately'), ('target', request['target_id'])))
        lines = [t('curation.target_prefix')+app.label(request['target_id']), t('common.stable_id_prefix')+request['target_id'],
                 t('curation.request_type', type=request['request_type'].replace('_', ' ')), t('curation.panel.request_id')+request['id'],
                 t('curation.panel.requester')+app.label(request['requester_id']), t('common.status_prefix')+request['status'],
                 t('curation.panel.request')+request['reason'],
                 t('curation.panel.approval_records_a_review_apply')]
        if request['related_id']:
            lines += [t('curation.panel.related_identity')+app.label(request['related_id']), t('curation.panel.related_id')+request['related_id']]
        if request['proposed_changes']:
            lines += [t('curation.panel.proposed_correction')+json.dumps(request['proposed_changes'], ensure_ascii=False, sort_keys=True)]
        lines += [item['kind']+' · '+app.label(item['actor_id'])+' · '+item['reason'] for item in request['history']]
        return Screen(t('curation.panel.curation_request_review'), lines, entries, t('curation.panel.enter_choose_b_queue'),
                      route.index, route.scroll, navigation=False, wrap_entries=True)
    if page == 'provenance':
        record = find_object(world, route.target)
        lines = json.dumps(record, ensure_ascii=False, indent=2).splitlines()
        if route.target in world['actors']:
            from game_gamer.runtime.curation import state
            lines += json.dumps({'curation': state(world).get('profiles', {}).get(route.target)}, ensure_ascii=False, indent=2).splitlines()
        return Screen(t('curation.panel.object_provenance'), lines, footer=t('curation.panel.pgup_pgdn_scroll_b_object'),
                      scroll=route.scroll, navigation=False)
    if route.target is None:
        return Screen(t('curation.panel.context_select_object'), [t('curation.panel.select_an_explicit_object_for')],
                      [(app.label(key)+' · '+key, ('focus', key)) for key in choices]+
                      ([(t('curation.panel.curator_review_queue') if curator.allowed(app) else t('curation.panel.my_curation_requests'), ('panel', 'queue'))] if app.session else []),
                      t('curation.panel.tab_main_view_enter_choose'), route.index, route.scroll, navigation=False, wrap_entries=True)
    obj = find_object(world, route.target)
    if obj is None:
        return Screen(t('curation.panel.context_object_unavailable'), [route.target]+(
            [t('curation.panel.not_present_in_this_historical')] if historical else []), navigation=False)
    object_type = obj.get('kind') or next((name for name, table in world.items() if route.target in table), 'object')
    entries = [(t('curation.inspect_provenance'), ('panel', 'provenance')), (t('curation.panel.object_history'), ('history', route.target))]
    if app.session and not historical:
        entries += [(t('curation.panel.request_correction'), ('request', 'correction')),
                    (t('curation.panel.request_profile_review'), ('request', 'profile_review'))]
        if route.target in world['actors']:
            entries.append((t('curation.panel.request_duplicate_merge'), ('request', 'duplicate_merge')))
        entries.append((t('curation.panel.curator_review_queue') if curator.allowed(app) else t('curation.panel.my_curation_requests'), ('panel', 'queue')))
    if not historical and curator.allowed(app) and route.target in world['actors']:
        entries += [(t('curation.correct_profile'), 'correct'), (t('curation.hide_archive_restore'), 'visibility'),
                    (t('curation.preview_verified_identity_merge'), 'preview'), (t('curation.panel.reverse_identity_merge'), 'reverse')]
    lines = [t('curation.target_prefix')+app.label(route.target), t('common.type_prefix')+object_type, t('common.stable_id_prefix')+route.target]
    if route.extra.get('pinned_target'):
        lines.append(t('curation.panel.target_retained_after_curation_navigate'))
    if historical:
        lines.append(t('curation.panel.historical_context_is_read_only'))
    return Screen(t('curation.panel.context_curation'), lines, entries, t('curation.panel.enter_choose_tab_main_u'),
                  route.index, route.scroll, navigation=False, wrap_entries=True)


def finish_frame(app, scroll):
    index = next(i for i in reversed(range(len(app.stack)))
                 if app.stack[i].kind == 'curator' and app.stack[i].extra.get('contextual'))
    source = app.stack[index-1]
    if isinstance(scroll, dict):
        if scroll.get('main') is not None:
            source.scroll = scroll['main']
        if scroll.get('panel') is not None:
            app.route.scroll = scroll['panel']
    source.reveal = app.route.reveal = False


def record(app, command, version):
    result = curator.write(app, command, version)
    app.notice = t('curation.panel.curation_request_recorded') if result['ok'] else t('curation.panel.request_failed')+error_list(result['errors'])
    return result


def handle(app, key, screen):
    route = app.route
    if key in {'H', 'm', 'e', 'g', 's', 'p', 'i', 'c', 'q'}:
        return False
    if key == 'u':
        app.back()
        return True
    if key in {'tab', 'backtab'}:
        if route.kind != 'curator':
            app.notice = t('curation.panel.return_to_the_object_panel')
            return True
        route.extra['panel_focus'] = not route.extra.get('panel_focus', True)
        return True
    if not route.extra.get('panel_focus', True):
        route.extra.pop('pinned_target', None)
        saved = app.stack
        app.stack = saved[:-1]
        try:
            app.handle(key, app.build_screen())
            result_stack = app.stack
        finally:
            app.stack = saved
        app.stack = [*result_stack, route]
        return True
    if route.kind != 'curator':
        if key in {'b', 'esc'}:
            app.back()
            return True
        return curator.handle(app, key, screen.panel)
    if key in {'b', 'esc'}:
        page = route.extra.get('panel_page', 'object')
        if page != 'object':
            route.extra['panel_page'] = 'queue' if page == 'review' else 'object'
            route.index = route.scroll = 0
        else:
            app.back()
        return True
    panel = screen.panel
    if key in {'up', 'down'}:
        route.index = min(max(0, route.index+(-1 if key == 'up' else 1)), max(0, len(panel.entries)-1))
        route.reveal = True
        return True
    if key in {'pageup', 'pagedown'}:
        route.scroll = max(0, route.scroll+(-1 if key == 'pageup' else 1)*max(1, app.height-10))
        return True
    if key != 'enter' or not panel.entries:
        return True
    choice = panel.entries[route.index][1]
    if isinstance(choice, str):
        # Existing curator operations retain their preview, confirmation and engine checks.
        return curator.handle(app, key, panel)
    action, value = choice
    if action == 'focus':
        route.target = value
    elif action == 'panel':
        route.extra['panel_page'] = value
    elif action == 'review':
        route.extra.update(panel_page='review', request_id=value)
    elif action == 'target':
        route.target = value
        route.extra['panel_page'] = 'object'
    elif action == 'history':
        app.push('history', value)
    elif action == 'request':
        version = app._frame_revision
        command = {'kind': 'request_curation', 'target_id': route.target, 'request_type': value}
        if value == 'duplicate_merge':
            command['related_id'] = curator.choose_actor(app, t('curation.panel.other_possible_identity'), exclude=route.target)
        command['reason'] = app.read(t('curation.panel.reason_for_the_curation_request'))
        app.write(t('curation.target_prefix')+app.label(route.target)+' · '+route.target)
        if app.confirm(t('curation.panel.submit_this_curation_request')):
            record(app, command, version)
    elif action in {'decision', 'clarify'}:
        ident = route.extra['request_id']
        version = app._frame_revision
        reason = app.read(t('curation.panel.review_reason_or_clarification'))
        request = records(app.world())[ident]
        app.write(t('curation.panel.request')+ident+t('curation.panel.target')+app.label(request['target_id'])+' · '+request['target_id'])
        if app.confirm(t('curation.panel.record_this_curation_review')):
            command = {'kind': 'review_curation_request' if action == 'decision' else 'clarify_curation_request',
                       'request_id': ident, 'reason': reason}
            if action == 'decision':
                command['decision'] = value
            record(app, command, version)
    route.index = route.scroll = 0
    return True
