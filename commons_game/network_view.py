"""Apply host display labels to the reusable terminal network."""
from game_gamer.tui.network import CATEGORIES as CATEGORIES
from game_gamer.tui.network import LAYERS as LAYERS
from game_gamer.tui.network import OBJECT_TYPES as OBJECT_TYPES
from game_gamer.tui.network import PRIORITY as PRIORITY
from game_gamer.tui.network import category_label as category_label
from game_gamer.tui.network import draw_graph as render
from game_gamer.tui.network import edge_category as edge_category
from game_gamer.tui.network import focus_graph as focus
from game_gamer.tui.network import object_type_label as object_type_label

from .presentation import display_label


def focus_graph(*args, **kwargs):
    return focus(*args, **kwargs, labeler=display_label)


def draw_graph(*args, **kwargs):
    return render(*args, **kwargs, labeler=display_label)
