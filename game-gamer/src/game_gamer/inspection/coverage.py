"""Observed transition coverage via a scoped Python profiler (tests only).

No executed-line/test-name inference: records submitted outcomes, returned prompt
values and successful navigation calls. Exceptions and opaque handlers are not
claimed as covered. No global profiler is replaced silently.
"""
from collections import defaultdict
from contextlib import contextmanager
import sys
import dis

from . import SCHEMA_VERSION


class CoverageRecorder:
    def __init__(self, graph):
        self.digest = graph['implementation_digest']
        self.edges = {e['id']: e for e in graph['edges']}
        self.transitions = defaultdict(set)
        self.by_site = defaultdict(list)
        for edge in graph['edges']:
            src = edge.get('source_code')
            if src and edge.get('instrumentation'):
                self.by_site[src['module'], src['function']].append(edge)

    def document(self):
        return {'schema_version': SCHEMA_VERSION, 'implementation_digest': self.digest,
                'transitions': {key: sorted(values) for key, values in sorted(self.transitions.items())}}

    @contextmanager
    def capture(self, test_ref):
        previous = sys.getprofile()
        if previous is not None and not getattr(previous, '_decision_recorder', False):
            raise RuntimeError('decision_coverage_profiler_already_active')
        def observed(ident):
            if ident in self.edges:
                self.transitions[ident].add(test_ref)
        def profile(frame, event, result):
            if previous is not None:
                previous(frame, event, result)
            if event != 'return':
                return
            function = frame.f_code.co_name
            if function not in {'submit', 'choose', 'pick', 'picker', 'ask', 'read', 'prompt', 'confirm', 'push', 'resume', 'back'}:
                return
            # Python profilers also emit "return, None" while unwinding an
            # exception. Only normal RETURN opcodes represent a traversal.
            if dis.opname[frame.f_code.co_code[frame.f_lasti]] not in {'RETURN_VALUE', 'RETURN_CONST'}:
                return
            module = frame.f_globals.get('__name__', '')
            if module == 'game_gamer.runtime.runner' and function == 'submit' and isinstance(result, dict):
                submission = frame.f_locals.get('submission')
                if submission is not None:
                    observed('engine.' + submission.action_type + ('.allowed' if result.get('ok') else '.rejected'))
            elif module == 'game_gamer.runtime.transactions' and function == 'submit' and isinstance(result, dict):
                command = frame.f_locals.get('command')
                if isinstance(command, dict) and isinstance(command.get('kind'), str):
                    observed('engine.' + command['kind'] + ('.allowed' if result.get('ok') else '.rejected'))
            if function not in {'choose', 'pick', 'picker', 'ask', 'read', 'prompt', 'confirm', 'push', 'resume', 'back'}:
                return
            # Only direct registered call sites, not all ancestors: otherwise a
            # nested picker could falsely cover the containing confirmation.
            caller = frame.f_back
            if caller is None:
                return
            mod = caller.f_globals.get('__name__', '')
            qualified = caller.f_code.co_qualname
            for edge in self.by_site.get((mod, qualified), ()):
                source = edge['source_code']
                if not source['line'] <= caller.f_lineno <= source['end_line']:
                    continue
                instrumentation = edge['instrumentation']
                if instrumentation == 'navigation_call':
                    if function != 'back' or result is not False:
                        observed(edge['id'])
                elif instrumentation == 'prompt_return' and result is not None:
                    value = edge.get('selection_value')
                    if value is not None and type(value) is type(result) and value == result:
                        observed(edge['id'])
                    elif value is None and edge.get('dynamic_provider') and edge.get('target'):
                        observed(edge['id'])
        profile._decision_recorder = True
        sys.setprofile(profile)
        try:
            yield self
        finally:
            sys.setprofile(previous)
