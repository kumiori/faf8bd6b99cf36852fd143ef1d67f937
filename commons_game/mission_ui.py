"""Compact mission pages shared by both player terminal interfaces."""

from game_gamer.projections.history import HistoryFilters, history_rows
from game_gamer.projections.missions import project_mission
from game_gamer.runtime import curation, missions
from game_gamer.tui.errors import error_list
from game_gamer.tui.i18n import message_key
from game_gamer.tui.screen import Screen
from game_gamer.tui.viewport import action_form

from .i18n import t
from .presentation import clean, folded
from .tui import Cancelled

SECTIONS = {
    'why': message_key('missions.why'),
    'where': message_key('missions.where'),
    'who': message_key('missions.who'),
    'how': message_key('missions.how'),
    'requirements': message_key('missions.requirements'),
    'moves': message_key('missions.moves'),
    'activity': message_key('missions.activity'),
    'sources': message_key('missions.sources'),
    'history': message_key('missions.history'),
}
MOVES = {
    'mission_join': message_key('missions.join'),
    'mission_propose': message_key('missions.propose'),
    'mission_commit': message_key('missions.commit'),
    'mission_challenge': message_key('missions.challenge'),
    'mission_explore': message_key('missions.explore'),
    'mission_accept': message_key('missions.accept'),
    'mission_verify': message_key('missions.verify'),
    'mission_revise': message_key('missions.revise'),
}
FIELDS = {
    'need': message_key('missions.need'),
    'rationale': message_key('missions.rationale'),
    'target': message_key('missions.target'),
    'requirements': message_key('missions.requirements'),
}
TYPES = {
    'initiative': message_key('missions.initiative'),
    'actor': message_key('missions.actor'),
    'means': message_key('missions.means'),
    'step': message_key('missions.step'),
}
CARD_TYPES = {
    'actor': message_key('missions.actors'),
    'means': message_key('missions.complementary_means'),
    'finality': message_key('missions.finalities'),
    'result': message_key('missions.generic_results'),
}
STATUSES = {
    'proposed': message_key('missions.proposed'),
    'submitted': message_key('missions.submitted'),
    'offered': message_key('missions.offered'),
    'pledged': message_key('missions.pledged'),
    'accepted': message_key('missions.accepted'),
    'verified': message_key('missions.verified'),
    'applied': message_key('missions.applied'),
}


def title(mission):
    return mission['id'] + ' · ' + mission['title']


def mission_menu(world, query=''):
    return [(title(item), ('mission', ident)) for ident, item in missions.definitions(world).items()
            if folded(query) in folded(title(item))]


def _catalogue(world):
    return world['configuration'][missions.CATALOGUE_ID]


def _card(card):
    return card['id'] + ' · ' + card['title']


def _cards(catalogue, kind, ids):
    cards = catalogue['catalogues'][kind]
    return [_card(cards[ident]) + ' · ' + cards[ident]['description'] for ident in ids]


def _summary(mission):
    return t('missions.summary', version=mission['version'],
             verified=sum(bool(item['evidence_ids']) for item in mission['requirements']),
             total=len(mission['requirements']))


def _steps(mission):
    return [step for route in mission['routes'] for step in route['steps']]


def _trajectory(mission):
    steps = _steps(mission)
    order = {step['id']: number for number, step in enumerate(steps, 1)}
    lines = [t('missions.trajectory'), t('missions.current') + _summary(mission),
             t('missions.future_steps')]
    for step in steps:
        if step['status'] == 'verified':
            continue
        predecessor = step.get('after_step_id')
        suffix = t('missions.after_step', number=order[predecessor]) if predecessor else ''
        lines.append(f"{order[step['id']]}. " + clean(step['description']) + suffix)
    if len(lines) == 3:
        lines.append(t('missions.no_steps'))
    lines.append(t('missions.target') + ' · ' + mission['target'])
    return lines


def _contribution(app, record):
    detail = record.get('description', record.get('reason', ''))
    return ' · '.join([app.label(record['actor_id']), t(STATUSES[record['status']]), clean(detail)])


def _activity(app, mission, catalogue):
    lines = [t('missions.completed')]
    for item in mission['outcomes']:
        requirement = catalogue['requirements'][item['requirement_id']]
        lines.append(' · '.join([item['mission_id'], requirement['label'], clean(item['reference'])]))
    if not mission['outcomes']:
        lines.append(t('missions.no_outcomes'))
    completed_steps = {step['id']: step for step in _steps(mission) if step['status'] == 'verified'}
    lines += [t('missions.completed_step', description=clean(step['description'])) for step in completed_steps.values()]
    lines += ['', t('missions.contributions')]
    for record in mission['contributions']:
        if record['status'] == 'verified' or record['id'] in completed_steps:
            continue
        detail = _contribution(app, record)
        if record['type'] == 'propose':
            detail += ' · ' + t(TYPES[record['proposal_type']])
            if 'card_id' in record:
                detail += ' · ' + _card(catalogue['catalogues'][record['proposal_type']][record['card_id']])
        elif record['type'] == 'challenge':
            detail += ' · ' + t(FIELDS[record['field']])
            if 'replacement' in record:
                replacement = record['replacement']
                detail += ' → ' + (', '.join(catalogue['requirements'][item]['label'] for item in replacement)
                                     if record['field'] == 'requirements' else clean(replacement))
        elif record['type'] == 'commit':
            detail += ' · ' + _offer_detail(app, record, catalogue)
        lines.append(detail)
    lines += [record['mission_id'] + ' · ' + _contribution(app, record) + ' · ' +
              _offer_detail(app, record, catalogue) for record in mission['shared_commitments']
              if record['status'] == 'accepted']
    if lines[-1] == t('missions.contributions'):
        lines.append(t('missions.no_contributions'))
    return lines


def _offer_detail(app, record, catalogue):
    parts = [catalogue['requirements'][record['requirement_id']]['label']]
    if 'recipient_id' in record:
        parts.append(app.label(record['recipient_id']))
    if 'resource_id' in record:
        parts.append(str(record['quantity']) + ' × ' + app.label(record['resource_id']))
    return ' · '.join(parts)


def section_lines(app, mission, section):
    catalogue = _catalogue(app.world())
    if section == 'why':
        return [t('missions.need'), mission['need'], '', t('missions.rationale'), mission['rationale']]
    if section == 'where':
        return [t('missions.target'), mission['target'], '', t('missions.structural_result'),
                _card(mission['structural_result']), '', t('missions.finalities'),
                *_cards(catalogue, 'finality', mission['finalities']), '', t('missions.generic_results'),
                *(_cards(catalogue, 'result', mission['generic_results']) or [t('missions.no_generic_result')])]
    if section == 'who':
        return [t('missions.actors'), *_cards(catalogue, 'actor', mission['actors']), '',
                t('missions.players'), *([app.label(ident) for ident in mission['players']] or
                                         [t('missions.no_players')])]
    if section == 'how':
        return [t('missions.principal_means'), *map(_card, mission['principal_means']), '',
                t('missions.complementary_means'), *_cards(catalogue, 'means', mission['complementary_means']),
                '', *_trajectory(mission)]
    if section == 'requirements':
        return [line for item in mission['requirements'] for line in (
            item['label'] + ' · ' + t('missions.met' if item['evidence_ids'] else 'missions.outstanding'),
            item['criterion'], '')]
    if section == 'activity':
        return _activity(app, mission, catalogue)
    if section == 'sources':
        source_card = catalogue['scenario_cards'][mission['id']]
        return [t('missions.source_note'), t('missions.selection_note'), t('missions.curated_note'), '',
                t('missions.source_page', page=source_card['provenance']['page']),
                title(source_card), source_card['need'], source_card['target'],
                _card(source_card['structural_result']), *map(_card, source_card['principal_means']), '',
                *[source['file'] + ' · SHA-256 ' + source['sha256'] for source in catalogue['sources'].values()]]
    if section in CARD_TYPES:
        return _cards(catalogue, section, catalogue['catalogues'][section])
    return []


def available_moves(app, mission):
    actor = app.session.actor if app.session else None
    world = app.world()
    if not actor or not missions.active_actor(world, actor):
        return {}
    moves = {'mission_explore': []}
    if actor in mission['players']:
        moves.update(mission_propose=[], mission_commit=[], mission_challenge=[])
    else:
        moves['mission_join'] = []
    roles = world['actors'][actor]['roles']
    for record in mission['contributions']:
        author = curation.canonical(world, record['actor_id'])
        recipient = curation.canonical(world, record.get('recipient_id'))
        if record['status'] == 'offered' and actor == recipient and actor != author:
            moves.setdefault('mission_accept', []).append(record)
        if record['status'] in {'pledged', 'accepted'} and actor not in {author, recipient} and 'verifier' in roles:
            moves.setdefault('mission_verify', []).append(record)
        if (record['type'] == 'challenge' and record['status'] == 'submitted' and 'replacement' in record
                and record['mission_version'] == mission['version'] and actor != author and 'curator' in roles):
            moves.setdefault('mission_revise', []).append(record)
    return moves


def _move_entries(app, mission):
    allowed = available_moves(app, mission)
    return [(t(label), kind) for kind, label in MOVES.items() if kind in allowed]


def _collect(app, mission, kind, candidates):
    catalogue = _catalogue(app.world())
    payload = {'kind': kind, 'mission_id': mission['id']}
    if kind == 'mission_propose':
        proposal_type = app.choose(t('missions.proposal_type'), list(TYPES), lambda item: t(TYPES[item]))
        payload.update(proposal_type=proposal_type, description=app.ask(t('missions.describe')))
        if proposal_type in {'actor', 'means'}:
            cards = catalogue['catalogues'][proposal_type]
            card = app.choose(t('missions.choose_card'), [None, *cards],
                              lambda ident: _card(cards[ident]) if ident else t('missions.no_card'))
            if card:
                payload['card_id'] = card
        if proposal_type == 'step' and _steps(mission):
            step = app.choose(t('missions.choose_predecessor'), [None, *_steps(mission)],
                              lambda item: clean(item['description']) if item else t('missions.no_predecessor'))
            if step:
                payload['after_step_id'] = step['id']
    elif kind == 'mission_commit':
        requirement = app.choose(t('missions.choose_requirement'), mission['requirements'], lambda item: item['label'])
        payload.update(requirement_id=requirement['id'], description=app.ask(t('missions.describe')))
        actor = app.session.actor
        world = app.world()
        recipients = [ident for ident in world['actors'] if ident != actor and missions.active_actor(world, ident)]
        resources = [item for item in world['resources'].values() if item['owner_id'] == actor and item['quantity'] > 0]
        resource = app.choose(t('missions.choose_resource'), [None, *resources],
                              lambda item: app.label(item['id']) if item else t('missions.responsibility')) if resources and recipients else None
        recipient = app.choose(t('missions.choose_recipient'), recipients if resource else [None, *recipients],
                               lambda ident: app.label(ident) if ident else t('missions.no_recipient'))
        if recipient:
            payload['recipient_id'] = recipient
        if resource:
            app.write(t('missions.resource_offer_note'))
            payload['resource_id'] = resource['id']
            payload['quantity'] = app.ask(t('missions.quantity', maximum=resource['quantity']), parse=int)
        if _steps(mission):
            step = app.choose(t('missions.link_step'), [None, *_steps(mission)],
                              lambda item: clean(item['description']) if item else t('missions.no_step_link'))
            if step:
                payload['proposal_id'] = step['id']
    elif kind == 'mission_challenge':
        field = app.choose(t('missions.choose_field'), list(FIELDS), lambda item: t(FIELDS[item]))
        payload.update(field=field, reason=app.ask(t('missions.reason')))
        if app.confirm(t('missions.suggest_replacement')):
            if field == 'requirements':
                current = [item['id'] for item in mission['requirements']]
                choices = [ident for ident in catalogue['requirements'] if ident not in current or len(current) > 1]
                change = app.choose(t('missions.change_requirement'), choices,
                                    lambda ident: ('− ' if ident in current else '+ ') + catalogue['requirements'][ident]['label'])
                payload['replacement'] = ([ident for ident in current if ident != change] if change in current
                                          else [*current, change])
            else:
                payload['replacement'] = app.ask(t('missions.replacement'))
    elif candidates:
        record = app.choose(t(MOVES[kind]), candidates, lambda item: _contribution(app, item))
        payload['contribution_id'] = record['id']
        app.write(_contribution(app, record))
        if kind == 'mission_revise':
            replacement = record['replacement']
            if record['field'] == 'requirements':
                replacement = ', '.join(catalogue['requirements'][item]['label'] for item in replacement)
            app.write(t(FIELDS[record['field']]) + ' → ' + clean(replacement))
        else:
            app.write(_offer_detail(app, record, catalogue))
        if kind == 'mission_verify':
            app.write(catalogue['requirements'][record['requirement_id']]['criterion'])
            payload['reference'] = app.ask(t('missions.evidence'))
    if kind != 'mission_explore' and not app.confirm(t('missions.confirm')):
        raise Cancelled
    return payload


def perform(app, mission_id, kind):
    mission = project_mission(app.world(), mission_id)
    allowed = available_moves(app, mission)
    if kind not in allowed:
        raise ValueError(t('missions.move_unavailable'))
    version = app._frame_revision
    payload = _collect(app, mission, kind, allowed[kind])
    return app.submit(payload, version)


def build(app):
    route = app.route
    mission = project_mission(app.world(), route.target)
    if route.kind == 'mission':
        entries = [(t(label), section) for section, label in SECTIONS.items()]
        return Screen(title(mission), [_summary(mission)], entries,
                      t('missions.page_keys'), route.index, route.scroll, wrap_entries=True)
    section = route.extra['section']
    entries = []
    lines = section_lines(app, mission, section)
    if section == 'moves':
        entries = _move_entries(app, mission)
        if not entries:
            lines = [t('missions.select_player')]
    elif section == 'sources':
        entries = [(t(label), kind) for kind, label in CARD_TYPES.items()]
    label = SECTIONS.get(section) or CARD_TYPES[section]
    return Screen(title(mission) + ' / ' + t(label), lines, entries,
                  t('missions.section_keys'), route.index, route.scroll, wrap_entries=True)


def handle(app, key, screen):
    route = app.route
    if key == 'd':
        app.push('mission_section', route.target, section='sources')
    elif key == 'h':
        app.push('history', history_filters=HistoryFilters(mission_id=route.target))
    elif key == 'a':
        app.push('mission_section', route.target, section='moves')
    elif key == 'enter' and screen.entries:
        selected = screen.entries[min(route.index, len(screen.entries) - 1)][1]
        if selected == 'history':
            app.push('history', history_filters=HistoryFilters(mission_id=route.target))
        elif selected in MOVES:
            app.reset_buffer()
            with action_form(app.viewport):
                receipt = perform(app, route.target, selected)
            app.reset_buffer()
            if receipt['ok'] and selected == 'mission_explore':
                app.push('mission_section', route.target, section='activity')
            elif receipt['ok']:
                app.notice = t('missions.saved')
                route.index = 0
            else:
                app.notice = t('feedback.no_state_changed') + error_list(receipt['errors'])
        else:
            app.push('mission_section', route.target, section=selected)
    else:
        return False
    return True


def show_line_history(app, mission_id):
    from game_gamer.tui.history import detail_lines

    from .global_history import label
    filters = HistoryFilters(mission_id=mission_id)
    for row in history_rows(app.current().project('log'), filters):
        app.write(f"#{row['event']['sequence']}")
        for line in detail_lines(row, 1, lambda ident: label(app, ident)):
            app.write(line)


def run_line(app, mission_id=None):
    if mission_id is None:
        items = missions.definitions(app.world())
        mission_id = app.choose(t('missions.choose_mission'), list(items), lambda ident: title(items[ident]))
    while True:
        app.refresh()
        mission = project_mission(app.world(), mission_id)
        app.view.heading(title(mission), app.context())
        app.write(_summary(mission))
        try:
            section = app.choose(t('missions.choose_section'), list(SECTIONS), lambda item: t(SECTIONS[item]))
        except Cancelled:
            return
        try:
            if section == 'moves':
                entries = _move_entries(app, mission)
                if not entries:
                    app.write(t('missions.select_player'))
                    continue
                kind = app.choose(t('missions.moves'), entries, lambda item: item[0])[1]
                if perform(app, mission_id, kind)['ok'] and kind == 'mission_explore':
                    app.refresh()
                    for line in section_lines(app, project_mission(app.world(), mission_id), 'activity'):
                        app.write(line)
            elif section == 'history':
                show_line_history(app, mission_id)
            else:
                for line in section_lines(app, mission, section):
                    app.write(line)
        except Cancelled:
            continue
