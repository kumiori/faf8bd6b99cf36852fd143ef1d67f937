"""Small, non-executing source adapter shared by engine and interface inspection."""
import ast
import hashlib
from importlib.util import find_spec
from pathlib import Path


def expression(node):
    return ast.unparse(node) if node is not None else None


def token(value):
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def load(module):
    spec = find_spec(module)
    if spec is None or not spec.origin or not spec.origin.endswith('.py'):
        raise ValueError('source_unavailable: ' + module)
    return ast.parse(Path(spec.origin).read_text(encoding='utf-8')), spec.origin


def provenance(module, function, node):
    return {'module': module, 'function': function, 'line': node.lineno,
            'end_line': getattr(node, 'end_lineno', node.lineno)}


def literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def name(call):
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, 'id', '')


def functions(tree):
    """Yield qualified functions without visiting their bodies twice."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name + '.' + child.name, child


def known(node, kind, registries):
    """Resolve only action-dispatch expressions; never execute inspected code."""
    if isinstance(node, ast.Name) and node.id == 'kind':
        return kind
    if isinstance(node, ast.Subscript) and expression(node) == "command['kind']":
        return kind
    if expression(node) in registries:
        return registries[expression(node)]
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left = known(node.left, kind, registries)
        right = known(node.comparators[0], kind, registries)
        if left is not None and right is not None:
            op = node.ops[0]
            if isinstance(op, ast.Eq): return left == right
            if isinstance(op, ast.NotEq): return left != right
            if isinstance(op, ast.In): return left in right
            if isinstance(op, ast.NotIn): return left not in right
        return None
    return literal(node)


def statements(body, kind, registries, conditions=()):
    """Path-sensitive action slicing; undecidable branches retain their conditions."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.If):
            yield ast.copy_location(ast.Expr(value=node.test), node.test), conditions
            value = known(node.test, kind, registries)
            if value is not False:
                yield from statements(node.body, kind, registries,
                                      conditions if value is True else (*conditions, expression(node.test)))
            if value is not True:
                yield from statements(node.orelse, kind, registries,
                                      conditions if value is False else (*conditions, 'not (' + expression(node.test) + ')'))
        elif isinstance(node, (ast.For, ast.While)):
            condition = 'for ' + expression(node.target) + ' in ' + expression(node.iter) if isinstance(node, ast.For) else expression(node.test)
            yield from statements(node.body, kind, registries, (*conditions, condition))
            yield from statements(node.orelse, kind, registries, conditions)
        elif isinstance(node, (ast.Try, ast.With)):
            yield from statements(node.body, kind, registries, conditions)
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    yield from statements(handler.body, kind, registries, (*conditions, 'except ' + str(expression(handler.type))))
                yield from statements(node.orelse, kind, registries, conditions)
                yield from statements(node.finalbody, kind, registries, conditions)
        else:
            yield node, conditions
