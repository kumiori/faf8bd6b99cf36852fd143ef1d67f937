"""Apply the narrow, hash-guarded shared-engine extraction to the sibling checkout."""
import ast
import hashlib
import json
from pathlib import Path
import sys

commons = Path(__file__).resolve().parents[1]
hube = commons.parent / 'game_hube'
baseline = json.loads((commons / 'docs/hube-baseline.json').read_text())
moved = {'__init__', 'get_world', '_timestamp', '_commit', '_result', '_prior',
         'submit', 'apply', 'world_at', 'save', 'load', 'replay', 'from_log'}
changes = {}
source = (hube / 'game/engine.py').read_text()
lines = source.splitlines(keepends=True)
cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Game')
for node in reversed(cls.body):
    if isinstance(node, ast.FunctionDef) and node.name in moved:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        del lines[start:node.end_lineno]
changes['game/engine.py'] = ''.join(lines).replace('class Game:', 'class Game(WorldEngine):').replace(
    'EPOCH = datetime', 'from ._shared import WorldEngine\n\nEPOCH = datetime')
source = (hube / 'game/model.py').read_text()
lines = source.splitlines(keepends=True)
node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Mutation')
start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
del lines[start:node.end_lineno]
changes['game/model.py'] = ''.join(lines).replace('from typing import Any', 'from typing import Any\nfrom ._shared import Mutation')
changes['game/persistence.py'] = '''"""Compatibility exports for the shared append-only event store."""\nfrom ._shared import load_log, save_log\n\n__all__ = ['load_log', 'save_log']\n'''
changes['game/_shared.py'] = '''"""Installed dependency or sibling source checkout; one transaction engine."""\ntry:\n    from commons_engine import WorldEngine, Mutation\nexcept ModuleNotFoundError as error:\n    if error.name != 'commons_engine':\n        raise\n    from pathlib import Path\n    import sys\n    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'game_commons'))\n    from commons_engine import WorldEngine, Mutation\nfrom commons_engine.persistence import load_log, save_log\n'''
changes['pyproject.toml'] = (hube / 'pyproject.toml').read_text().replace(
    'dependencies = []', 'dependencies = ["commons-game>=0.1.0"]')

for name, content in changes.items():
    path = hube / name
    if path.exists() and path.read_text() == content:
        continue
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != baseline.get(name):
        raise SystemExit(f'Refusing changed sibling source: {name}')

if '--apply' in sys.argv:
    for name, content in changes.items():
        (hube / name).write_text(content)
else:
    print('\n'.join(changes))
