"""Bounded curses viewport and modal controls."""
from contextlib import contextmanager
import os
import textwrap
import unicodedata

from .navigation import NAVIGATION
from .screen import Cancelled, Screen
from .text import clean, folded, clip, column_slice


class CursesViewport:
    """POSIX/ttyd viewport: bounded redraw, no growing transcript or raw ANSI input."""
    form_active = False

    def __init__(self, window, *, plain=False):
        import curses
        self.curses, self.window, self.plain = curses, window, plain
        self.last_screen = None
        self.pairs={}
        window.keypad(True)
        curses.curs_set(0)
        self.colour=curses.has_colors() and not plain and 'NO_COLOR' not in os.environ
        if self.colour:
            curses.start_color(); curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            self.highlight = curses.color_pair(1) | curses.A_BOLD
        else:
            self.highlight = curses.A_BOLD

    def colour_style(self, foreground, background=None, bold=False):
        attribute=self.curses.A_BOLD if bold else 0
        if not self.colour:return attribute
        def index(value):
            if value is None:return -1
            rgb=[int(value[i:i+2],16) for i in (1,3,5)]
            if self.curses.COLORS>=256:
                levels=[0,95,135,175,215,255]
                r,g,b=(min(range(6),key=lambda j:abs(levels[j]-v)) for v in rgb)
                return 16+36*r+6*g+b
            return self.curses.COLOR_WHITE if sum(rgb)>360 else self.curses.COLOR_BLUE
        colours=(index(foreground),index(background))
        if colours not in self.pairs and len(self.pairs)+2<self.curses.COLOR_PAIRS:
            number=len(self.pairs)+2
            self.curses.init_pair(number,*colours);self.pairs[colours]=number
        return attribute | self.curses.color_pair(self.pairs.get(colours,1))

    def size(self):
        height, width = self.window.getmaxyx()
        return width, height

    def safe(self, value):
        value = clean(value)
        if self.plain:
            value = value.replace('→', '->').replace('–', '-').replace('·', '/').replace('…', '...')
            value = unicodedata.normalize('NFKD',value).encode('ascii', 'ignore').decode('ascii')
        return value

    def put(self, row, text, style=0):
        width, height = self.size()
        if 0 <= row < height:
            try:
                clipped = clip(self.safe(text), max(0, width - 1))
                self.window.addnstr(row, 0, clipped, len(clipped), style)
            except self.curses.error:
                pass  # A resize or bottom-right cell can invalidate a draw.

    def draw(self, screen, context='', notice=''):
        self.last_screen = screen
        width, height = self.size(); self.window.erase()
        self.put(0, screen.title, self.curses.A_BOLD)
        self.put(1, context)
        if screen.navigation:
            self.put(2, NAVIGATION)
        if screen.breadcrumb:self.put(3,screen.breadcrumb)
        body_start=4 if screen.breadcrumb else 3
        body_height = max(1, height-body_start-3)
        content, painted = [], []

        def add_line(line, style=0, *, raster=False, indent=''):
            safe = self.safe(line)
            rows = [safe] if raster else textwrap.wrap(safe, max(1,width-1),
                    replace_whitespace=False, subsequent_indent=indent) or ['']
            content.extend((row, style) for row in rows)

        for i, line in enumerate(screen.lines):
            start=len(content)
            add_line(line, self.highlight if i in screen.highlights else 0,
                     raster=screen.raster_start is not None or i in screen.fixed_rows)
            # Raster/heatmap rows are bounded to viewport width and never wrap.
            if len(content)==start+1:
                painted += [(start,column,length,fg,bg,bold) for row,column,length,fg,bg,bold in screen.styles if row==i]
        decision_starts = []
        if screen.split_regions:
            add_line('DECISIONS' + ('  <' if screen.region == 'decisions' else ''), self.curses.A_BOLD)
            if not screen.decisions:
                add_line('No decision available for this actor and state.')
            for i, (label, _) in enumerate(screen.decisions):
                decision_starts.append(len(content))
                selected = screen.region == 'decisions' and i == screen.decision_index
                add_line(('> ' if selected else '  ')+label, self.curses.A_REVERSE if selected else 0, indent='  ')
            add_line('EXPLORE' + ('  <' if screen.region == 'explore' else ''), self.curses.A_BOLD)
        entry_starts = []
        for i, (label, _) in enumerate(screen.entries if screen.show_entries else []):
            entry_starts.append(len(content))
            active = screen.region == 'explore' and i == screen.selected
            prefix = '> ' if active else '  '
            text=prefix+f'[{i+1}] '+label
            parts=textwrap.wrap(self.safe(text),max(1,width-1),subsequent_indent='      ') if screen.wrap_entries else [text]
            content.extend((part,self.curses.A_REVERSE if active else 0) for part in parts)
        detail_start = len(content)
        if screen.details:
            add_line('DETAILS' + ('  <' if screen.region == 'details' else ''), self.curses.A_BOLD)
            for line in screen.details:
                add_line(line)
        scroll = min(screen.scroll, max(0, len(content)-body_height))
        selected = None
        if entry_starts and screen.region == 'explore' and screen.reveal:
            selected = entry_starts[min(screen.selected,len(entry_starts)-1)]
        if screen.reveal and screen.region == 'decisions' and decision_starts:
            selected = decision_starts[min(screen.decision_index,len(decision_starts)-1)]
        if screen.reveal and screen.region == 'details' and screen.details:
            scroll = min(detail_start, max(0,len(content)-body_height))
        if selected is not None:
            if selected < scroll:
                scroll = selected
            elif selected >= scroll+body_height:
                scroll = selected-body_height+1
        for i, (line, style) in enumerate(content[scroll:scroll+body_height], body_start):
            self.put(i, line, style)
        for row,column,length,fg,bg,bold in painted:
            if scroll<=row<scroll+body_height:
                try:
                    text = column_slice(content[row][0], column, min(length, width - 1 - column))
                    if text and column < width - 1:
                        self.window.addnstr(row-scroll+body_start, column, text, len(text),
                                            self.colour_style(fg,bg,bold))
                except self.curses.error:pass
        if len(content) > body_height:
            self.put(height-3, f'Scroll {scroll+1}/{max(1,len(content)-body_height+1)} · PgUp/PgDn')
        self.put(height-2, notice, self.curses.A_BOLD)
        # Help lists the controls when a narrow terminal clips the footer.
        self.put(height-1, ('Esc/b Back  ? Help | ' if screen.navigation else '')+(screen.footer or 'Enter Continue'))
        self.window.refresh()
        return scroll

    def message(self, screen):
        self.draw(screen)

    def key(self):
        key = self.window.get_wch()
        mapping = {self.curses.KEY_UP: 'up', self.curses.KEY_DOWN: 'down', self.curses.KEY_LEFT: 'left',
                   self.curses.KEY_RIGHT: 'right', self.curses.KEY_NPAGE: 'pagedown', self.curses.KEY_PPAGE: 'pageup',
                   self.curses.KEY_RESIZE: 'resize', self.curses.KEY_HOME: 'home', self.curses.KEY_ENTER: 'enter', '\n': 'enter', '\r': 'enter', '\x1b': 'esc'}
        mapping.update({self.curses.KEY_BTAB:'backtab','\t':'tab'})
        if key in {'\x03', '\x04'}:
            raise EOFError
        return mapping.get(key, key)

    def prompt(self, title, lines, context):
        value = ''
        while True:
            width, height = self.size()
            screen = Screen(title, list(lines)+['', '> '+value[-max(1,width-4):]], footer='Enter Confirm · Esc Cancel', navigation=False)
            screen.scroll = max(0, len(screen.lines)-(height-6))
            self.draw(screen, context)
            key = self.key()
            # Esc and the letter b must remain distinct while entering text.
            if key == 'enter': return value
            if key == 'resize': continue
            if key in {self.curses.KEY_BACKSPACE, '\x7f', '\b'}:
                value = value[:-1]
            elif key == 'esc':
                if not (value or self.form_active) or self.confirm_discard(context):
                    return None
            elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                value += key

    def confirm_discard(self, context):
        while True:
            self.draw(Screen('DISCARD UNSUBMITTED INPUT?', ['y Discard · n Keep editing'],
                             footer='Esc Return to form', navigation=False), context)
            key = self.key()
            if key in {'y', 'n', 'esc', 'b'}:
                return key == 'y'

    def choose(self, title, items, label, context, *, preview=None):
        index = 0; query = ''; scroll = 0; region = 'explore'
        while True:
            filtered = [item for item in items if folded(query) in folded(label(item))]
            index = min(index, max(0, len(filtered)-1))
            lines = ['Search: '+query, f'{len(filtered)} choices']
            if region == 'details':
                lines += ['Up/Down selects an option in the list. Tab returns to choices.',
                          '/ changes search; Enter confirms the current choice.', 'Esc/b goes back.']
                if filtered:
                    lines += ['Selected: '+label(filtered[index])]
            self.draw(Screen(title, lines, [(label(item), item) for item in filtered],
                'Enter Confirm · Tab Regions · / Search · '+('v Preview · ' if preview else '')+'Esc/b Back',
                index, scroll if region == 'explore' else 0, navigation=False,
                show_entries=region == 'explore', reveal=region == 'explore'), context)
            key = self.key()
            if key in {'b', 'q', 'esc'}:
                if not self.form_active or self.confirm_discard(context):
                    raise Cancelled
                continue
            if key in {'tab', 'backtab', '?'}:
                region = 'details' if region == 'explore' else 'explore'
                continue
            if key == '/':
                value = self.prompt('Search by name or organisation', [], context)
                if value is not None:
                    query = value; index = scroll = 0
                    region = 'explore'
            elif key in {'up', 'down'}:
                index = max(0, min(len(filtered)-1, index+(-1 if key == 'up' else 1)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif key in {'pageup', 'pagedown'}:
                index = max(0, min(len(filtered)-1, index+(-1 if key == 'pageup' else 1)*max(1,self.size()[1]-10)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif key == 'enter' and filtered:
                return filtered[index]
            elif key == 'v' and preview and filtered:
                details = preview(filtered[index]); offset = 0
                while True:
                    shown = self.draw(Screen('PROFILE PREVIEW',details,footer='PgUp/PgDn Scroll · Enter or b Return',
                                             scroll=offset,navigation=False),context)
                    key = self.key()
                    if key in {'enter','b','esc','q'}: break
                    if key in {'pageup','pagedown','up','down'}:
                        step = max(1,self.size()[1]-8) if key in {'pageup','pagedown'} else 1
                        offset = max(0,shown+(-step if key in {'pageup','up'} else step))
            elif isinstance(key,str) and key.isdigit() and key != '0' and int(key) <= len(filtered):
                return filtered[int(key)-1]


def supported(source, output):
    if os.getenv('TERM', 'dumb') == 'dumb' or not source.isatty() or not output.isatty():
        return False
    try:
        import curses
        return bool(curses)
    except ImportError:
        return False


def run_curses(run, *, plain=False):
    import curses
    import locale

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            plain = True
    return curses.wrapper(lambda window: run(CursesViewport(window, plain=plain), plain))


class LineViewport:
    """Scriptable line fallback using the same screens and action forms."""
    plain = True
    form_active = False

    def __init__(self, source, output):
        self.source, self.output = source, output

    def size(self):
        return 100, 32

    def key(self):
        line = self.source.readline()
        if not line:
            raise EOFError
        return line.strip() or 'enter'

    def draw(self, screen, context='', notice=''):
        lines = [screen.title, context, screen.breadcrumb, *screen.lines]
        if screen.split_regions:
            lines.extend(('DECISIONS', *(f'  a{i} {title}' for i, (title, _) in enumerate(screen.decisions, 1))))
            lines.append('EXPLORE')
        lines.extend(f'  {i} {title}' for i, (title, _) in enumerate(screen.entries if screen.show_entries else [], 1))
        lines.extend(screen.details)
        if screen.navigation:
            lines.append(NAVIGATION)
        lines.extend((notice, screen.footer))
        self.output.write('\n'.join(line for line in lines if line) + '\n')
        self.output.flush()
        return screen.scroll

    def message(self, screen):
        self.draw(screen)

    def confirm_discard(self, context):
        self.output.write('DISCARD UNSUBMITTED INPUT? y Discard · Enter Keep editing\n')
        self.output.flush()
        return self.key() == 'y'

    def prompt(self, title, lines, context):
        while True:
            self.draw(Screen(title, lines, navigation=False), context)
            value = self.source.readline()
            if not value:
                raise EOFError
            value = value.rstrip('\r\n')
            if value != '/cancel':
                return value
            if not self.form_active or self.confirm_discard(context):
                return None

    def choose(self, title, items, label, context, *, preview=None):
        while True:
            self.draw(Screen(title, entries=[(label(item), item) for item in items], navigation=False), context)
            key = self.key()
            if key in {'b', 'esc', 'q'}:
                if not self.form_active or self.confirm_discard(context):
                    raise Cancelled
            elif key == 'enter' and items:
                return items[0]
            elif key.isdecimal() and 0 < int(key) <= len(items):
                return items[int(key) - 1]



@contextmanager
def action_form(viewport):
    """Modal forms require explicit discard even between individual fields."""
    previous = getattr(viewport, 'form_active', False)
    viewport.form_active = True
    try:
        yield
    finally:
        viewport.form_active = previous
