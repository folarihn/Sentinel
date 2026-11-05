# SENTINEL OS build status

Updated November 5, 2026 (Africa/Lagos). Candidate version 0.1.1.

## Current milestone

**Phase:** Phase 5 acceptance and release hardening. Candidate implemented and tested; final submission gates remain open.

**Implemented:** Security regressions fixed, real model and host execution harnesses, transactional restore claims, API validation and lock recovery, persistent restart tests, bounded frontend memory and journal search, accessible dialogs, reliable stale-data/reconnect behavior, official catalog validation, and release preparation.

**Files changed:** `sentinel/`, Python and Node tests, verification scripts, workflow matrix, release documentation, sanitized evidence and genuine screenshots. No primary Hermes files were modified.

**Tests executed:** Installed Hermes Python full suite, Node DOM contract suite, real HTTP sockets, actual host tool bodies, bounded approved live model run, browser interactions at desktop/narrow viewports, Ruff critical lint/format, package build, current official doctor/admission checks.

**Tests passed:** 72 Python tests ran: 70 passed, two Windows symlink-privilege skips. All 19 Node tests passed. Ruff critical lint and format checks and JavaScript syntax passed. Model-free host dispatch and the approved live retry passed independently. All four remote matrix jobs passed; fresh official installation matched the exact candidate SHA. See `RELEASE_EVIDENCE.json`.

**Integration verified:** Hermes 0.20.0 loaded eight hooks in disposable profiles. The actual tool dispatcher executed safe terminal and write_file bodies, enforced destructive/secret blocks, exercised native deny/once fixture decisions, preserved separate sessions, and created/restored automatic file checkpoints. The approved live OpenRouter free-router run invoked terminal and write_file, produced 10 journal events and one checkpoint, and restored the new file to absence. Exactly two API attempts were observed, with a five-attempt cap and 700 output tokens per response. No credential bytes were found in artifacts.

**Known limitations:** All ten scenarios have not been run as live model-driven tasks. Live human approval interaction, concurrent live-model sessions, gateway/Desktop sessions and production-profile execution remain unverified. Native approval fixtures must not be described as human interaction. The personal model's initial HTTP404 is retained in the evidence. See `HOST_ACCEPTANCE.md`, `HOST_ACCEPTANCE.json`, and `LIVE_ACCEPTANCE.json`.

**Commit SHA:** Release candidate `f58da50154aeb8fb9fb0811b4e46a9de267e0f73` on `codex/sentinel-foundation`; runtime implementation `27f32ebc583be0c25c93670701fca60ccd50d66c`. Subsequent evidence-only commits preserve that immutable candidate pin. Earlier baseline: `4f52afc1366383a8ea95d14bb404cfbf96d48c05`.

**Next implementation step:** Complete the broader live approval/restricted-task recording before claiming all-scenario acceptance, obtain license/public-release approval, and submit a reviewed catalog pin only after public-release gates pass.

## Security findings fixed

- Unsafe Git flags and configured diff/textconv execution no longer inherit read-only classification.
- Executable-path spoofing, newline command chaining, conflicting command aliases, Windows shell escaping, and tool-name/command confusion no longer silently allow execution.
- Mission path operands, recursive implicit access, sensitive path spelling, alternate data streams, and normalized URL host aliases receive conservative decisions.
- Operator JSON rejects duplicate keys rather than interpreting ambiguous policy documents.
- Concurrent restore requests claim a checkpoint through SQLite before changing bytes. Interrupted/failed restore status is explicit; no automatic retry discards newer data.
- Checkpoint identity cannot override integrity metadata. Large-file limits are checked before reading the original.
- Real database writer locks cause explicit pre-execution blocks, followed by successful operation after the lock is released.
- Malformed API objects and non-ASCII authorization do not silently terminate requests. Retention timestamps require timezone and normalize to UTC.

This remains hook-level enforcement, not OS isolation. Enabled plugin order, host approval mode, remote tool semantics, file races and disabled/unloaded plugins remain material boundaries. No scanner or Hermes core override was used.

## Module evidence matrix

- **Guard:** Implemented, unit tested, actual host dispatcher/native-fixture gate tested, model-safe-operation tested, browser rule persistence verified. Broader live adversarial and live human decisions remain open.
- **Watch:** Implemented, concurrent persistence tested, real host/live events captured, actual API and browser connection/reconnection verified. Long-running production/gateway soak remains open.
- **Replay:** Implemented, read-only queries and full-journal pagination tested, 1,205-event API history verified, 2,000-record bounded browser window, explicit export scope, browser details/focus and stale-data recovery verified. No side-effect replay route.
- **Missions:** Implemented, expiry/pause/concurrent association tested, browser lifecycle previously verified, configured mission used in actual live conversation. Model-driven out-of-scope attempt still pending.
- **Recovery:** Implemented, conflict/corruption/path tests and concurrent restore claim tested. Actual Hermes write and model-generated write both checkpointed/restored. Browser manual create/seal/restore verified against actual bytes. Universal rollback is not supported.
- **Mesh:** Implemented shared journal and separate session attribution, concurrent storage tests, actual two-session host evidence. Concurrent live agents and cancellation controls are not claimed.
- **Control Room:** Eight routes verified; desktop 1440x1000 and narrow 390x844 captures, no narrow document overflow, persisted rules affect decisions, file restoration and Replay details work. Offline refresh retains stale records and reconnect preserves persistent state. Node tests are DOM contract tests, not a substitute for browser layout checks.

## CI, installation and catalog

The missing-CI diagnosis was a connector limitation: `fetch_commit_workflow_runs` filters to pull-request runs. GitHub CLI/API confirms both earlier push runs succeeded:

- [Baseline implementation CI](https://github.com/folarihn/Sentinel/actions/runs/42031161252)
- [Baseline installation-evidence CI](https://github.com/folarihn/Sentinel/actions/runs/42031482505)

The current workflow covers Ubuntu/Windows and Python 3.11/3.12, Python tests and critical lint/format, Node syntax/regressions, and wheel build. Optional Hermes checks skip in CI without a host; installed-host evidence is separate. No model credential is placed in CI.

All four candidate jobs passed in [run 42035631740](https://github.com/folarihn/Sentinel/actions/runs/42035631740). An earlier Windows/Python 3.11 wheel build failed because the runner's preinstalled backend did not satisfy declared requirements; switching to isolated builds fixed it. A new official install on Hermes 0.20.0 matched candidate `f58da50154aeb8fb9fb0811b4e46a9de267e0f73`, enabled version 0.1.1 and loaded eight hooks without errors. Its temporary profile was removed afterward.

Installed Hermes 0.20.0 has no doctor/validate commands. A separate official upstream checkout at `c55af2c93b9d61f5db7943fbc5ff50553038171f` ran both commands on a fresh source snapshot: doctor passed; admission validation passed. The validator used installed Python dependencies without modifying the primary Hermes installation. No `--install-deps` mutation of that environment occurred because Sentinel has no runtime dependencies.

The first admission attempt flagged a denylist string as dangerous. Transparent command-family classification fixed that false positive; the unchanged scanner now returns pass with caution. Retained warnings cover the formatter-name denylist and private host imports used only by acceptance scripts. Reviewer attention is required; this is not catalog acceptance. Full output is in `CATALOG_VALIDATION.json`.

Doctor and all 15 admission checks also passed against an exact Git archive of the candidate, not merely the working tree; `PINNED_VALIDATION.json` retains the result and warnings. The concrete draft `catalog/sentinel.yaml` pins that SHA and passed the official catalog schema validator. It is not submitted, publicly reachable or accepted.

## Release gates

Repository remains private. No LICENSE has been added without owner approval. No public deployment, social post, catalog PR or hackathon submission was performed. Release documents contain the checklist, proposed license, exact-pin process and reproducible 90-second script. Full live adversarial/human approval coverage and a real final recording remain open; this candidate is not advertised as a completed submission.

## Reproduce

```powershell
python -m unittest discover -v
node --test tests/frontend.test.cjs
node --check sentinel/web/app.js
python scripts/host_acceptance.py
# Explicit provider approval required; never run in ordinary CI:
python scripts/live_acceptance.py --model openrouter/free
python scripts/verify_catalog.py --host-source .tools/hermes-validator
python scripts/verify_install.py --expected-sha <exact-pushed-code-commit>
uv build --wheel
```
