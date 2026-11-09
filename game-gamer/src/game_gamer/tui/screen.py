"""Screen data and shared inspector composition."""

from dataclasses import dataclass, field
from time import monotonic

from .visual import ACTION, CONFIRMED, ERROR, NAVIGATION, motion_enabled

from .errors import error_message
from .i18n import t


class Cancelled(Exception):
    """A local interaction was cancelled."""


@dataclass
class Screen:
    title: str
    lines: list[str] = field(default_factory=list)
    entries: list[tuple[str, object]] = field(default_factory=list)
    footer: str = ''
    selected: int = 0
    scroll: int = 0
    # Matrix row and column highlights supplement textual markers.
    highlights: set[int] = field(default_factory=set)
    navigation: bool = True
    styles: list = field(default_factory=list)
    show_entries: bool = True
    breadcrumb: str = ''
    wrap_entries: bool = False
    decisions: list[tuple[str, object]] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    region: str = 'explore'
    decision_index: int = 0
    reveal: bool = False
    split_regions: bool = False
    raster_start: int | None = None
    fixed_rows: set[int] = field(default_factory=set)
    navigation_text: str | None = None
    refresh_interval_ms: int | None = None
    header_indicator: str = ''
    header_colour: str = '#f0c75e'
    entry_sections: dict[int, str] = field(default_factory=dict)
    panel: 'Screen | None' = None
    panel_focused: bool = True
    masthead: str = ''
    hint: str = ''
    notice_colour: str = ACTION
    pulse: tuple[int, str] | None = None


def inspector(title, lines, *, links, decisions, details, route, footer=None, wrap_entries=True):
    """Keep actionable decisions separate from informational links."""
    footer = t('controls.inspect_regions') if footer is None else footer
    return Screen(title, lines, links, footer, route.index, route.scroll, decisions=decisions,
                  details=details, region=route.region, decision_index=route.decision_index,
                  split_regions=True, wrap_entries=wrap_entries)


def record_receipt(app, result, previous_revision):
    """Style feedback from the commit receipt and animate new milestones."""
    app.notice_colour = CONFIRMED if result['ok'] else ERROR
    if not result['ok'] or result.get('state_version', 0) <= previous_revision:
        return
    for change in result['mutations']:
        before, after = change['before'] or {}, change['after']
        kind = change['entity_type']
        if (kind == 'relationship' and after.get('status') != 'retracted'
                and (not before or before.get('status') == 'retracted')
                and after.get('kind') in {'acknowledged_connection', 'recollection_claim', 'prior_relationship_claim'}):
            app.flash = CONFIRMED
            return
        if kind == 'agreement':
            number = after['current_version']
            version = after['versions'][number-1]
            old = before['versions'][number-1] if before.get('current_version') == number else {}
            if version['acceptances'].keys() - old.get('acceptances', {}).keys():
                app.flash = CONFIRMED
                return
        if kind == 'commitment' and after['status'] == 'fulfilled' and before.get('status') != 'fulfilled':
            app.flash = CONFIRMED
            return
        if kind == 'objective' and set(after.get('support_ids', ())) - set(before.get('support_ids', ())):
            app.flash = CONFIRMED
            return


def run_screens(app):
    """Draw and dispatch a host's screens without coupling to its world."""
    major = {'matrix', 'gathering', 'scenarios', 'exercises', 'history',
             'montreal_network', 'montreal_network_graph', 'network'}
    previous_route = pulse_started = None
    pulse_colour = NAVIGATION
    while not app.finished:
        app.prepare_screen()
        screen = app.build_screen()
        route = app.route
        screen.breadcrumb = app.breadcrumbs()
        decorate = getattr(app, 'decorate_screen', None)
        if decorate:
            decorate(screen)
        if screen.panel is None:
            screen.region = 'explore' if route.kind == 'network' and screen.show_entries else route.region
            screen.reveal = route.reveal
        screen.notice_colour = getattr(app, 'notice_colour', ACTION)
        flash = getattr(app, 'flash', None)
        if flash or (route is not previous_route and route.kind in major):
            pulse_started = monotonic()
            pulse_colour = flash or NAVIGATION
        previous_route = route
        if flash:
            app.flash = None
        if pulse_started is not None and motion_enabled(app.viewport):
            frame = int((monotonic()-pulse_started)/.07)
            if frame < 3:
                screen.pulse = (frame+1, pulse_colour)
                screen.refresh_interval_ms = min(screen.refresh_interval_ms or 70, 70)
            else:
                pulse_started = None
        scroll = app.viewport.draw(screen, app.context(at=route.extra.get('at')), app.notice)
        if screen.panel is not None:
            app.panel_drawn(screen, scroll)
        route.reveal = False
        if isinstance(scroll, int) and screen.raster_start is None:
            route.scroll = scroll
        poll = getattr(app.viewport, 'poll_key', None)
        navigation_key = getattr(app.viewport, 'navigation_key', None)
        if navigation_key:
            key = navigation_key(screen.refresh_interval_ms)
        else:
            key = poll(screen.refresh_interval_ms) if poll and screen.refresh_interval_ms else app.viewport.key()
        if key is None:
            continue
        if key != 'resize':
            pulse_started = None
            app.notice = ''
            app.notice_colour = ACTION
        try:
            app.handle(key, screen)
        except Cancelled:
            app.notice = t('feedback.form_cancelled')
        except (ValueError, RuntimeError) as error:
            app.notice_colour = ERROR
            app.notice = t('feedback.unavailable_prefix') + error_message(error).replace('_', ' ')
