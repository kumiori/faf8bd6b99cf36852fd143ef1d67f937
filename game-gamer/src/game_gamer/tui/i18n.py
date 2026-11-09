"""Resolve UI messages independently of gameplay state."""
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from importlib.resources import files
from string import Formatter

import yaml

DEFAULT_LANGUAGE = 'en'
_language = ContextVar('interface_language', default=None)


class CatalogueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError(f'Invalid or duplicate catalogue key {key!r} at line {key_node.start_mark.line + 1}')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def language_tag(language):
    tag = (language or DEFAULT_LANGUAGE).strip().lower().replace('_', '-')
    return tag if re.fullmatch(r'[a-z]{2,3}(?:-[a-z0-9]{2,8})*', tag) else DEFAULT_LANGUAGE


def current_language():
    return language_tag(_language.get() or os.getenv('SADDLE_LANGUAGE'))


@contextmanager
def using_language(language):
    token = _language.set(language_tag(language) if language else current_language())
    try:
        yield
    finally:
        _language.reset(token)


@lru_cache(maxsize=32)
def load_catalogue(package, language):
    path = files(package).joinpath('locales', language + '.yaml')
    if not path.is_file():
        return {}
    return read_catalogue(path)


def read_catalogue(path):
    document = yaml.load(path.read_text(encoding='utf-8'), Loader=CatalogueLoader)

    def flatten(mapping, prefix=''):
        for key, value in mapping.items():
            if not re.fullmatch(r'[a-z][a-z0-9_-]*', key):
                raise ValueError(f'{path.name}: invalid catalogue key {prefix + key}')
            if isinstance(value, dict) and value:
                yield from flatten(value, prefix + key + '.')
            elif isinstance(value, str):
                yield prefix + key, value
            else:
                raise ValueError(f'{path.name}: expected a message at {prefix + key}')

    if not isinstance(document, dict):
        raise ValueError(f'{path.name}: expected a mapping')
    return dict(flatten(document))


@lru_cache(maxsize=32)
def messages(package, language):
    tag = language_tag(language)
    result = {}
    parts = tag.split('-')
    for candidate in dict.fromkeys([DEFAULT_LANGUAGE, *('-'.join(parts[:n]) for n in range(1, len(parts) + 1))]):
        result.update(load_catalogue(package, candidate))
    return result


def message_key(key):
    """Mark a catalogue reference stored for later resolution."""
    return key


def fields(template):
    result = set()
    for _, field, spec, conversion in Formatter().parse(template):
        if field is None:
            continue
        if not field.isidentifier() or conversion not in (None, 's', 'r', 'a') or '{' in spec or '}' in spec:
            raise ValueError(f'Invalid interpolation field {field!r}')
        result.add(field)
    return result


def format_message(template, params):
    return template.format_map(params)


def t(key, **params):
    return format_message(messages(__package__, current_language())[key], params)
