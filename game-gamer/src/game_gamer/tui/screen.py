"""Screen data and shared inspector composition."""
from dataclasses import dataclass, field


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


def inspector(title, lines, *, links, decisions, details, route, footer='Tab Regions · Enter Open', wrap_entries=True):
    """Keep actionable decisions separate from informational links."""
    return Screen(title, lines, links, footer, route.index, route.scroll, decisions=decisions,
                  details=details, region=route.region, decision_index=route.decision_index,
                  split_regions=True, wrap_entries=wrap_entries)


def run_screens(app):
    """Draw and dispatch a host's screens without coupling to its world."""
    while not app.finished:
        app.prepare_screen()
        screen = app.build_screen()
        route = app.route
        screen.breadcrumb = app.breadcrumbs()
        screen.region = 'explore' if route.kind == 'network' and screen.show_entries else route.region
        screen.reveal = route.reveal
        scroll = app.viewport.draw(screen, app.context(at=route.extra.get('at')), app.notice)
        route.reveal = False
        if isinstance(scroll, int) and screen.raster_start is None:
            route.scroll = scroll
        app.notice = ''
        key = app.viewport.key()
        try:
            app.handle(key, screen)
        except Cancelled:
            app.notice = 'Cancelled. No incomplete form was submitted.'
        except (ValueError, RuntimeError) as error:
            app.notice = 'Unavailable: ' + str(error).replace('_', ' ')
