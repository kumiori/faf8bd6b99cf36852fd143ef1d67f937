"""Optional terminal hosts and reusable widgets."""

__all__ = ['TerminalGame']


def __getattr__(name):
    if name == 'TerminalGame':
        from .application import TerminalGame
        return TerminalGame
    raise AttributeError(name)
