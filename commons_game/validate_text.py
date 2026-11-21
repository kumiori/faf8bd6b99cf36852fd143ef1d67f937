"""Audit the Commons and Game-Gamer interface catalogues in a source checkout."""
import argparse
import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from string import Formatter

import yaml
from game_gamer.tui.i18n import fields, read_catalogue

from .i18n import is_browser_key
from .scenario import SCENARIOS

HOST_FILES = (
    '__main__', 'commands', 'curation_panel', 'curator', 'exercises', 'fullscreen',
    'global_history', 'mission_ui', 'montreal_network', 'play', 'player', 'presentation', 'profile_editor', 'reconstruction',
    'reconstruction_filters', 'reconstruction_transitions', 'scenario_catalogue', 'server', 'tui',
)
HOST = Path('commons_game')
SHARED = Path('game-gamer/src/game_gamer/tui')
KEY = r'[a-z][a-z0-9_.-]+'
JS_REFERENCE = re.compile(r'\bt\(\s*["\'](' + KEY + r')["\']')
HTML_REFERENCE = re.compile(r'\{\{(' + KEY + r')\}\}')
PAGE_DATA = {'lang', *(f'scenario.{name}' for name in SCENARIOS)}
# Identifiers, command switches, ANSI sequences, styling and punctuation are outside the catalogue.
TECHNICAL = re.compile(r'[a-zA-Z0-9_]+(?:[./:-][a-zA-Z0-9_.?=/:_-]+)+\Z')
ID_FRAGMENT = re.compile(r'(?:[a-z][a-z0-9_-]*[-.:](?:\{\})?|/[a-z]+/|https?://\{\})\Z')
PROSE = re.compile(r'[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]{2,}|[A-Za-zÀ-ÿ]{2,}[^\w\s]+$')
UI_CALLS = {'Screen', 'write', 'print', 'heading', 'prompt', 'read', 'ask', 'choose', 'picker', 'pick', 'confirm'}
UI_ATTRIBUTES = {'notice', 'title', 'footer', 'navigation_text', 'header_indicator', 'breadcrumb'}


@dataclass(frozen=True)
class Reference:
    key: str
    location: str
    params: set[str] | None = None


def _keys(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from _keys(node.body)
        yield from _keys(node.orelse)


def _literal(node, parent):
    if isinstance(node, ast.JoinedStr):
        return ''.join(part.value if isinstance(part, ast.Constant) else '{}' for part in node.values)
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and not isinstance(parent, (ast.JoinedStr, ast.Expr, ast.Compare))):
        if isinstance(parent, ast.Subscript) and parent.slice is node:
            return ''
        if isinstance(parent, ast.Dict) and node in parent.keys:
            return ''
        if isinstance(parent, ast.keyword) and parent.arg in {'id', 'kind', 'provider', 'action_reference'}:
            return ''
        return node.value
    return ''


def _human(text, *, visible=False):
    value = text.strip()
    if not value or value.startswith(('\\x1b', '--', '#')) or TECHNICAL.fullmatch(value) or ID_FRAGMENT.fullmatch(value):
        return False
    if not re.search('[A-Za-zÀ-ÿ]', value):
        return False
    return bool(PROSE.search(value) or (visible and re.search('[A-Za-zÀ-ÿ]{2,}', value)))


def _ui_argument(node, parent):
    if isinstance(parent, ast.Call) and parent.args and parent.args[0] is node:
        function = parent.func
        name = function.id if isinstance(function, ast.Name) else getattr(function, 'attr', None)
        return name in UI_CALLS
    if isinstance(parent, ast.keyword):
        return parent.arg in UI_ATTRIBUTES
    if isinstance(parent, ast.Assign):
        return any(isinstance(target, ast.Attribute) and target.attr in UI_ATTRIBUTES for target in parent.targets)
    return False


def _python(source, name):
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    references, literals = [], []
    for node in ast.walk(tree):
        parent = parents.get(node)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {'t', 'message_key', 'inbox_text'} and node.args):
            params = (None if node.func.id == 'message_key' or any(k.arg is None for k in node.keywords)
                      else {k.arg for k in node.keywords})
            references += [Reference(key, f'{name}:{node.lineno}', params) for key in _keys(node.args[0])]
        value = _literal(node, parent)
        visible = _ui_argument(node, parent)
        # This file declares developer inspection states as well as UI prompts.
        if name.endswith('/reconstruction_transitions.py') and not visible:
            continue
        if not _human(value, visible=visible):
            continue
        scope = parent
        while scope and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = parents.get(scope)
        literals.append((scope.name if scope else '<module>', value, node.lineno))
    return references, literals


class PageCopy(HTMLParser):
    def __init__(self):
        super().__init__()
        self.literals = []

    def handle_data(self, data):
        if _human(HTML_REFERENCE.sub('', data), visible=True):
            self.literals.append(('<text>', data.strip(), self.getpos()[0]))

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if (name in {'alt', 'title', 'placeholder', 'aria-label'} or
                    (tag == 'meta' and name == 'content' and ('name', 'description') in attrs)):
                if value and _human(HTML_REFERENCE.sub('', value), visible=True):
                    self.literals.append((name, value, self.getpos()[0]))


def _browser(source, name):
    literals = []
    if name.endswith('.html'):
        parser = PageCopy()
        parser.feed(source)
        literals = parser.literals
        pattern = HTML_REFERENCE
    else:
        pattern = JS_REFERENCE
        # Audit markup text/attributes and direct JS UI sinks. The browser
        # fixture tests exercise interpolated HTML and all three modes.
        patterns = (
            r'>([^<>\n$`"\']*[A-Za-z][^<>\n$`"\']*)<',
            r'\b(?:aria-label|placeholder|title|alt)="([^"\n$]+)"',
            r'''(?:\.textContent\s*=|\b(?:toast|Error|tag)\()\s*['"]([^'"\n]+)['"]''',
        )
        quoted = re.compile(r'''(?P<quote>['"])(?P<value>[^'"`\n${}]+)(?P=quote)''')
        for match in quoted.finditer(source):
            value = match['value'].strip()
            prefix = source[max(0, match.start() - 10):match.start()]
            if (not value.startswith(('/', '[', '(', '#')) and not any(mark in value for mark in '<>=')
                    and not re.search(r'(?:class|style|aria-label|placeholder|title|alt)=$', prefix)
                    and re.search(r'[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]{2,}', value)):
                literals.append(('<browser>', value, source.count('\n', 0, match.start()) + 1))
        for expression in patterns:
            for match in re.finditer(expression, source):
                value = match[1].strip()
                if _human(value, visible=True):
                    literals.append(('<browser>', value, source.count('\n', 0, match.start()) + 1))
    references = [Reference(match[1], f'{name}:{source.count(chr(10), 0, match.start()) + 1}',
                            set() if name.endswith('.html') else None)
                  for match in pattern.finditer(source)
                  if match[1] not in PAGE_DATA]
    return references, sorted(set(literals), key=lambda literal: literal[2])


def _catalogues(root, problems):
    english, translations = {}, defaultdict(dict)
    for base in (HOST, SHARED):
        directory = root / base / 'locales'
        base_english = directory / 'en.yaml'
        if not base_english.is_file():
            problems.append(f'{base}: missing en.yaml')
        default = read_catalogue(base_english) if base_english.is_file() else {}
        for key, value in default.items():
            if key in english:
                problems.append(f'{base_english}: duplicate catalogue key {key}')
            english[key] = value
        for file in sorted(directory.glob('*.yaml')):
            if file.stem == 'en':
                continue
            for key, value in read_catalogue(file).items():
                if key not in default:
                    problems.append(f'{file}: translation has no English key {key}')
                elif fields(value) != fields(default[key]):
                    problems.append(f'{file}: interpolation fields differ for {key}')
                translations[file.stem][key] = value
    return english, translations


def _files(root):
    yield from (HOST / (name + '.py') for name in HOST_FILES)
    yield from (path.relative_to(root) for path in sorted((root / SHARED).rglob('*.py'))
                if path.stem not in {'i18n', 'text', 'keyboard', 'bands', 'hack_terminal'})
    yield HOST / 'web/index.html'
    yield HOST / 'web/app.js'


def audit(root):
    problems = []
    english, translations = _catalogues(root, problems)
    params = {key: fields(value) for key, value in english.items()}
    allowlist = yaml.safe_load((root / HOST / 'locales/literal_exceptions.yml').read_text(encoding='utf-8')) or {}
    used, seen_exceptions = set(), set()
    shared = read_catalogue(root / SHARED / 'locales/en.yaml')
    for path in _files(root):
        name = path.as_posix()
        source = (root / path).read_text(encoding='utf-8')
        inspect = _python if path.suffix == '.py' else _browser
        references, literals = inspect(source, name)
        for ref in references:
            if ref.key not in (shared if path.is_relative_to(SHARED) else english):
                problems.append(f'{ref.location}: missing key {ref.key}')
                continue
            used.add(ref.key)
            if path.suffix == '.js':
                if not is_browser_key(ref.key):
                    problems.append(f'{ref.location}: {ref.key} is missing from the browser export')
                for template in (english[ref.key], *(catalogue[ref.key] for catalogue in translations.values()
                                                      if ref.key in catalogue)):
                    if any(field is not None and (spec or conversion)
                           for _, field, spec, conversion in Formatter().parse(template)):
                        problems.append(f'{ref.location}: {ref.key} uses a Python-only format specifier')
                        break
            if ref.params is not None and ref.params != params[ref.key]:
                problems.append(f'{ref.location}: {ref.key} expects {sorted(params[ref.key])}, got {sorted(ref.params)}')
        for scope, value, line in literals:
            if value in allowlist.get(name, {}).get(scope, ()):
                seen_exceptions.add((name, scope, value))
            else:
                problems.append(f'{name}:{line}: hard-coded UI text {value!r}')
    for key in sorted(english.keys() - used):
        problems.append(f'Unused key {key}')
    for name, scopes in allowlist.items():
        for scope, values in scopes.items():
            for value in values:
                if (name, scope, value) not in seen_exceptions:
                    problems.append(f'{name}: stale literal exception in {scope}: {value!r}')
    return problems, len(english), {lang: len(values) for lang, values in translations.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        problems, count, translations = audit(args.root.resolve())
    except (OSError, SyntaxError, ValueError, yaml.YAMLError) as error:
        parser.exit(1, f'Text catalogue audit failed: {error}\n')
    if problems:
        print('\n'.join(problems))
        return 1
    print(f'Text catalogue OK ({count} English keys)')
    for language, translated in sorted(translations.items()):
        print(f'{language}: {translated} translated, {count - translated} use English fallback')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
