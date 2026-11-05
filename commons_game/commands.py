"""One declarative player command registry, used for parsing, help and dispatch."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    aliases: tuple[str, ...]
    description: str
    grammar: str
    screens: tuple[str, ...]
    handler: str
    help: str
    availability: str = 'command_availability'


COMMANDS = (
    Command('paths', ('m',), 'Choose a path', '', ('explorer','inspector','inbox'), 'cmd_paths', 'Choose a mode in the same saved world.'),
    Command('ecosystem', ('e',), 'Ecosystem mode', '', ('explorer','inspector','inbox'), 'cmd_ecosystem', 'Explore the current world; does not start or reset a simulation.'),
    Command('gathering', ('g',), 'Gathering mode', '', ('explorer','inspector','inbox'), 'cmd_gathering', 'Inspect collective event conditions in the same world.'),
    Command('scenarios', ('s',), 'Scenarios mode', '', ('explorer','inspector','inbox'), 'cmd_scenarios', 'Explore strategy and agreement possibilities without changing worlds.'),
    Command('open', ('o',), 'Inspect selected object', '[name, number or contract reference]', ('explorer','inspector','inbox'), 'cmd_open', 'Enter or a number inspects an item. open latest contract finds the newest proposal in this world.'),
    Command('actions', ('a','act','available actions'), 'Available actions', '[object]', ('explorer','inspector','inbox'), 'cmd_actions', 'Shows actions permitted by the engine for your current simulated actor; explains empty results.'),
    Command('contracts', ('c',), 'Contract registry', '[actor=... status=... objective=... resource=...]', ('explorer','inspector','inbox'), 'cmd_contracts', 'Browse all contracts, or the selected person\'s contracts. No ID is required.'),
    Command('inbox', ('i','n'), 'Contract inbox', '', ('explorer','inspector','inbox'), 'cmd_inbox', 'Proposals, amendments and obligations requiring this actor\'s attention.'),
    Command('player', ('p','change player'), 'Change simulated player', '', ('explorer','inspector','inbox'), 'cmd_player', 'Select another catalogue person. This changes perspective, never the shared world or real authority.'),
    Command('history', ('h','contract history'), 'Selected object history', '[object]', ('explorer','inspector','inbox'), 'cmd_history', 'Choose a transition to inspect its historical graph; return to recover the current world.'),
    Command('past', (), 'Historical graph', '[state number] [object]', ('explorer','inspector','inbox'), 'cmd_past', 'Without arguments, opens a history selector. past 3 K-001 inspects a particular state.'),
    Command('list', ('l','graph','world'), 'World explorer', '', ('explorer','inspector','inbox'), 'cmd_list', 'Return to the typed graph projection of the current authoritative state.'),
    Command('invite', (), 'Invite to a gathering', '', ('explorer','inspector','inbox'), 'cmd_invite', 'Only worlds with a gathering objective support invitations. Other worlds explain why it is unavailable.'),
    Command('connect', ('invite to connect',), 'Invite to connect', '[person]', ('explorer','inspector','inbox'), 'cmd_connect', 'Propose contact inside the simulated game. It sends no real message and creates no contract.'),
    Command('respond', ('r',), 'Respond to pending items', '', ('explorer','inspector','inbox'), 'cmd_respond', 'Choose a pending invitation or a contract requiring your response.'),
    Command('search', ('/',), 'Search by name', '[text]', ('explorer','inspector','inbox'), 'cmd_search', '/ followed by a name filters the catalogue. / alone asks for a search term.'),
    Command('trajectory', ('t',), 'Recorded trajectory', '', ('explorer','inspector','inbox'), 'cmd_trajectory', 'Inspect recorded transitions through the pinned trajectory adapter. This is recorded simulation history, not an alternative experiment.'),
    Command('replay', (), 'Check saved history', '', ('explorer','inspector','inbox'), 'cmd_replay', 'Reconstruct the authoritative log without changing the saved world.'),
    Command('metadata', ('details',), 'Source and technical details', '[object]', ('explorer','inspector','inbox'), 'cmd_metadata', 'Show source IDs and capture metadata on demand. Raw questionnaire answers and contact information are never imported.'),
    Command('help', ('?',), 'Contextual help', '', ('explorer','inspector','inbox'), 'cmd_help', 'All listed commands have handlers; unavailable actions give a reason.'),
    Command('back', ('b','esc','\x1b','0'), 'Back', '', ('explorer','inspector','inbox'), 'cmd_back', 'Return to the previous screen without changing state.'),
    Command('quit', ('q',), 'Quit and save', '', ('explorer','inspector','inbox'), 'cmd_quit', 'Accepted events are already persisted. Quitting does not reset the world.'),
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
    from .projections import network
    from .presentation import display_label, folded
    nodes = network(world)['nodes']
    if any(n['id'] == value for n in nodes):
        return value
    matches = [n['id'] for n in nodes if folded(display_label(n)) == folded(value)]
    return matches[0] if len(matches) == 1 else None
