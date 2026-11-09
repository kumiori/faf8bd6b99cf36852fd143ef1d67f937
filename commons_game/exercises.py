"""Workshop navigation with isolated, explicitly role-bound practice sessions."""

from game_gamer.exercises.tutorials import TutorialSession, catalogue
from game_gamer.tui.errors import error_list
from game_gamer.tui.screen import Screen

from .i18n import t
from .reconstruction import exercise_available


def exercise_menu(app):
    entries = [(t('workshop.menu.tutorial_isolated_practice', index=index, title=item['title']), ('tutorial', item['id']))
               for index, item in enumerate(catalogue(), 1)]
    if exercise_available(app.world()):
        from .reconstruction_transitions import REGISTRY, P
        entries.append((t('workshop.menu.collective_entry', title=t('workshop.reconstruction.title')), REGISTRY.choice(P+'enter')))
    return Screen(t('workshop.menu.exercises_workshop'), [t('workshop.menu.practice_in_a_fictional_sandbox')],
                  entries, t('controls.choose_back'), app.route.index, app.route.scroll)


def session(app):
    if not hasattr(app, '_tutorial_sessions'):
        app._tutorial_sessions = {}
    key = app.route.target
    if key not in app._tutorial_sessions:
        definition = next(item for item in catalogue() if item['id'] == key)
        app._tutorial_sessions[key] = TutorialSession(definition)
    return app._tutorial_sessions[key]


def tutorial_screen(app):
    practice = session(app)
    snapshot = practice.collective.project()
    graph = snapshot['network']
    lines = [t('workshop.tutorial.isolated_practice_main_collective_is'),
             practice.definition['title'],
             t('workshop.tutorial.step', value=min(practice.index + 1, len(practice.definition['steps'])), steps_count=len(practice.definition['steps']))]
    if practice.complete:
        lines += [t('workshop.tutorial.tutorial_complete'), t('workshop.tutorial.inspect_the_resulting_relationships_commitments')]
    else:
        step = practice.definition['steps'][practice.index]
        lines += [step['title'], t('workshop.tutorial.acting_practice_role')+step['actor_id'].title()]
    lines += [t('workshop.tutorial.graph_edges_commitments', edges_count=len(graph['edges']), commitments_count=len(snapshot['world']['commitments']))]
    lines += [a['label']+' · '+a['status']+' · outcome '+a['outcome_status']
              for a in snapshot['world']['agreements'].values()]
    lines += [r['kind'].replace('_', ' ')+' · '+r['status'] for r in snapshot['world']['relationships'].values()]
    lines += [t('workshop.tutorial.recent_history')]+[e['kind'] for e in practice.collective.project('log')[-5:]]
    entries = ([] if practice.complete else [(t('workshop.tutorial.perform_this_step'), 'perform')])
    entries += [(t('workshop.tutorial.inspect_practice_graph'), 'graph'), (t('workshop.tutorial.restart_this_tutorial'), 'reset'),
                (t('workshop.tutorial.return_to_exercises'), 'back')]
    return Screen(t('workshop.tutorial.screen_title', title=practice.definition['title'].upper()), lines, entries,
                  t('workshop.tutorial.enter_choose_b_exercises'), app.route.index, app.route.scroll,
                  navigation_text=t('workshop.tutorial.isolated_practice_main_world_navigation'))


def tutorial_key(app, key, screen):
    if key in {'up', 'down'}:
        app.route.index = min(max(0, app.route.index+(-1 if key == 'up' else 1)), len(screen.entries)-1)
        app.route.reveal = True
    elif key == 'enter':
        practice = session(app)
        action = screen.entries[app.route.index][1]
        if action == 'back':
            app.back()
        elif action == 'reset':
            if app.confirm(t('workshop.tutorial.restart_this_practice')):
                app._tutorial_sessions.pop(app.route.target, None)
                app.route.index = 0
        elif action == 'graph':
            app.push('tutorial_graph', app.route.target)
        elif action == 'perform':
            index = practice.index
            step = practice.definition['steps'][index]
            app.write(step['title'])
            if app.confirm(t('workshop.tutorial.confirm_step', actor=step['actor_id'].upper())):
                result = practice.perform(index)
                expected = step.get('expected_errors', [])
                app.notice = (t('workshop.tutorial.step_complete') if result['ok'] else t('workshop.tutorial.expected_rejection')+error_list(result['errors'])
                              if result['errors'] == expected else t('workshop.tutorial.step_failed')+error_list(result['errors']))
                app.route.index = 0
    else:
        return False
    return True


def tutorial_graph(app):
    practice = session(app)
    graph = practice.collective.project('network')
    from game_gamer.tui.network import draw_graph, focus_graph
    visual = focus_graph(graph, 'learner', scope='whole', limit=len(graph['nodes']))
    lines, styles = draw_graph(visual, max(8, app.width-2), max(3, app.height-10), selected='learner', plain=app.plain)
    return Screen(t('workshop.tutorial.practice_graph'), [t('workshop.tutorial.fictional_tutorial_world'), *lines], footer=t('workshop.tutorial.b_tutorial'),
                  styles=[(y+1,x,length,fg,bg,bold) for y,x,length,fg,bg,bold in styles], raster_start=1,
                  show_entries=False)
