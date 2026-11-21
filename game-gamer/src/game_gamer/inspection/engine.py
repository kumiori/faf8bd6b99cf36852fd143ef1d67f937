"""Project registered runtime actions and their implemented validation/effects."""
import ast

from ..runtime.engine import FIELDS, CollectiveEngine
from ..runtime import invitations, reconstruction, curation, curation_requests, missions
from .source import expression, functions, load, name, provenance, statements

ENGINE = 'game_gamer.runtime.engine'
REGISTRIES = {'invitations.KINDS': invitations.KINDS, 'curation.FIELDS': curation.FIELDS,
              'reconstruction.FIELDS': reconstruction.FIELDS, 'curation_requests.FIELDS': curation_requests.FIELDS,
              'missions.FIELDS': missions.FIELDS,
              'self.extension_fields': CollectiveEngine.extension_fields}


def extract_engine():
    modules = [ENGINE, 'game_gamer.runtime.invitations', 'game_gamer.runtime.reconstruction',
               'game_gamer.runtime.curation', 'game_gamer.runtime.curation_requests', missions.__name__,
               'game_gamer.runtime.governance', 'game_gamer.runtime.actions']
    sources = {module: dict(functions(load(module)[0])) for module in modules}
    nodes, edges = [], []
    for kind, (required, optional) in sorted(FIELDS.items()):
        owner = next((m for m in (invitations, reconstruction, curation, curation_requests, missions) if kind in m.FIELDS), None)
        module = owner.__name__ if owner else ENGINE
        function = 'prepare' if owner else 'CollectiveEngine._prepare'
        guards, effects, events, helpers = [], [], [], []
        visited = set()

        def scan(mod, func, conditions=()):
            if (mod, func) in visited:
                return
            visited.add((mod, func))
            fn = sources[mod][func]
            for statement, when in statements(fn.body, kind, REGISTRIES, conditions):
                # A statement is never walked recursively into another control-flow body.
                calls = [n for n in ast.walk(statement) if isinstance(n, ast.Call)]
                for call in calls:
                    callee = name(call)
                    src = provenance(mod, func, call)
                    if callee in {'require', 'text', 'instant'} and call.args:
                        code = literal_code(call, callee)
                        guards.append({'condition': expression(call.args[0]), 'reason': code,
                                       'validator': callee, 'when': list(when), 'source': src})
                    elif callee == 'states':
                        guards.append({'condition': 'agreement.status in (' + ', '.join(map(expression, call.args)) + ')',
                                       'reason': 'invalid_transition', 'validator': 'states', 'when': list(when), 'source': src})
                    elif callee == 'party':
                        guards.append({'condition': "actor in agreement['parties']", 'reason': 'party_required',
                                       'validator': 'party', 'when': list(when), 'source': src})
                    helper = None
                    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                        prefix = call.func.value.id
                        target_mod = {'invitations': invitations.__name__, 'reconstruction': reconstruction.__name__,
                                      'curation': curation.__name__, 'curation_requests': curation_requests.__name__,
                                      'missions': missions.__name__}.get(prefix)
                        if target_mod and callee in sources[target_mod]:
                            helper = (target_mod, callee)
                        elif prefix == 'self' and 'CollectiveEngine.' + callee in sources[ENGINE]:
                            helper = (ENGINE, 'CollectiveEngine.' + callee)
                    elif callee in sources[mod] and callee not in {'text', 'instant'}:
                        helper = (mod, callee)
                    if callee == 'evaluate_authorisation':
                        helper = ('game_gamer.runtime.governance', callee)
                    if helper and helper[1] not in {'CollectiveEngine._prepare', 'CollectiveEngine.validate'}:
                        helpers.append({'call': expression(call), 'when': list(when), 'source': src})
                        scan(*helper, conditions=when)
                if isinstance(statement, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                    targets = getattr(statement, 'targets', [getattr(statement, 'target', None)])
                    if any(isinstance(target, (ast.Subscript, ast.Attribute)) for target in targets):
                        effects.append({'expression': expression(statement), 'when': list(when),
                                        'source': provenance(mod, func, statement)})
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id in {'summary', 'event'}:
                            events.append({'expression': expression(statement.value), 'when': list(when),
                                           'source': provenance(mod, func, statement)})
                elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                    call = statement.value
                    local_collection = (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                                        and call.func.value.id in {'seen', 'ids', 'parties', 'attendees', 'categories', 'approved'})
                    if not local_collection and name(call) in {'update', 'append', 'add', 'extend', '_release', '_close', 'expire'}:
                        effects.append({'expression': expression(call), 'when': list(when),
                                        'source': provenance(mod, func, call)})
        scan(ENGINE, 'CollectiveEngine.validate')
        scan(ENGINE, 'CollectiveEngine._prepare')
        scan('game_gamer.runtime.actions', 'ActionSubmission.command')
        scan('game_gamer.runtime.actions', 'SimulationBinding.bind')
        permissions = [g for g in guards if any(word in g['condition'] for word in
                       ('actor', 'parties', 'authority', 'session', 'authoris', 'authoriz', 'policy', 'curator'))]
        ident = 'engine.' + kind
        nodes.append({'id': ident, 'kind': 'action', 'level': 'state', 'scope': 'engine', 'label': kind,
                      'action_id': kind, 'source': provenance(module, function, sources[module][function]),
                      'input_schema': {'required': sorted(required), 'optional': sorted(optional),
                                       'envelope': ['action_id', 'actor_id', 'scope_id', 'target_id', 'expected_revision']},
                      'guards': guards, 'permissions': permissions, 'effects': effects, 'events': events,
                      'helper_calls': helpers, 'availability': {'status': 'unknown', 'reasons': ['structural_definition']},
                      'metadata_status': 'source_expressions'})
        for outcome in ('allowed', 'rejected'):
            target = ident + '.' + outcome
            nodes.append({'id': target, 'kind': 'outcome', 'level': 'state', 'scope': 'engine',
                          'label': kind + ': ' + outcome, 'terminal': True})
            edges.append({'id': ident + '.' + outcome, 'source': ident, 'target': target,
                          'kind': 'action', 'level': 'state', 'scope': 'engine', 'option': outcome,
                          'action_id': kind, 'guard': {'action_ref': ident, 'field': 'guards'},
                          'permissions': {'action_ref': ident, 'field': 'permissions'},
                          'changes_world_state': outcome == 'allowed',
                          'effects': {'action_ref': ident, 'field': 'effects'} if outcome == 'allowed' else [],
                          'recovery': outcome == 'rejected', 'coverage_status': 'uncovered',
                          'instrumentation': 'engine_submission', 'test_refs': []})
    return nodes, edges


def literal_code(call, callee):
    from .source import literal
    return literal(call.args[1], expression(call.args[1])) if len(call.args) > 1 else {
        'text': 'text_required', 'instant': 'invalid_timestamp', 'require': 'validation_failed'}[callee]
