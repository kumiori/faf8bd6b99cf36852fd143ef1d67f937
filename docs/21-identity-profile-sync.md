# Identity review and profile synchronisation

In Montréal Network, a curator opens source review with **U**. Select a source
identity to inspect its observations and choose **MATCH**, **CREATE**, **DEFER**
or **REJECT**. **MATCH** searches people in the imported Notion roster and
shows their canonical Notion record identifiers. Names, known aliases and
organisation are suggestions for the reviewer. Refresh the roster from the
authorised Notion capture before reviewing against a changed People database.

A match or provisional profile gives topology a stable actor ID. Deferred
identities remain visible as source observations. Rejected observations remain
in source history and are omitted from topology. Historical name-only
suggestions go back to the review queue. The import stores source rows and
decisions separately within its event history.

Press **E** on a profile to propose an edit. Open the curation queue with **u**
to review the previous and proposed values. Approval applies a local profile
edit immediately or queues a Notion-backed profile edit for synchronisation.
Profile topics are curated display fields. Recorded questionnaire answers,
player-authored declarations and the matching matrix keep their original
inputs.

## Run the Notion bridge

Use a connection authorised for the canonical profile data source. Configure
its token via `COMMONS_NOTION_WRITE_TOKEN` and fill in
[the example mapping](../config/notion-profile-write.example.json). Map the
curated properties only. Provisioning requires a dedicated rich-text
`Commons Actor ID` property, which lets the synchroniser find the same page
after an interrupted request.

```sh
python -m commons_game --db /path/to/world.sqlite sync-profile
python -m commons_game --db /path/to/world.sqlite sync-profile JOB_ID --mapping /path/to/profile-mapping.json
```

Synchronisation checks the configured data source and mapped property types.
An edit compares the current Notion values with the recorded previous values
before writing. If the previous value is unavailable locally, the remote field
must be empty or already match the approved value. This comparison detects
divergence at read time. Coordinate edits to the same Notion fields while
applying a job, since the [Notion page update endpoint](https://developers.notion.com/reference/patch-page)
has no compare-and-swap condition.

If a response is lost, rerun the same job. Updates already visible in Notion
are acknowledged without sending the patch again. Creation is reserved before
posting and recovered by its actor marker. If creation remains unconfirmed
and no marker is found, a curator must investigate the Notion data source
before resolving the job. Sync outcomes and approval provenance are part of
the game event history.

## Verify a provisional profile

After matching the intended recipient to a verified provider subject outside
the game, a trusted operator can issue a one-time invitation.

```sh
python -m commons_game --db /path/to/world.sqlite profile-claim issue \
  --actor ACTOR_ID --curator CURATOR_ID --provider PROVIDER --subject OPAQUE_SUBJECT \
  --reference VERIFICATION_REFERENCE
python -m commons_game --db /path/to/world.sqlite profile-claim verify \
  --curator CURATOR_ID --provider PROVIDER --subject OPAQUE_SUBJECT \
  --reference VERIFICATION_REFERENCE
```

Deliver the token privately through the verified channel. Verification prompts
for the token, requires the bound subject and an operator attestation, and
activates the synced provisional profile. The invitation expires after seven
days. The event log contains its digest and the verification receipt. The
terminal continues to use its existing simulated sessions.
