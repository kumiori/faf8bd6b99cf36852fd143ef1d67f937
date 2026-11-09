"""One declarative player command registry, used for parsing, help and dispatch."""

from dataclasses import dataclass

from game_gamer.tui.i18n import message_key

from .i18n import t


@dataclass(frozen=True)
class Command:
    name: str
    aliases: tuple[str, ...]
    description_key: str
    grammar_key: str
    screens: tuple[str, ...]
    handler: str
    help_key: str
    availability: str = 'command_availability'

    @property
    def description(self):
        return t(self.description_key)

    @property
    def grammar(self):
        return t(self.grammar_key) if self.grammar_key else ''

    @property
    def help(self):
        return t(self.help_key)


COMMANDS = (
    Command('paths', ('m',), message_key('commands.paths.label'), '', ('explorer','inspector','inbox'), 'cmd_paths', message_key('commands.paths.help')),
    Command('ecosystem', ('e',), message_key('commands.ecosystem.label'), '', ('explorer','inspector','inbox'), 'cmd_ecosystem', message_key('commands.ecosystem.help')),
    Command('gathering', ('g',), message_key('commands.gathering.label'), '', ('explorer','inspector','inbox'), 'cmd_gathering', message_key('commands.gathering.help')),
    Command('scenarios', ('s',), message_key('commands.scenarios.label'), '', ('explorer','inspector','inbox'), 'cmd_scenarios', message_key('commands.scenarios.help')),
    Command('open', ('o',), message_key('commands.open.label'), message_key('commands.open.grammar'), ('explorer','inspector','inbox'), 'cmd_open', message_key('commands.open.help')),
    Command('actions', ('a','act','available actions'), message_key('contracts.available_actions'), message_key('commands.object_grammar'), ('explorer','inspector','inbox'), 'cmd_actions', message_key('commands.actions.help')),
    Command('contracts', ('c',), message_key('commands.contracts.label'), message_key('commands.contracts.grammar'), ('explorer','inspector','inbox'), 'cmd_contracts', message_key('commands.contracts.help')),
    Command('inbox', ('i','n'), message_key('commands.inbox.label'), '', ('explorer','inspector','inbox'), 'cmd_inbox', message_key('commands.inbox.help')),
    Command('player', ('p','change player'), message_key('commands.player.label'), '', ('explorer','inspector','inbox'), 'cmd_player', message_key('commands.player.help')),
    Command('history', ('h','contract history'), message_key('commands.history.label'), message_key('commands.object_grammar'), ('explorer','inspector','inbox'), 'cmd_history', message_key('commands.history.help')),
    Command('past', (), message_key('commands.past.label'), message_key('commands.past.grammar'), ('explorer','inspector','inbox'), 'cmd_past', message_key('commands.past.help')),
    Command('list', ('l','graph','world'), message_key('commands.list.label'), '', ('explorer','inspector','inbox'), 'cmd_list', message_key('commands.list.help')),
    Command('invite', (), message_key('commands.invite.label'), '', ('explorer','inspector','inbox'), 'cmd_invite', message_key('commands.invite.help')),
    Command('connect', ('invite to connect',), message_key('contact.invite'), message_key('commands.connect.grammar'), ('explorer','inspector','inbox'), 'cmd_connect', message_key('commands.connect.help')),
    Command('respond', ('r',), message_key('commands.respond.label'), '', ('explorer','inspector','inbox'), 'cmd_respond', message_key('commands.respond.help')),
    Command('search', ('/',), message_key('commands.search.label'), message_key('commands.search.grammar'), ('explorer','inspector','inbox'), 'cmd_search', message_key('commands.search.help')),
    Command('trajectory', ('t',), message_key('commands.trajectory.label'), '', ('explorer','inspector','inbox'), 'cmd_trajectory', message_key('commands.trajectory.help')),
    Command('replay', (), message_key('commands.replay.label'), '', ('explorer','inspector','inbox'), 'cmd_replay', message_key('commands.replay.help')),
    Command('metadata', ('details',), message_key('commands.metadata.label'), message_key('commands.object_grammar'), ('explorer','inspector','inbox'), 'cmd_metadata', message_key('commands.metadata.help')),
    Command('help', ('?',), message_key('commands.help.label'), '', ('explorer','inspector','inbox'), 'cmd_help', message_key('commands.help.help')),
    Command('back', ('b','esc','\x1b','0'), message_key('controls.back'), '', ('explorer','inspector','inbox'), 'cmd_back', message_key('commands.back.help')),
    Command('quit', ('q',), message_key('commands.quit.label'), '', ('explorer','inspector','inbox'), 'cmd_quit', message_key('commands.quit.help')),
)


def parse(raw):
    raw = raw.strip()
    if raw.startswith('/'):
        return next(c for c in COMMANDS if c.name == 'search'), raw[1:].strip()
    for alias, command in sorted(((alias, c) for c in COMMANDS for alias in (c.name, *c.aliases)), key=lambda pair: -len(pair[0])):
        if raw.casefold() == alias or raw.casefold().startswith(alias + ' '):
            return command, raw[len(alias):].strip()
    return None, raw


def menu(screen):
    return tuple(c for c in COMMANDS if screen in c.screens)


def contract_aliases(world):
    # Insertion order is authoritative creation order and survives log replay.
    return {f'K-{i:03}': a['id'] for i,a in enumerate(world['agreements'].values(), 1)}


def invitation_aliases(world):
    from .invitations import records
    return {f'I-{i:03}':r['id'] for i,r in enumerate(records(world),1)}


def resolve(world, value, *, selected=None):
    """Resolve exact source IDs, stable short contract aliases or unique labels."""
    value = value.strip()
    if value.casefold() in {'latest','latest contract','last contract'}:
        return next(reversed(world['agreements']), None)
    if not value:
        return selected
    aliases = {**contract_aliases(world),**invitation_aliases(world)}
    if value.upper() in aliases:
        return aliases[value.upper()]
    from .presentation import display_label, folded
    from .projections import network
    nodes = network(world)['nodes']
    if any(n['id'] == value for n in nodes):
        return value
    matches = [n['id'] for n in nodes if folded(display_label(n)) == folded(value)]
    return matches[0] if len(matches) == 1 else None
