"""Apply host display labels to the reusable terminal network."""
from game_gamer.tui.network import CATEGORIES as CATEGORIES
from game_gamer.tui.network import LAYERS as LAYERS, PRIORITY as PRIORITY, edge_category as edge_category
from game_gamer.tui.network import draw_graph as render, focus_graph as focus

from .presentation import display_label


def focus_graph(*args, **kwargs):
    return focus(*args, **kwargs, labeler=display_label)


def draw_graph(*args, **kwargs):
    return render(*args, **kwargs, labeler=display_label)
