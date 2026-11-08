"""A contextual side panel sharing the focused screen and bound action session."""
from dataclasses import replace
import json

from game_gamer.runtime.curation_requests import records, find_object
from game_gamer.runtime.curation import canonical
from game_gamer.tui.screen import Screen
from . import curator


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
                   footer=base.footer+' · Tab Main/Panel · u Close panel')


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
        return Screen('CURATION / REVIEW QUEUE', ['All recorded requests' if curator.allowed(app) else 'Your requests'],
                      entries, 'Enter Review · b Object', route.index, route.scroll, navigation=False, wrap_entries=True)
    if page == 'review':
        request = records(world).get(route.extra['request_id'])
        if request is None:
            return Screen('CURATION REQUEST', ['Request unavailable.'], navigation=False)
        entries = []
        if not historical and curator.allowed(app) and request['status'] == 'submitted':
            entries = [('APPROVE REQUEST', ('decision', 'approve')), ('REJECT REQUEST', ('decision', 'reject')),
                       ('REQUEST CLARIFICATION', ('decision', 'request_clarification'))]
        if not historical and request['status'] == 'needs_clarification' and canonical(world, request['requester_id']) == app.playing_actor:
            entries.append(('ADD CLARIFICATION', ('clarify', request['id'])))
        if not historical and curator.allowed(app) and request['status'] == 'approved':
            entries.append(('OPEN TARGET / APPLY SEPARATELY', ('target', request['target_id'])))
        lines = ['Target: '+app.label(request['target_id']), 'Stable ID: '+request['target_id'],
                 'Type: '+request['request_type'].replace('_', ' ')+' request', 'Request ID: '+request['id'],
                 'Requester: '+app.label(request['requester_id']), 'Status: '+request['status'],
                 'Request: '+request['reason'],
                 'Approval records a review. Apply changes through a separate confirmed action.']
        if request['related_id']:
            lines += ['Related identity: '+app.label(request['related_id']), 'Related ID: '+request['related_id']]
        if request['proposed_changes']:
            lines += ['Proposed correction: '+json.dumps(request['proposed_changes'], ensure_ascii=False, sort_keys=True)]
        lines += [item['kind']+' · '+app.label(item['actor_id'])+' · '+item['reason'] for item in request['history']]
        return Screen('CURATION / REQUEST REVIEW', lines, entries, 'Enter Choose · b Queue',
                      route.index, route.scroll, navigation=False, wrap_entries=True)
    if page == 'provenance':
        record = find_object(world, route.target)
        lines = json.dumps(record, ensure_ascii=False, indent=2).splitlines()
        if route.target in world['actors']:
            from game_gamer.runtime.curation import state
            lines += json.dumps({'curation': state(world).get('profiles', {}).get(route.target)}, ensure_ascii=False, indent=2).splitlines()
        return Screen('OBJECT / PROVENANCE', lines, footer='PgUp/PgDn Scroll · b Object',
                      scroll=route.scroll, navigation=False)
    if route.target is None:
        return Screen('CONTEXT / SELECT OBJECT', ['Select an explicit object for curation.'],
                      [(app.label(key)+' · '+key, ('focus', key)) for key in choices]+
                      ([('Curator review queue' if curator.allowed(app) else 'My curation requests', ('panel', 'queue'))] if app.session else []),
                      'Tab Main view · Enter Choose', route.index, route.scroll, navigation=False, wrap_entries=True)
    obj = find_object(world, route.target)
    if obj is None:
        return Screen('CONTEXT / OBJECT UNAVAILABLE', [route.target]+(
            ['Not present in this historical state (read-only).'] if historical else []), navigation=False)
    object_type = obj.get('kind') or next((name for name, table in world.items() if route.target in table), 'object')
    entries = [('Inspect provenance', ('panel', 'provenance')), ('Object history', ('history', route.target))]
    if app.session and not historical:
        entries += [('Request correction', ('request', 'correction')),
                    ('Request profile review', ('request', 'profile_review'))]
        if route.target in world['actors']:
            entries.append(('Request duplicate merge', ('request', 'duplicate_merge')))
        entries.append(('Curator review queue' if curator.allowed(app) else 'My curation requests', ('panel', 'queue')))
    if not historical and curator.allowed(app) and route.target in world['actors']:
        entries += [('Correct profile', 'correct'), ('Hide / archive / restore', 'visibility'),
                    ('Preview verified identity merge', 'preview'), ('Reverse identity merge', 'reverse')]
    lines = ['Target: '+app.label(route.target), 'Type: '+object_type, 'Stable ID: '+route.target]
    if route.extra.get('pinned_target'):
        lines.append('Target retained after curation. Navigate in Main to follow its focus again.')
    if historical:
        lines.append('Historical context is read-only. Return to the current world to submit changes.')
    return Screen('CONTEXT / CURATION', lines, entries, 'Enter Choose · Tab Main · u Close',
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
    app.notice = 'CURATION REQUEST RECORDED' if result['ok'] else 'REQUEST FAILED · '+', '.join(result['errors'])
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
            app.notice = 'Return to the object panel before changing focus.'
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
            command['related_id'] = curator.choose_actor(app, 'OTHER POSSIBLE IDENTITY', exclude=route.target)
        command['reason'] = app.read('Reason for the curation request')
        app.write('Target: '+app.label(route.target)+' · '+route.target)
        if app.confirm('SUBMIT THIS CURATION REQUEST?'):
            record(app, command, version)
    elif action in {'decision', 'clarify'}:
        ident = route.extra['request_id']
        version = app._frame_revision
        reason = app.read('Review reason or clarification')
        request = records(app.world())[ident]
        app.write('Request: '+ident+' · Target: '+app.label(request['target_id'])+' · '+request['target_id'])
        if app.confirm('RECORD THIS CURATION REVIEW?'):
            command = {'kind': 'review_curation_request' if action == 'decision' else 'clarify_curation_request',
                       'request_id': ident, 'reason': reason}
            if action == 'decision':
                command['decision'] = value
            record(app, command, version)
    route.index = route.scroll = 0
    return True
