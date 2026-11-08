# Curator access in the local simulation

On 8 November 2026, curator access was assigned to **A**, the participant shown
as playing in the supplied screenshot. The assignment is recorded as
`curator.access_granted` at world revision 18. A backup was taken before the
assignment in the private save directory's `backups` folder.

Restart the terminal application and choose A.

```sh
.venv/bin/python -m commons_game play
```

The player list marks A with **CURATOR**. Once A is playing, the yellow
**◆ CURATOR** badge appears at the top right of ordinary screens and picker
dialogs. Press **u** from gameplay to open the curator menu. Inside a picker,
Enter confirms a choice and Escape returns to gameplay.

The menu provides profile corrections, provenance, visibility controls, merge
preview and merge reversal. Permissions continue to be checked by the engine.

The trusted local operator can explicitly grant or revoke the simulated role.

```sh
.venv/bin/python -m commons_game curator-access grant A --reference "Local operator assignment"
.venv/bin/python -m commons_game curator-access revoke A --reference "Local operator revocation"
```

Use `--db PATH` before `curator-access` to target another saved world. Actor
selection accepts an exact ID, exact full label or unique displayed name.
Unknown or ambiguous names are rejected. An identical role setup is idempotent.
The operator command is separate from the player command registry.

Role changes append an audited event and preserve the source profile provenance.
Later ecosystem metadata refreshes preserve locally assigned roles. Existing
replay and restart recover the assignment from the same authoritative history.
