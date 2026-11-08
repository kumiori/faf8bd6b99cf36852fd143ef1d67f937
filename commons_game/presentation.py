"""Shared, read-only presentation vocabulary; independent of any terminal toolkit."""
from dataclasses import asdict
import os
import shutil
import textwrap
import unicodedata

from game_gamer.tui.objects import OBJECTS as OBJECTS, ObjectStyle as ObjectStyle


STATUS_LABELS = {'authorized': 'AUTHORISED', 'unverified': 'UNVERIFIED'}


def status(value):
    return STATUS_LABELS.get(value, str(value).replace('_', ' ').upper())


def dictionary():
    """Serializable vocabulary for future graphical clients; never mutates world."""
    return {kind: asdict(style) for kind, style in OBJECTS.items()}


def clean(value):
    return ''.join(c for c in str(value) if c.isprintable() or c in '\n\t')


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).casefold()) if not unicodedata.combining(c))


def display_label(record):
    """First names for people, without changing source records or identity keys.

    The imported catalogue has unstructured names: retain the first token,
    including accents and hyphens. A middle-dot suffix is descriptive context.
    Organisation and other object labels remain complete.
    """
    if record.get('kind')=='person' and 'display_name' in record:
        return record['display_name']
    label = str(record.get('label', record.get('domain', 'Recorded evidence')))
    if record.get('kind') != 'person':
        return label
    if record.get('provenance',{}).get('kind') == 'fictional_fixture' and label.endswith('(synthetic)'):
        return label  # Explicit support roles describe a function, not a person's name.
    name, separator, context = label.partition(' · ')
    tokens = name.split()
    first = tokens[0] if tokens else ''
    return first + separator + context


def person_labels(world):
    """First names plus collision ordinals, in authoritative creation order.

    The mapping is presentation only. Inactive actors retain their slot; replay
    preserves insertion order and later imports never reassign existing slots.
    A historical prefix derives its own clearly historical display mapping.
    """
    groups = {}
    labels = {}
    from game_gamer.runtime.curation import profile
    for original in world['actors'].values():
        actor = profile(world, original['id'])
        if actor['kind']!='person': continue
        label=display_label({k:v for k,v in actor.items() if k!='display_name'})
        labels[actor['id']]=label
        groups.setdefault(folded(label.partition(' · ')[0]),[]).append(actor['id'])
    for ids in groups.values():
        if len(ids)>1:
            for ordinal,key in enumerate(ids,1):
                name,separator,context=labels[key].partition(' · ')
                labels[key]=name+f' ({ordinal})'+separator+context
    return labels


def actor_label(world, actor_id):
    actor=world['actors'][actor_id]
    return person_labels(world).get(actor_id,display_label(actor))


def display_world(world):
    """A disposable view for the laboratory's technical world inspector."""
    return {**world, 'actors': {key: {**actor, 'label': actor_label(world,key),
                                    **({'display_name':actor_label(world,key)} if actor['kind']=='person' else {})}
                               for key, actor in world['actors'].items()}}


class Presentation:
    def __init__(self, output, *, plain=False, colour=None, width=None):
        self.output = output
        encoding = getattr(output, 'encoding', None) or 'utf-8'
        self.encoding = encoding
        try:
            '●◆⬡'.encode(encoding)
        except (UnicodeError, LookupError):
            plain = True
        self.plain = plain or os.getenv('TERM') == 'dumb'
        self.colour = (getattr(output, 'isatty', lambda: False)() if colour is None else colour)
        self.colour = self.colour and not self.plain and 'NO_COLOR' not in os.environ
        self.width = width or min(100, max(24, shutil.get_terminal_size().columns))

    def paint(self, text, colour):
        if not self.colour:
            return text
        rgb = tuple(int(colour[i:i+2],16) for i in (1,3,5))
        return '\x1b[38;2;%s;%s;%sm%s\x1b[0m' % (*rgb, text)

    def write(self, value=''):
        value = clean(value)
        if self.plain:
            value = value.replace('↑↓','Up/Down')
            value = value.translate(str.maketrans({'→':'->', '←':'<-', '↑':'up', '↓':'down', '—':'-', '·':'/', '≠':'!=', '✓':'OK'}))
        value = self.safe_encoding(value)
        for line in value.split('\n'):
            lines = textwrap.wrap(line, width=self.width, replace_whitespace=False, break_long_words=True) or ['']
            for part in lines:
                self.output.write(part + '\n')
        self.output.flush()

    def heading(self, title, context=''):
        self.write('\n' + ('=' if self.plain else '─') * self.width)
        self.write(title.upper())
        if context:
            self.write(context)
        self.write(('-' if self.plain else '─') * self.width)

    def node(self, node, *, prefix='', alias=None):
        style = OBJECTS.get(node['kind'], OBJECTS['evidence'])
        symbol = style.plain if self.plain else style.symbol
        suffix = ('  ' + status(node['status'])) if node['kind'] == 'agreement' else ''
        label = clean(display_label(node))
        reference = (alias + '  ') if alias else ''
        line = f'{prefix}{symbol} {reference}{label}{suffix}'
        if self.plain:line=line.replace(' · ',' / ')
        line=self.safe_encoding(line)
        # Wrap before colouring so escape sequences never count as layout width.
        for part in textwrap.wrap(line, self.width) or ['']:
            self.output.write(self.paint(part, style.colour) + '\n')
        if node['kind'] == 'agreement':
            self.write('      Outcome: ' + status(node.get('outcome_status', 'unverified')))
        self.output.flush()

    def safe_encoding(self,value):
        try:
            value.encode(self.encoding)
            return value
        except (UnicodeError,LookupError):
            return unicodedata.normalize('NFKD',value).encode('ascii','replace').decode('ascii')
