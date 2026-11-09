"""Commons presentation catalogue, with shared Game-Gamer widget vocabulary."""
from game_gamer.tui.i18n import current_language, format_message, messages

_SHARED_PACKAGE = 'game_gamer.tui'
_BROWSER_PREFIXES = ('web.', 'navigation.', 'branding.', 'errors.')
_BROWSER_SHARED = {
    'contracts.actions.verify', 'contracts.record_action', 'forms.reason',
    'history.events.fulfill', 'matrix.expertise.need', 'workshop.directory.layers.declared',
}


def is_browser_key(key):
    return key.startswith(_BROWSER_PREFIXES) or key in _BROWSER_SHARED


def t(key, **params):
    language = current_language()
    template = messages(__package__, language).get(key)
    if template is None:
        template = messages(_SHARED_PACKAGE, language)[key]
    return format_message(template, params)


def browser_messages(language):
    """Return presentation templates for the browser's selected language."""
    catalogue = {**messages(_SHARED_PACKAGE, language), **messages(__package__, language)}
    return {key: value for key, value in catalogue.items()
            if is_browser_key(key)}
