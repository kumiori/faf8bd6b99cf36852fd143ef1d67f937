"""Bounded curses viewport and modal controls."""

import os
import textwrap
import unicodedata
from contextlib import contextmanager

from .i18n import t
from .navigation import navigation_bar
from .screen import Cancelled, Screen
from .text import clean, clip, column_slice, display_width, folded
from .visual import ACTION, CONFIRMED, ERROR, NAVIGATION, PRIMARY, SECONDARY, panel_columns, text_span


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
        attribute = self.curses.A_BOLD if bold else 0
        if foreground == SECONDARY and (not self.colour or self.curses.COLORS < 256):
            attribute |= self.curses.A_DIM
        if not self.colour:
            return attribute
        def index(value):
            if value is None:return -1
            rgb=[int(value[i:i+2],16) for i in (1,3,5)]
            if self.curses.COLORS>=256:
                levels=[0,95,135,175,215,255]
                r,g,b=(min(range(6),key=lambda j:abs(levels[j]-v)) for v in rgb)
                return 16+36*r+6*g+b
            return {ACTION: self.curses.COLOR_YELLOW, CONFIRMED: self.curses.COLOR_GREEN,
                    ERROR: self.curses.COLOR_RED, NAVIGATION: self.curses.COLOR_CYAN}.get(
                        value, self.curses.COLOR_WHITE if sum(rgb)>360 else self.curses.COLOR_BLUE)
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

    def draw_panel(self, screen, context, notice):
        from dataclasses import replace
        width, height = self.size()
        self.window.erase()
        base = replace(screen, panel=None)
        panel = replace(screen.panel, panel=None, notice_colour=screen.notice_colour, pulse=screen.pulse,
                        header_indicator=screen.header_indicator,
                        header_colour=screen.header_colour,
                        region='explore' if screen.panel_focused else 'details',
                        reveal=screen.panel_focused and screen.panel.reveal)
        if width < 90:
            chosen = panel if screen.panel_focused else base
            chosen.footer += t('viewport.tab_main_context')
            result = self.draw(chosen, context, notice)
            return {'panel' if screen.panel_focused else 'main': result}

        right_width = min(52, max(32, width//3))
        left_width = width-right_width-1

        def child(window):
            view = object.__new__(type(self))
            view.__dict__.update(self.__dict__)
            view.window = window
            return view

        left = child(self.window.derwin(height, left_width, 0, 0))
        right = child(self.window.derwin(height, right_width, 0, left_width+1))
        main_scroll = left.draw(base, context, '' if screen.panel_focused else notice)
        result = right.draw(panel, t('viewport.tab_main_view') if screen.panel_focused else t('viewport.tab_context_panel'),
                            notice if screen.panel_focused else '')
        for row in range(height):
            try:
                self.window.addnstr(row, left_width, '|', 1, self.colour_style(SECONDARY))
            except self.curses.error:
                pass
        self.window.refresh()
        self.last_screen = screen
        return {'main': main_scroll, 'panel': result}

    def draw(self, screen, context='', notice=''):
        if screen.panel is not None:
            return self.draw_panel(screen, context, notice)
        self.last_screen = screen
        width, height = self.size(); self.window.erase()
        header = screen.masthead or screen.title
        title_width = width-1
        if screen.header_indicator:
            text = clip(self.safe(screen.header_indicator), max(0, width//2))
            column = max(0, width-display_width(text)-2)
            title_width = max(0, column-2)
            try:
                self.window.addnstr(0, column, text, len(text),
                                   self.colour_style(screen.header_colour, bold=True))
            except self.curses.error:
                pass
        self.put(0, clip(self.safe(header), title_width), self.colour_style(PRIMARY, bold=True))
        if height >= 4:
            self.put(1, context, self.colour_style(SECONDARY))
        if screen.masthead and height >= 6:
            self.put(2, screen.title, self.colour_style(NAVIGATION, bold=True))
        elif screen.navigation:
            bar = navigation_bar() if screen.navigation_text is None else screen.navigation_text
            self.put(2, bar, self.colour_style(SECONDARY))
        if screen.breadcrumb and not screen.masthead:
            self.put(3, screen.breadcrumb, self.colour_style(SECONDARY))
        if screen.pulse and height >= 9:
            count, colour = screen.pulse
            row = 3 if screen.masthead else height-3
            self.put(row, ('▰' if not self.plain else '=')*count,
                     self.colour_style(colour, bold=True))
        body_start = 4 if screen.breadcrumb or screen.masthead else 3
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
            add_line(t('viewport.decisions') + ('  <' if screen.region == 'decisions' else ''), self.colour_style(ACTION, bold=True))
            if not screen.decisions:
                add_line(t('viewport.no_decision_available_for_this'))
            for i, (label, _) in enumerate(screen.decisions):
                decision_starts.append(len(content))
                selected = screen.region == 'decisions' and i == screen.decision_index
                add_line(('> ' if selected else '  ')+label, self.colour_style(ACTION, bold=selected), indent='  ')
            add_line(t('viewport.explore') + ('  <' if screen.region == 'explore' else ''), self.colour_style(NAVIGATION, bold=True))
        entry_starts = []
        inline_hint = height >= 18 and bool(screen.hint)
        for i, (label, _) in enumerate(screen.entries if screen.show_entries else []):
            if i in screen.entry_sections:
                if i:
                    add_line('')
                add_line(screen.entry_sections[i], self.colour_style(SECONDARY, bold=True))
            entry_starts.append(len(content))
            active = screen.region == 'explore' and i == screen.selected
            prefix = '> ' if active else '  '
            text=prefix+f'[{i+1}] '+label
            parts=textwrap.wrap(self.safe(text),max(1,width-1),subsequent_indent='      ') if screen.wrap_entries else [text]
            content.extend((part,self.colour_style(NAVIGATION, bold=True) if active else 0) for part in parts)
            if active and inline_hint:
                add_line('      '+screen.hint, self.colour_style(SECONDARY), indent='      ')
        detail_start = len(content)
        if screen.details and screen.region == 'details':
            add_line(t('viewport.details') + ('  <' if screen.region == 'details' else ''), self.colour_style(SECONDARY, bold=True))
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
        if len(content) > body_height and height >= 8:
            self.put(height-3, t('viewport.scroll_pgup_pgdn', scroll=scroll + 1, value=max(1, len(content) - body_height + 1)),
                     self.colour_style(SECONDARY))
        if notice and height >= 3:
            self.put(height-2, notice, self.colour_style(screen.notice_colour, bold=True))
        elif screen.hint and not inline_hint and height >= 3:
            self.put(height-2, screen.hint, self.colour_style(SECONDARY))
        footer = (t('viewport.esc_b_back_help') if screen.navigation else '')+(screen.footer or t('viewport.enter_continue'))
        self.put(height-1, footer, self.colour_style(NAVIGATION))
        self.window.refresh()
        return scroll

    def message(self, screen):
        self.draw(screen)

    def poll_key(self, timeout_ms):
        self.window.timeout(timeout_ms)
        try:
            return self.key()
        except self.curses.error:
            return None
        finally:
            self.window.timeout(-1)

    def key(self):
        pending = getattr(self, '_pending_key', None)
        if pending is not None:
            self._pending_key = None
            return pending
        key = self.window.get_wch()
        mapping = {self.curses.KEY_UP: 'up', self.curses.KEY_DOWN: 'down', self.curses.KEY_LEFT: 'left',
                   self.curses.KEY_RIGHT: 'right', self.curses.KEY_NPAGE: 'pagedown', self.curses.KEY_PPAGE: 'pageup',
                   self.curses.KEY_RESIZE: 'resize', self.curses.KEY_HOME: 'home', self.curses.KEY_ENTER: 'enter', '\n': 'enter', '\r': 'enter', '\x1b': 'esc'}
        mapping.update({self.curses.KEY_BTAB:'backtab','\t':'tab'})
        if key in {'\x03', '\x04'}:
            raise EOFError
        return mapping.get(key, key)

    def navigation_key(self, timeout_ms=None):
        key = self.poll_key(timeout_ms) if timeout_ms else self.key()
        if key not in {'up', 'down', 'left', 'right', 'pageup', 'pagedown'}:
            return key
        # Coalesce a queued burst of the same direction. Preserve the following command.
        self.window.timeout(0)
        try:
            for _ in range(64):
                try:
                    following = self.key()
                except self.curses.error:
                    break
                if following != key:
                    self._pending_key = following
                    break
        finally:
            self.window.timeout(-1)
        return key

    def confirm(self, title, lines, context):
        index = 0
        while True:
            self.draw(Screen(title, list(lines), [(t('viewport.confirm'), True), (t('controls.cancel_button'), False)],
                             t('viewport.enter_choose_y_confirm_n'), selected=index, navigation=False), context)
            key = self.key()
            if key in {'up', 'down', 'left', 'right', 'tab'}:
                index = 1-index
            elif key in {'n', 'esc', 'b'}:
                return False
            elif key == 'enter' or key == 'y':
                # Scripts and terminals may send y followed by Enter in one input burst.
                self.window.timeout(0)
                try:
                    following = self.key()
                    if following not in {'enter', 'y'}:
                        self._pending_key = following
                except self.curses.error:
                    pass
                finally:
                    self.window.timeout(-1)
                return key == 'y' or index == 0
            # Other keys leave the selected option and dialog intact.

    def prompt(self, title, lines, context):
        value = ''
        while True:
            width, height = self.size()
            screen = Screen(title, list(lines)+['', '> '+value[-max(1,width-4):]], footer=t('viewport.enter_confirm_esc_cancel'), navigation=False)
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
            self.draw(Screen(t('viewport.discard_unsubmitted_input'), [t('viewport.y_discard_n_keep_editing')],
                             footer=t('viewport.esc_return_to_form'), navigation=False), context)
            key = self.key()
            if key in {'y', 'n', 'esc', 'b'}:
                return key == 'y'

    def choose(self, title, items, label, context, *, preview=None, section=None, header_indicator='', masthead='', menu=None, directory=False):
        index = 0; query = ''; scroll = 0; region = 'explore'
        while True:
            filtered = [item for item in items if folded(query) in folded(label(item))]
            index = min(index, max(0, len(filtered)-1))
            lines = [t('controls.search_prefix')+query, t('controls.choice_count', count=len(filtered))]
            hint = ''
            if menu and region == 'explore' and filtered:
                lines = [t('controls.search_prefix')+query] if query else []
                hint = menu[filtered[index]][1]
            if region == 'details':
                lines += [t('viewport.up_down_selects_an_option'),
                          t('controls.search_instructions'), t('viewport.esc_b_goes_back')]
                if filtered:
                    lines += [t('controls.selected_prefix')+label(filtered[index])]
            sections = {}
            previous = None
            if section:
                for i, item in enumerate(filtered):
                    current = section(item)
                    if current != previous:
                        sections[i] = current
                    previous = current
            entries = [(menu[item][0] if menu else label(item), item) for item in filtered]
            if directory:
                width, height = self.size()
                rows = max(1, height-10)
                columns = min(4, max(1, (width-1)//25))
                page_size = rows*columns
            if directory and region == 'explore':
                page, total = index//page_size, max(1, (len(entries)+page_size-1)//page_size)
                start = page*page_size
                cell_width = max(1, (width-1-2*(columns-1))//columns)
                panels = []
                for offset in range(start, min(start+page_size, len(entries)), rows):
                    names = [('> ' if number == index else '  ')+name
                             for number, (name, _) in enumerate(entries[offset:min(offset+rows, start+page_size)], offset)]
                    styles = [text_span(index-offset, 0, names[index-offset], NAVIGATION, bold=True)] if offset <= index < offset+len(names) else []
                    panels.append((cell_width, names, styles))
                body, styles = panel_columns(panels, row_offset=len(lines), gutter=2)
                footer = t('viewport.directory_keys')
                if preview:
                    footer += t('viewport.v_preview')
                if total > 1:
                    footer = t('viewport.directory_pages', current=page+1, total=total)+'  '+footer
                self.draw(Screen(title, lines+body, footer=footer, navigation=False,
                                 fixed_rows=set(range(len(lines+body))), styles=styles,
                                 header_indicator=header_indicator, masthead=masthead), context)
            else:
                self.draw(Screen(title, lines, entries,
                    t('viewport.enter_confirm_tab_regions_search')+(t('viewport.v_preview') if preview else '')+t('viewport.esc_b_back'),
                    index, scroll if region == 'explore' else 0, navigation=False,
                    show_entries=region == 'explore', reveal=region == 'explore', entry_sections=sections,
                    header_indicator=header_indicator, masthead=masthead, hint=hint), context)
            key = self.key()
            if key in {'b', 'q', 'esc'}:
                if not self.form_active or self.confirm_discard(context):
                    raise Cancelled
                continue
            if key in {'tab', 'backtab', '?'}:
                region = 'details' if region == 'explore' else 'explore'
                continue
            if key == '/':
                value = self.prompt(t('viewport.directory_search' if directory else 'viewport.search_by_name_or_organisation'), [], context)
                if value is not None:
                    query = value; index = scroll = 0
                    region = 'explore'
            elif key in {'up', 'down'}:
                index = max(0, min(len(filtered)-1, index+(-1 if key == 'up' else 1)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif directory and key in {'left', 'right'}:
                index = max(0, min(len(filtered)-1, index+(-rows if key == 'left' else rows)))
            elif key in {'pageup', 'pagedown'}:
                step = page_size if directory else max(1, self.size()[1]-10)
                index = max(0, min(len(filtered)-1, index+(-step if key == 'pageup' else step)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif key == 'enter' and filtered:
                return filtered[index]
            elif key == 'v' and preview and filtered:
                details = preview(filtered[index]); offset = 0
                while True:
                    shown = self.draw(Screen(t('viewport.profile_preview'),details,footer=t('viewport.pgup_pgdn_scroll_enter_or'),
                                             scroll=offset,navigation=False,header_indicator=header_indicator),context)
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
        if screen.panel is not None:
            from dataclasses import replace
            self.draw(replace(screen, panel=None), context)
            return self.draw(screen.panel, t('viewport.context_panel'), notice)
        lines = [screen.masthead, screen.title, screen.header_indicator, context, screen.breadcrumb, *screen.lines]
        if screen.split_regions:
            lines.extend((t('viewport.decisions'), *(f'  a{i} {title}' for i, (title, _) in enumerate(screen.decisions, 1))))
            lines.append(t('viewport.explore'))
        lines.extend(f'  {i} {title}' for i, (title, _) in enumerate(screen.entries if screen.show_entries else [], 1))
        if screen.region == 'details':
            lines.extend(screen.details)
        if screen.navigation:
            lines.append(navigation_bar() if screen.navigation_text is None else screen.navigation_text)
        lines.extend((notice, screen.footer))
        self.output.write('\n'.join(line for line in lines if line) + '\n')
        self.output.flush()
        return screen.scroll

    def message(self, screen):
        self.draw(screen)

    def confirm_discard(self, context):
        self.output.write(t('viewport.discard_unsubmitted_input_y_discard'))
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

    def choose(self, title, items, label, context, *, preview=None, section=None, header_indicator='', masthead='', menu=None, directory=False):
        while True:
            self.draw(Screen(title, entries=[(label(item), item) for item in items], navigation=False, header_indicator=header_indicator, masthead=masthead), context)
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
