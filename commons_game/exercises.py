"""Workshop navigation with isolated, explicitly role-bound practice sessions."""
from game_gamer.exercises.tutorials import catalogue, TutorialSession
from game_gamer.tui.screen import Screen
from .reconstruction import exercise_available


def exercise_menu(app):
    entries = [(f'Tutorial {index:02} · {item["title"]} · isolated practice', ('tutorial', item['id']))
               for index, item in enumerate(catalogue(), 1)]
    if exercise_available(app.world()):
        from .reconstruction_transitions import REGISTRY, P
        entries.append(('Montréal · Reconstruct the Network · shared collective', REGISTRY.choice(P+'enter')))
    return Screen('EXERCISES / WORKSHOP', ['Practice in a fictional sandbox, or contribute to the collective exercise.'],
                  entries, 'Enter Choose · b Back', app.route.index, app.route.scroll)


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
    lines = ['ISOLATED PRACTICE · Main collective is separate.',
             practice.definition['title'],
             f'Step {min(practice.index+1, len(practice.definition["steps"]))}/{len(practice.definition["steps"])}']
    if practice.complete:
        lines += ['TUTORIAL COMPLETE', 'Inspect the resulting relationships, commitments and history below.']
    else:
        step = practice.definition['steps'][practice.index]
        lines += [step['title'], 'Acting practice role: '+step['actor_id'].title()]
    lines += [f'{len(graph["edges"])} graph edges · {len(snapshot["world"]["commitments"])} commitments']
    lines += [a['label']+' · '+a['status']+' · outcome '+a['outcome_status']
              for a in snapshot['world']['agreements'].values()]
    lines += [r['kind'].replace('_', ' ')+' · '+r['status'] for r in snapshot['world']['relationships'].values()]
    lines += ['Recent history']+[e['kind'] for e in practice.collective.project('log')[-5:]]
    entries = ([] if practice.complete else [('PERFORM THIS STEP', 'perform')])
    entries += [('INSPECT PRACTICE GRAPH', 'graph'), ('RESTART THIS TUTORIAL', 'reset'),
                ('RETURN TO EXERCISES', 'back')]
    return Screen('TUTORIAL / '+practice.definition['title'].upper(), lines, entries,
                  'Enter Choose · b Exercises', app.route.index, app.route.scroll,
                  navigation_text='ISOLATED PRACTICE | Main-world navigation remains available through m/e/g/s')


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
            if app.confirm('RESTART THIS PRACTICE?'):
                app._tutorial_sessions.pop(app.route.target, None)
                app.route.index = 0
        elif action == 'graph':
            app.push('tutorial_graph', app.route.target)
        elif action == 'perform':
            index = practice.index
            step = practice.definition['steps'][index]
            app.write(step['title'])
            if app.confirm('CONTINUE AS '+step['actor_id'].upper()+' IN PRACTICE?'):
                result = practice.perform(index)
                expected = step.get('expected_errors', [])
                app.notice = ('STEP COMPLETE' if result['ok'] else 'EXPECTED REJECTION: '+', '.join(result['errors'])
                              if result['errors'] == expected else 'STEP FAILED: '+', '.join(result['errors']))
                app.route.index = 0
    else:
        return False
    return True


def tutorial_graph(app):
    practice = session(app)
    graph = practice.collective.project('network')
    from game_gamer.tui.network import focus_graph, draw_graph
    visual = focus_graph(graph, 'learner', scope='whole', limit=len(graph['nodes']))
    lines, styles = draw_graph(visual, max(8, app.width-2), max(3, app.height-10), selected='learner', plain=app.plain)
    return Screen('PRACTICE GRAPH', ['Fictional tutorial world', *lines], footer='b Tutorial',
                  styles=[(y+1,x,length,fg,bg,bold) for y,x,length,fg,bg,bold in styles], raster_start=1,
                  show_entries=False)
