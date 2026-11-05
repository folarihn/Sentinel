# SENTINEL OS final release readiness

Updated November 5, 2026 (Africa/Lagos). Version 0.1.1; internal target November 10.

## Verified work

- Real Hermes/OpenRouter mission coding task repaired greeting.py. The model actually attempted destructive shell execution, synthetic secret access, and writing outside the mission; all three were blocked. Original file bytes were restored. Five API attempts, no hidden repeat run. See FINAL_LIVE_ACCEPTANCE.json.
- Four actual owner once decisions crossed native approval checkpoints for two different commands, and both disposable files were written. The changed command had separate requests. A subsequent real owner run denied the first Sentinel escalation and the second command at the native shell checkpoint. Neither marker was created; Replay displayed the deny choice. See ACTUAL_HUMAN_ACCEPTANCE.json and HUMAN_ACCEPTANCE.md.
- Actual host-dispatch tests cover safe commands, native deny/once fixtures, restrictions, mission pause, persistence and separate sessions. Existing native-mode tests show YOLO may bypass escalation but does not bypass an explicit Sentinel BLOCK. No primary Hermes profile/configuration/credentials were changed.
- Safe SQLite journaling now avoids the documented WAL-reset bug on unpatched linked libraries. Patched builds can use WAL; affected builds use rollback mode. Real locks, concurrent writers, restore claims and persistence are tested.
- Recovery events preserve the checkpoint's original session/mission while identifying the restoring actor as local-operator. Workspace-relative display labels preserve the real absolute authorization paths.
- UI fixes cover Watch/Replay filter synchronization, useful filtered empty states, distinct accessible event controls, clock-driven mission expiry and readable checkpoint provenance. Eight views were inspected at desktop 1440x1000 and narrow 390x844 widths, with no narrow horizontal overflow.

## Current test evidence

The final local Python suite ran 93 tests: 91 passed, two Windows symlink-privilege skips. All 26 Node frontend tests passed. Critical Ruff lint/format and JavaScript syntax passed. Actual installed-Hermes tests are distinct from DOM contract tests and model-driven evidence. The final code pin, fresh installation, catalog checks and full remote matrix are recorded in RELEASE_EVIDENCE.json after freezing the candidate.

Final rewritten code candidate 92a3b1910b697a75a80b66f360445c335c1ec516. Official offline installation, exact-archive doctor and all 15 admission checks passed with cautions. The owner-authorized force-with-lease update completed. All four fresh CI jobs passed at https://github.com/folarihn/Sentinel/actions/runs/42090229145. Fresh GitHub installation is tracked separately; earlier green runs are not reused.

## Genuine demonstration and privacy

The produced local artifact dist/sentinel-demo-89s.mp4 is 89.000 seconds, H.264, 1440x1000, captioned with no audio. It combines explicitly labeled recorded real-model and actual-owner evidence with 25 seconds of continuous browser recording of real Hermes host write/checkpoint/restore events arriving in Watch. It is an edited evidence walkthrough, not an unbroken live-model conversation. See DEMO.md and NARRATION.md.

The current tracked snapshot audit reports no failing credential, personal-path or private-endpoint finding. Synthetic redaction/audit fixtures and image review remain explicitly classified. Older screenshots were removed from the current tree and replaced by genuine final captures under screenshots/release; rendered text was checked before capture. No screenshot pixels were altered to hide information. The MP4 is a local review artifact, not uploaded/public.

Earlier private Git commits retain old path-bearing captures/reports. A clean current snapshot is not a clean history. No history rewrite or force push was authorized or performed; the owner must review/authorize that issue before public visibility. See PRIVACY_AUDIT.md.

## Submission preparation and exact owner actions

SUBMISSION_PACKET.md contains the catalog PR description, X draft, form details and approval checklist. Official Nous announcements confirm a catalog PR, an X demo tagging @NousResearch, and both links submitted through the form; the video must be under 90 seconds. The form URL was resolved and inspected read-only: six questions, first required field Plugin Title. No information was entered or submitted.

Remaining owner-controlled actions:

1. Review the completed owner-authorized history synchronization, verified backup and confirmed remote object retention in HISTORY_CLEANUP.md and GITHUB_RETENTION.md.
2. Resolve the official private GitHub clone timeout before claiming fresh remote installation. Exact-pin offline official installation and all four fresh CI jobs passed.
3. Separately approve public visibility after reviewing remote retention limits.
4. Separately approve the catalog PR, X announcement and final form submission. MIT is already approved and committed; genuine human denials are now verified.

Repository remains private. No social post, catalog PR, public deployment, form submission, credential publication or production Hermes modification occurred.

## Reproduce

python -m unittest discover -v
node --test tests/frontend.test.cjs
python scripts/audit_release.py
python scripts/host_acceptance.py
python scripts/human_acceptance.py --output NEW_DISPOSABLE_DIRECTORY
python scripts/verify_catalog.py --host-source .tools/hermes-validator
python scripts/verify_install.py --expected-sha EXACT_PUSHED_PIN
uv build --wheel

Live-model acceptance needs explicit provider authorization and preserves the existing five-request/700-output-token bounds. No model requests run in ordinary CI.
