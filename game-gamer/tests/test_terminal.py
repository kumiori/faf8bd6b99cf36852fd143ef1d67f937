"""Geometry and a complete independent line-terminal playthrough."""
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace

from game_gamer import Collective, SimulationBinding
from game_gamer.tui import TerminalGame
from game_gamer.tui.matrix import AxisLabel, Detail, MatrixCell, MatrixView, MatrixViewport, format_cell, render_matrix
from game_gamer.tui.network import draw_graph, focus_graph, layout_graph
from game_gamer.tui.text import display_width
from game_gamer.tui.viewport import CursesViewport, LineViewport

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'minimal_collective' / 'world.json'


def test_geometry_preserves_direction_and_display_columns():
    assert display_width('\x1b[32mÉe\u0301東京\x1b[0m') == 6
    assert format_cell(MatrixCell('a', 'b', 120), numeric=True, selected=True) == '>+'
    assert format_cell(MatrixCell('a', 'b', 42), 3, numeric=True, selected=True) == '>42'
    assert display_width(format_cell(MatrixCell('a', 'b', None), width=2)) == 2
    axis = [AxisLabel(str(i), f'Ée\u0301 東京 very long actor name {i}') for i in range(120)]
    values = [[i * 10 + j for j in range(120)] for i in range(120)]
    matrix = MatrixView(axis, axis, values, exclude_self=True)
    original = deepcopy(values)
    selected = (102, 113)
    cell = matrix.cell(*selected)
    assert cell.value == 1133 and matrix.cell(*reversed(selected)).value == 1232
    viewport = MatrixViewport()
    for detail, width, height in ((Detail.COMPACT, 100, 16), (Detail.STANDARD, 31, 3),
                                  (Detail.DETAILED, 160, 40), (Detail.COMPACT, 14, 1)):
        viewport.detail = detail
        result = render_matrix(matrix, viewport, row=selected[0], column=selected[1], width=width, height=height,
                               numeric=True)
        if detail != Detail.DETAILED:
            assert result.cell_width == (2 if detail == Detail.COMPACT else 3)
        assert selected[0] in result.rows and selected[1] in result.columns
        assert len({display_width(line) for line in result.lines}) == 1
        assert all(display_width(line) <= width for line in result.lines)
        assert values == original and matrix.cell(*selected) == cell
    assert viewport.handle('f')
    fitted = render_matrix(matrix, viewport, row=102, column=113, width=100, height=8)
    assert 102 in fitted.rows and 113 in fitted.columns
    assert viewport.handle('+') and viewport.detail == Detail.STANDARD
    assert viewport.handle('+') and viewport.detail == Detail.DETAILED
    assert viewport.handle('-') and viewport.detail == Detail.STANDARD
    assert render_matrix(MatrixView([], [], []), viewport, row=0, column=0, width=10, height=3).lines == []


def test_graph_layout_and_dense_context_are_deterministic():
    graph = {'nodes': [{'id': str(i), 'kind': 'person', 'label': 'Éloïse ' + str(i)} for i in range(260)],
             'edges': [{'source_id': '0', 'target_id': '1', 'kind': 'knows', 'layer': 'declared', 'directed': True}]}
    original = deepcopy(graph)
    for three_d in (False, True):
        visual = focus_graph(graph, '0', three_d=three_d)
        layout = layout_graph(visual, 52, 17, yaw=.4, pitch=.2)
        assert layout.points.keys() == {'0', '1'}
        for x, y, _ in layout.points.values():
            assert 0 <= x < layout.width and 0 <= y < layout.height
            assert layout.hit_test(round(y), round(x)) in {'0', '1'}
        hidden, hidden_styles = draw_graph(visual, 16, 7, background='hidden')
        dim, dim_styles = draw_graph(visual, 16, 7)
        full, full_styles = draw_graph(visual, 16, 7, background='full')
        assert dim != hidden and dim == draw_graph(visual, 16, 7)[0]
        assert len(dim_styles) <= len(hidden_styles) + 16 * 7
        assert any(style[3] == '#465060' for style in dim_styles)
        assert not any(style[3] == '#465060' for style in full_styles)
        assert all(display_width(line) == 16 for line in full)
    assert graph == original


def test_curses_draft_guard_keeps_buffer_on_cancel_and_resize():
    viewport = object.__new__(CursesViewport)
    viewport.curses = SimpleNamespace(KEY_BACKSPACE=0)
    keys = iter(['é', 'resize', 'esc', 'n', 'b', 'enter'])
    screens = []
    viewport.key = lambda: next(keys)
    viewport.size = lambda: (40, 16)
    viewport.draw = lambda screen, _: screens.append(screen)
    assert viewport.prompt('Draft', [], 'Context') == 'éb'
    assert any(screen.title == 'DISCARD UNSUBMITTED INPUT?' for screen in screens)


def test_independent_terminal_negotiates_verifies_and_resumes(tmp_path):
    definition = json.loads(EXAMPLE.read_text())
    game = Collective.start(definition, path=tmp_path / 'world.sqlite')
    commands = [
        'x', '1', 'b', '2', 'b', '3', 'b', 'b',  # inspect all three actors
        'w', 'b', 'down', '+', '+', 'enter',     # network and directional matrix
        'j', 'Rehearse together?', '1', '1',    # contact as Jo
        'b', 'p', '1', 'i', '1', 'y', '', '1', # accept contact as Sam
        'g', 'j', '1', '1', '1',               # invite Jo to attend
        'p', '2', 'i', '1', 'y', '1',          # attendance as Jo
        'p', '1', 's', 'k', '1', '1', '1', '1',
        'Rehearsal plan', '', '', '', '', '1', '1', '', '', '', '1',
        'j', 'Revised rehearsal', '', '', '', '1',
        'y', '1', 'p', '2', 'y', '1',          # independently accept terms v2
        'p', '3', 'a1', '1',                   # Pat approves
        'p', '1', 'a1', '1',                   # Sam activates
        'a1', 'Sam started', '1', 'a1', '1', 'Sam completed', '1',
        'p', '2', 'a1', 'Jo started', '1', 'a1', '1', 'Jo completed', '1',
        'p', '3', 'a1', 'Independent review', '1', 'h', 'q',
    ]
    output = StringIO()
    binding = SimulationBinding(scope_id=game.scope_id, actor_id='jo')
    ui = TerminalGame(collective=game, binding=binding, hot_seat=True,
                      viewport=LineViewport(StringIO('\n'.join(commands) + '\n'), output))
    ui.run()
    transcript = output.getvalue()
    assert 'ECOSYSTEM / NETWORK' in transcript and 'Jo offers → Sam requests' in transcript
    assert 'INBOX' in transcript and 'HISTORY' in transcript
    events = game.project('log')
    assert [e['command']['kind'] for e in events[1:]] == [
        'send_contact', 'respond_contact', 'invite', 'respond_invitation', 'propose', 'amend',
        'accept', 'accept', 'authorize', 'activate', 'initiate', 'fulfill', 'initiate', 'fulfill', 'verify',
    ], transcript[-7000:]
    contract = game.project('agreements')[0]
    assert contract['current_version'] == 2
    assert set(contract['versions'][1]['acceptances']) == {'sam', 'jo'}
    assert contract['outcome_status'] == 'verified'
    restored = Collective.open(tmp_path / 'world.sqlite', scope_id=game.scope_id)
    assert restored.project() == game.project()
    assert restored.project('objectives')[0]['status'] == 'verified'
    assert game.inbox(binding=binding) == []
