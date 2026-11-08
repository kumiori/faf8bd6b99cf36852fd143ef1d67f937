"""Stable source-registration API for imperative optional terminal interfaces.

Adapters register source modules, never a duplicate hand-written decision graph.
Unresolved control/data flow is exported explicitly rather than guessed.
"""
import ast
from dataclasses import dataclass

from .source import expression, functions, literal, load, name, provenance, token


@dataclass(frozen=True)
class InterfaceAdapter:
    id: str
    modules: tuple[str, ...]
    entry_functions: tuple[str, ...]


TERMINAL = InterfaceAdapter('terminal', tuple('game_gamer.tui.' + m for m in
    ('application', 'forms', 'navigation', 'screen', 'viewport', 'opening', 'reconstruction')),
    ('game_gamer.tui.application.TerminalGame.run',))
COMMONS = InterfaceAdapter('commons', tuple('commons_game.' + m for m in
    ('fullscreen', 'play', 'tui', 'exercises', 'reconstruction', 'reconstruction_filters', 'curator')),
    ('commons_game.fullscreen.FullScreenTerminal.run',))


def scope_of(module, function, conditions=()):
    words = ' '.join((module.rsplit('.', 1)[-1], function, *conditions)).lower()
    for scope, markers in [('exercises', ('reconstruct', 'tutorial', 'exercise')),
                           ('gathering', ('gathering',)), ('scenarios', ('scenario',)),
                           ('ecosystem', ('matrix', 'network', 'people', 'incidence', 'expertise'))]:
        if any(marker in words for marker in markers):
            return scope
    return 'shared'


def call_id(module, function, call, role):
    # Source location is provenance only. Unrelated line insertions do not rename edges.
    return module + '.' + function + '.' + role + '.' + token(expression(call))


def option_registry(fn, globals_):
    """Collect declared list branches, including mutations and literal for loops.

    This is a structural union, not execution of the provider. Runtime roster
    comprehensions stay parameterised; literal action menus retain each kind.
    """
    registry = {key: [value] for key, value in globals_.items()}
    class Bind(ast.NodeTransformer):
        def __init__(self, values): self.values = values
        def visit_Name(self, node): return self.values.get(node.id, node)
    def bind(node, env):
        from copy import deepcopy
        return Bind(env).visit(deepcopy(node))
    def visit(body, env):
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
                continue
            if isinstance(statement, ast.For) and isinstance(statement.iter, (ast.List, ast.Tuple)):
                for item in statement.iter.elts:
                    values = dict(env)
                    if isinstance(statement.target, ast.Name):
                        values[statement.target.id] = bind(item, env)
                    elif isinstance(statement.target, ast.Tuple) and isinstance(item, ast.Tuple):
                        values.update({key.id: bind(value, env) for key, value in zip(statement.target.elts, item.elts)
                                       if isinstance(key, ast.Name)})
                    visit(statement.body, values)
                visit(statement.orelse, env)
                continue
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        registry.setdefault(target.id, []).append(bind(statement.value, env))
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
                registry.setdefault(statement.target.id, []).append(bind(statement.value, env))
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.args:
                    variable = call.func.value.id
                    if call.func.attr in {'append', 'insert'}:
                        registry.setdefault(variable, []).append(ast.List(elts=[bind(call.args[-1], env)]))
                    elif call.func.attr == 'extend':
                        registry.setdefault(variable, []).append(bind(call.args[0], env))
            for field in ('body', 'orelse', 'finalbody'):
                visit(getattr(statement, field, ()), env)
    visit(fn.body, {})
    return registry


def expand_choices(choices, registry, seen=()):
    if isinstance(choices, ast.Name) and choices.id in registry and choices.id not in seen:
        return [item for value in registry[choices.id] for item in expand_choices(value, registry, (*seen, choices.id))]
    if isinstance(choices, (ast.List, ast.Set, ast.Tuple)):
        return [item for child in choices.elts for item in
                (expand_choices(child.value, registry, seen) if isinstance(child, ast.Starred) else [child])]
    if isinstance(choices, ast.Dict):
        return [key for key in choices.keys if key is not None]
    if isinstance(choices, ast.IfExp):
        return expand_choices(choices.body, registry, seen) + expand_choices(choices.orelse, registry, seen)
    return [choices]


def extract_interface(adapter):
    parsed = {module: load(module)[0] for module in adapter.modules}
    nodes, edges, diagnostics = {}, {}, []
    function_map = {}
    sites = set()

    def node(ident, kind, label, module, function, origin, conditions=(), **extra):
        nodes.setdefault(ident, {'id': ident, 'kind': kind, 'level': 'navigation',
                                'scope': scope_of(module, function, conditions), 'label': label,
                                'source': provenance(module, function, origin), **extra})
        return ident

    def edge(ident, source, target, option, module, function, origin, conditions=(), **extra):
        edges[ident] = {'id': ident, 'source': source, 'target': target, 'option': option,
                        'kind': 'navigation', 'level': 'navigation',
                        'scope': scope_of(module, function, conditions),
                        'guard': list(conditions), 'action_id': None, 'changes_world_state': False,
                        'source_code': provenance(module, function, origin),
                        'coverage_status': 'uninstrumented', 'test_refs': [], **extra}
        if edges[ident].get('instrumentation'):
            edges[ident]['coverage_status'] = 'uncovered'

    for module, tree in parsed.items():
        for function, fn in functions(tree):
            ident = module + '.' + function
            function_map[(module, function)] = ident
            node(ident, 'interaction', function, module, function, fn,
                 entry_point=ident in adapter.entry_functions)
    # Guarded AST walk keeps the exact expressions surrounding each prompt/option.
    def walk(body, conditions=()):
        for item in body:
            if isinstance(item, ast.If):
                yield ast.copy_location(ast.Expr(value=item.test), item.test), conditions
                yield from walk(item.body, (*conditions, expression(item.test)))
                yield from walk(item.orelse, (*conditions, 'not (' + expression(item.test) + ')'))
            elif isinstance(item, (ast.FunctionDef, ast.ClassDef)):
                continue
            else:
                yield item, conditions
                # Visit call expressions here, and nested bodies only in their own context.
                for field in ('body', 'orelse', 'finalbody'):
                    children = getattr(item, field, None)
                    if children:
                        yield from walk(children, conditions)
                for handler in getattr(item, 'handlers', ()):
                    yield from walk(handler.body, (*conditions, 'except ' + str(expression(handler.type))))

    for module, tree in parsed.items():
        globals_ = {n.targets[0].id: n.value for n in tree.body if isinstance(n, ast.Assign)
                    and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)}
        for function, fn in functions(tree):
            parent = function_map[module, function]
            assignments = dict(globals_)
            registry = option_registry(fn, globals_)
            for statement, conditions in walk(fn.body):
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = statement.value
                if isinstance(statement, ast.Raise) and (
                        isinstance(statement.exc, ast.Name) and statement.exc.id == 'Cancelled' or
                        isinstance(statement.exc, ast.Call) and name(statement.exc) == 'Cancelled'):
                    cancelled = parent + '.cancelled'
                    node(cancelled, 'outcome', 'Cancelled; return to caller', module, function, statement,
                         conditions, terminal=True, outcome_type='cancelled')
                    edge(cancelled + '.raise', parent, cancelled, 'Cancel', module, function, statement,
                         conditions, recovery=True, declared_option=True)
                # Do not walk nested bodies twice.
                direct = [value for field, value in ast.iter_fields(statement)
                          if field not in {'body', 'orelse', 'finalbody', 'handlers'}]
                calls = []
                for value in direct:
                    for root in (value if isinstance(value, list) else [value]):
                        if isinstance(root, ast.AST):
                            calls += [c for c in ast.walk(root) if isinstance(c, ast.Call)]
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                    calls.append(statement.value)
                for call in calls:
                    site = (module, function, call.lineno, call.col_offset)
                    if site in sites:
                        continue
                    sites.add(site)
                    callee = name(call)
                    base = call_id(module, function, call, callee)
                    if conditions:
                        base += '.' + token('\n'.join(conditions))
                    src = provenance(module, function, call)
                    # Discover implemented calls between registered source functions.
                    matches = []
                    if isinstance(call.func, ast.Name):
                        matches = [value for (m, f), value in function_map.items()
                                   if f == callee and (m == module or '.' not in f)]
                        alias = assignments.get(callee)
                        if isinstance(alias, ast.Call) and name(alias) == 'getattr' and len(alias.args) >= 2:
                            method = literal(alias.args[1])
                            if expression(alias.args[0]).endswith('.viewport') and isinstance(method, str):
                                matches += [value for (m, f), value in function_map.items()
                                            if m.endswith('.viewport') and f.rsplit('.', 1)[-1] == method]
                    elif isinstance(call.func, ast.Attribute):
                        receiver = expression(call.func.value)
                        matches = [value for (m, f), value in function_map.items()
                                   if m.rsplit('.', 1)[-1] == receiver and f == callee]
                        if receiver in {'self', 'app', 'self.forms', 'self.navigation', 'self.app'} or receiver.endswith('.viewport'):
                            own_class = function.rpartition('.')[0]
                            exact = function_map.get((module, own_class + '.' + callee))
                            if receiver.endswith('.viewport'):
                                candidate_modules = {m for m in parsed if m.endswith('.viewport')}
                            elif receiver == 'self.forms':
                                candidate_modules = {'game_gamer.tui.forms'}
                            elif receiver == 'self.navigation':
                                candidate_modules = {'game_gamer.tui.navigation'}
                            elif module.startswith('commons_game'):
                                candidate_modules = {m for m in parsed if m.startswith('commons_game')}
                            elif module == 'game_gamer.tui.screen':
                                candidate_modules = {'game_gamer.tui.application', 'commons_game.fullscreen', 'commons_game.play', 'commons_game.tui'}
                            else:
                                candidate_modules = {m for m in parsed if m.startswith('game_gamer.tui')}
                            matches = [exact] if exact and receiver == 'self' else [value for (m, f), value in function_map.items()
                                if m in candidate_modules and f.rsplit('.', 1)[-1] == callee]
                    for target in sorted(set(matches)):
                        if target != parent:
                            edge(base + '.call.' + token(target), parent, target, callee,
                                 module, function, call, conditions, kind='call', declared_option=False,
                                 resolution='source_call', instrumentation=None)
                    if callee == 'Screen' and call.args:
                        screen_id = base
                        node(screen_id, 'screen', literal(call.args[0], expression(call.args[0])),
                             module, function, call, conditions,
                             navigation=next((literal(k.value, True) for k in call.keywords if k.arg == 'navigation'), True))
                        edge(base + '.render', parent, screen_id, 'render', module, function, call,
                             conditions, kind='render', declared_option=False)
                        choices = call.args[2] if len(call.args) > 2 else next((k.value for k in call.keywords if k.arg == 'entries'), None)
                        if choices is not None:
                            question = base + '.entries'
                            node(question, 'question', 'Select an entry', module, function, call, conditions)
                            edge(question + '.open', screen_id, question, 'Choose', module, function, call,
                                 conditions, declared_option=False)
                            add_choices(question, choices, registry, module, function, call, conditions,
                                        node, edge, nodes, diagnostics)
                    elif callee in {'pick', 'choose', 'picker', 'ask', 'read', 'confirm', 'prompt'} and call.args:
                        question = base
                        prompt = literal(call.args[0], expression(call.args[0]))
                        node(question, 'question', prompt, module, function, call, conditions,
                             question_text=prompt, prompt_expression=expression(call.args[0]))
                        edge(question + '.open', parent, question, 'Ask', module, function, call,
                             conditions, declared_option=False)
                        if callee == 'confirm':
                            choices = ast.List(elts=[ast.Constant(True), ast.Constant(False)])
                        elif callee in {'ask', 'read', 'prompt'}:
                            choices = ast.Name(id='input_value')
                        else:
                            choices = call.args[1] if len(call.args) > 1 else ast.Name(id='runtime_choices')
                        add_choices(question, choices, registry, module, function, call, conditions,
                                    node, edge, nodes, diagnostics, confirmation=callee == 'confirm',
                                    input_value=callee in {'ask', 'read', 'prompt'})
                    elif callee in {'push', 'resume'} and call.args:
                        value = literal(call.args[0])
                        host = 'commons' if module.startswith('commons_game') else 'terminal'
                        route = host + '.route.' + (value if isinstance(value, str) else token(expression(call.args[0])))
                        node(route, 'route', value or expression(call.args[0]), module, function, call, conditions,
                             dynamic=not isinstance(value, str))
                        edge(base + '.navigate', parent, route, value or expression(call.args[0]),
                             module, function, call, conditions, declared_option=True,
                             resolution='source_call', instrumentation='navigation_call')
                    elif callee == 'back':
                        target = base + '.caller'
                        node(target, 'outcome', 'Return to previous route (or entry path menu)', module,
                             function, call, conditions, terminal=True)
                        edge(base + '.back', parent, target, 'Back / Cancel', module, function, call,
                             conditions, recovery=True, declared_option=True,
                             instrumentation='navigation_call', resolution='caller_stack')
                    elif callee in {'submit', 'execute', 'execute_action'} and call.args:
                        candidate = call.args[0]
                        if isinstance(candidate, ast.Dict):
                            for key, value in zip(candidate.keys, candidate.values):
                                if literal(key) == 'kind' and isinstance(literal(value), str):
                                    kind = literal(value)
                                    edge(base + '.action.' + kind, parent, 'engine.' + kind, kind,
                                         module, function, call, conditions, kind='decision', level='decision',
                                         action_id=kind, changes_world_state=True, declared_option=True)
    # A literal picker branch returns to its calling function, where subsequent
    # implemented conditionals/navigation can be explored. This is a local
    # control-flow return, not an assertion that an engine action was submitted.
    for e in list(edges.values()):
        target = nodes.get(e.get('target'))
        if target and target.get('outcome_type') == 'local_return':
            origin = nodes[e['source']]['source']
            parent = function_map[origin['module'], origin['function']]
            ident = e['id'] + '.continuation'
            edges[ident] = {'id': ident, 'source': target['id'], 'target': parent, 'option': 'Continue caller',
                           'kind': 'return', 'level': 'navigation', 'scope': e['scope'], 'declared_option': False,
                           'changes_world_state': False, 'guard': [], 'coverage_status': 'uninstrumented', 'test_refs': []}
    # Screen input is dispatched by the implemented shared run loop. This also
    # exposes global Back/Quit paths instead of assuming each screen implements one.
    for screen in list(nodes.values()):
        if screen['kind'] != 'screen' or not screen.get('navigation', True) or screen['source']['module'].endswith('.viewport'):
            continue
        module = screen['source']['module']
        host = 'commons_game' if module.startswith('commons_game') else 'game_gamer.tui'
        handlers = [ident for (m, f), ident in function_map.items() if
                    m.startswith(host) and f in {'FullScreenTerminal.handle', 'TerminalGame.handle'}]
        for target in handlers:
            ident = screen['id'] + '.input.' + token(target)
            edges[ident] = {'id': ident, 'source': screen['id'], 'target': target,
                           'option': 'Dispatch keyboard input', 'kind': 'dispatch', 'level': 'navigation',
                           'scope': screen['scope'], 'declared_option': False, 'changes_world_state': False,
                           'coverage_status': 'uninstrumented', 'test_refs': [],
                           'guard': ['run_screens: app.handle(key, screen)'],
                           'source_code': screen['source']}
            question = screen['id'] + '.entries'
            if question in nodes:
                qid = question + '.keyboard'
                edges[qid] = {**edges[ident], 'id': qid, 'source': question}
    # Propagate explicit Cancelled outcomes along the registered call graph to
    # prompts that use those providers. A failed static resolution stays visible.
    adjacency = {}
    for e in edges.values():
        if e['kind'] == 'call':
            adjacency.setdefault(e['source'], set()).add(e['target'])
    for question in list(nodes.values()):
        if question['kind'] != 'question':
            continue
        origin = question['source']
        parent = function_map[origin['module'], origin['function']]
        pending, seen = [parent], set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            cancelled = current + '.cancelled'
            if cancelled in nodes:
                ident = question['id'] + '.cancel.' + token(current)
                edges[ident] = {'id': ident, 'source': question['id'], 'target': cancelled,
                               'option': 'Cancel input', 'kind': 'recovery', 'level': 'navigation',
                               'scope': question['scope'], 'guard': ['input provider raises Cancelled'],
                               'source_code': nodes[cancelled]['source'], 'recovery': True,
                               'declared_option': True, 'changes_world_state': False,
                               'coverage_status': 'uninstrumented', 'test_refs': []}
                break
            pending.extend(sorted(adjacency.get(current, ())))
    # Connect route destinations only where the dispatch explicitly tests route.kind.
    for route in list(nodes.values()):
        if route['kind'] != 'route' or route.get('dynamic'):
            continue
        value = route['label']
        destinations = []
        for e in list(edges.values()):
            if e.get('kind') != 'render':
                continue
            target_module = nodes[e['target']]['source']['module']
            if route['id'].startswith('commons.') != target_module.startswith('commons_game.'):
                continue
            for guard in e.get('guard', []):
                if 'not (' not in guard and 'route.kind' in guard and repr(value) in guard:
                    destinations.append(e['target'])
        for target in sorted(set(destinations)):
            edges[route['id'] + '.dispatch.' + token(target)] = {
                'id': route['id'] + '.dispatch.' + token(target), 'source': route['id'], 'target': target,
                'kind': 'dispatch', 'level': 'navigation', 'scope': nodes[target]['scope'], 'option': value,
                'guard': ["route.kind == " + repr(value)], 'declared_option': False,
                'changes_world_state': False, 'test_refs': [], 'coverage_status': 'uninstrumented'}
        if not destinations:
            diagnostics.append({'severity': 'WARNING', 'code': 'unresolved_route_dispatch',
                                'node_id': route['id'], 'reason': 'Route uses a delegated or imperative screen dispatcher.'})
    return list(nodes.values()), list(edges.values()), diagnostics


def add_choices(question, choices, assignments, module, function, call, conditions,
                node, edge, nodes, diagnostics, *, confirmation=False, input_value=False):
    original = choices
    items = expand_choices(choices, assignments)
    if isinstance(choices, ast.Tuple):
        items = choices.elts
    # Identical declarations (e.g. an initial value reused by a provider) are one branch.
    items = list({expression(item): item for item in items}.values())
    if not items:
        return
    for index, item in enumerate(items):
        dynamic = isinstance(item, (ast.ListComp, ast.GeneratorExp))
        provider_expression = expression(item)
        if dynamic:
            item = item.elt
        label = literal(item, expression(item))
        destination = None
        action_id = None
        parameterised = dynamic or not isinstance(item, (ast.Constant, ast.Tuple))
        if isinstance(item, ast.Tuple) and len(item.elts) == 2:
            label = literal(item.elts[0], expression(item.elts[0]))
            target = item.elts[1]
            if isinstance(target, ast.Tuple) and target.elts and isinstance(literal(target.elts[0]), str):
                # The target is a declared route, not a rendered string.
                route_name = literal(target.elts[0])
                destination = ('commons' if module.startswith('commons_game') else 'terminal') + '.route.' + route_name
                node(destination, 'route', route_name, module, function, call, conditions)
            elif isinstance(target, ast.Dict):
                action_id = next((literal(v) for k, v in zip(target.keys, target.values) if literal(k) == 'kind'), None)
                destination = 'engine.' + action_id if isinstance(action_id, str) else None
            if isinstance(target, ast.Constant) and target.value is None and str(label).lower() == 'cancel':
                destination = question + '.cancelled'
                node(destination, 'outcome', 'Cancel and return to caller', module, function, call,
                     conditions, terminal=True, outcome_type='cancelled')
            parameterised = dynamic or any(isinstance(n, (ast.ListComp, ast.GeneratorExp)) for n in ast.walk(item))
        elif isinstance(item, ast.Constant):
            # A literal picker value is returned to its caller; subsequent control flow may be unresolved.
            destination = question + '.return'
            node(destination, 'outcome', 'Return selected value to caller', module, function, call,
                 conditions, terminal=True, outcome_type='local_return')
        if input_value:
            destination = question + '.return'
            node(destination, 'outcome', 'Return entered value', module, function, call, conditions,
                 terminal=True, outcome_type='local_return')
        ident = question + '.option.' + token(expression(item))
        # Preserve identical textual branches separately using a stable occurrence suffix.
        if ident in {question + '.option.' + token(expression(previous)) for previous in items[:index]}:
            ident += '.' + str(index)
        provider = {'expression': expression(original), 'resolved_expression': provider_expression,
                    'selection_constraints': list(conditions), 'enumeration': 'symbolic'} if parameterised or input_value else None
        edge(ident, question, destination, str(label), module, function, call, conditions,
             declared_option=True, action_id=action_id, changes_world_state=bool(action_id),
             level='decision' if action_id else 'navigation', dynamic_provider=provider,
             resolution='resolved' if destination else 'unresolved', selection_expression=expression(item),
             selection_value=literal(item), instrumentation='prompt_return' if destination and not isinstance(item, ast.Tuple) else None,
             recovery=(confirmation and literal(item) is False) or str(label).lower() == 'cancel')
        if destination is None:
            diagnostics.append({'severity': 'WARNING', 'code': 'unresolved_option', 'edge_id': ident,
                                'reason': 'Imperative option provider/handler requires an additional source adapter; no destination guessed.'})
