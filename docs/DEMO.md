# Reproducible demonstration under 90 seconds

## Produced media

`dist/sentinel-demo-89s.mp4` is a verified 89.000-second, 1440×1000 H.264
captioned evidence walkthrough. It has no voiceover/audio track; use
`NARRATION.md` for an owner-recorded narration if desired. No media was uploaded.
The source manifest is `dist/sentinel-demo-89s.json`.

The walkthrough uses genuine final Control Room captures, explicitly labels
recorded model and owner-approval evidence, and includes 25 seconds of continuous
browser-frame recording while actual Hermes host write/checkpoint/restore events
arrive in Watch. It is an edited walkthrough, not one unbroken live-model video.
No action or metric was fabricated or reconstructed. Screenshot sources are in
`docs/screenshots/release/`; recording frames remain local under ignored `.tools/`.

Re-render locally with `python scripts/render_demo.py` while those genuine local
frames are retained. To reproduce the live host segment, run
`scripts/demo_operator.py` against a new disposable acceptance workspace with the
Control Room recording its real events. Do not re-run it against an existing
marker or production workspace. The script performs no model/provider request.

Final model evidence (`FINAL_LIVE_ACCEPTANCE.json`) records the coding repair,
three actual restricted attempts blocked, and restoration. Actual owner evidence
(`ACTUAL_HUMAN_ACCEPTANCE.json`) records four **once** decisions and two completed
tool effects. There was no owner denial; do not voice a rejection claim. Earlier
fixture decisions below remain separately identified.

Use disposable workspaces and synthetic files. Hide the dashboard token, credentials, raw logs and personal paths before recording. Do not make another model request merely to refresh footage: further provider runs require authorization.

## Prepare distinct evidence sources

**Recorded real model session:** the approved `openrouter/free` acceptance completed two API requests. Hermes executed the model's terminal and `write_file` actions; Sentinel recorded ten events and automatically sealed one checkpoint. Authorized restore returned the new file to absence. See [LIVE_ACCEPTANCE.json](LIVE_ACCEPTANCE.json). Caption its forensic playback **Recorded real model session**. It was an isolated profile, not the owner's primary agent.

**Actual host dispatch with fixture decisions:** `python scripts/host_acceptance.py` creates a credential-free profile and runs real Hermes tools. It verifies destructive/secret blocks, native fixture deny/once decisions, mission pause, two-session separation, persistence and recovery. See [HOST_ACCEPTANCE.json](HOST_ACCEPTANCE.json). Caption it **Hermes host acceptance · fixture human decisions**. A fixture callback is not a person clicking approval.

The command prints a new evidence directory. Open that journal from the reviewed checkout:

```powershell
$evidence = Read-Host 'Paste the returned disposable evidence directory'
python -m sentinel.server --data "$evidence/state" --workspace "$evidence/workspace" --port 8765
```

Open `http://127.0.0.1:8765`, enter the token locally and keep it outside the recording. Retained live evidence has the same `state` and `workspace` subdirectories. The server displays journals; Hermes must load the plugin to enforce policy. Historical events must not be described as currently arriving live.

`scripts/demo.py` is a weaker, direct-runtime fixture generator. Caption it **Synthetic fixture · direct Sentinel callbacks** if used. It cannot substantiate Hermes tool execution or live-model claims.

## Recording script

- **0–10 seconds:** show SENTINEL OS and Control Room. Say: “A local policy and evidence layer for Hermes tools.” Show the data-source caption and recorded session identifier.
- **10–29 seconds:** open the recorded real-model session in Replay. Inspect actual terminal/file-write events, identities and policy decisions. Say: “This model-generated action passed through Hermes and Sentinel's pre-execution policy.”
- **29–43 seconds:** switch to the separately captioned actual-host journal. Inspect the destructive block and matching rule; show the preserved disposable marker. Explain that the fixture calls the real Hermes dispatcher.
- **43–57 seconds:** inspect native approval request and fixture deny/once records. Say: “Native Hermes approval controls execution. These are explicit test decisions; manual human interaction is a separate release check.” Do not invent dashboard approval controls.
- **57–74 seconds:** show the real-model file-write checkpoint and recorded restoration. Inspect the restored status and original-absence outcome. Say: “Recovery covers supported local files, with conflict detection; it cannot undo external actions.”
- **74–85 seconds:** show scoped mission authority and two-session host evidence, then the concrete pinned install command from the release record. Close with “Autonomy with accountability.” Leave five seconds of margin.

Use genuine interface footage and artifacts. Edit for pace, legibility and privacy only. No fabricated events, altered decisions, fake live indicators or restaged human approvals.

## Recording gates

- Freeze and verify the release pin before filming the closing install command.
- Match footage to its actual journal. Newly rerun fixtures may have different IDs/counts; disclose their actual values.
- Show manual CLI/gateway approval only after actually recording it in an isolated profile. Fixture evidence remains labelled until then.
- Review duration below 90 seconds and accidental token, credential or personal-path disclosure.
- Obtain owner approval for public visibility, social posting, catalog PR and final submission. None has been performed by this document.
