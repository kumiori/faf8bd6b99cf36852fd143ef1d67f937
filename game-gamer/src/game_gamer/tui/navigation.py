"""Local route stacks and controls shared by terminal hosts."""
from dataclasses import dataclass, field

from .matrix import MatrixViewport


MODE_KEYS = {'e': 'ecosystem', 'g': 'gathering', 's': 'scenarios'}
NAVIGATION = 'm Paths | e Ecosystem | g Gathering | s Scenarios | c Contracts | i Inbox | p Player'


@dataclass
class Route:
    kind: str
    target: str | None = None
    index: int = 0
    scroll: int = 0
    row: int = 0
    column: int = 0
    query: str = ''
    extra: dict = field(default_factory=dict)
    region: str = 'explore'
    decision_index: int = 0
    reveal: bool = False
    matrix: MatrixViewport = field(default_factory=MatrixViewport)


class NavigationState:
    def __init__(self):
        self.mode = 'ecosystem'
        self.roots = {'ecosystem': Route('matrix'), 'gathering': Route('gathering'),
                      'scenarios': Route('scenarios')}
        self.stacks = {mode: [route] for mode, route in self.roots.items()}

    @property
    def stack(self):
        return self.stacks[self.mode]

    @stack.setter
    def stack(self, routes):
        self.stacks[self.mode] = routes

    @property
    def route(self):
        return self.stack[-1]

    def resume(self, mode, *, reset=False):
        self.mode = mode
        if reset:
            self.stack = [self.roots[mode]]

    def push(self, kind, target=None, **extra):
        self.stack.append(Route(kind, target, extra=extra, region='canvas' if kind == 'network' else 'explore'))

    def back(self):
        if len(self.stack) == 1:
            return False
        self.stack.pop()
        return True
