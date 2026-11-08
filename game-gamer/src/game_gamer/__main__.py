"""Support ``python -m game_gamer`` independently of the host application."""
from .cli import main

raise SystemExit(main())
