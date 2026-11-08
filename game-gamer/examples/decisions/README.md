# Portable decision inspection example

Generated from the installed source with `--interface terminal`. These examples
contain no player-session data and no host-specific screens. Counts are calculated
by extraction and audit; unresolved imperative branches remain explicit. The host's
full reconstruction graph and observed coverage are in `docs/decision-graphs` at
the repository root.

```sh
python -m game_gamer inspect decisions --interface terminal --format json --output decisions.json
python -m game_gamer inspect decisions --interface terminal --format mermaid --output decisions.mmd
python -m game_gamer inspect decisions --interface terminal --format dot --output decisions.dot
python -m game_gamer inspect decisions --interface terminal --audit
```

The executable reconstruction contract requires the Commons host. The portable
terminal remains a source-only discovery view; its observations are not release
verification. Scoped passed-test evidence, the technical gate and four views live
under the repository's `docs/decision-graphs/reconstruction/`.
