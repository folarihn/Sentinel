# SENTINEL OS build status

Updated November 5, 2026, Africa/Lagos. Version 0.1.0 engineering preview.

## Milestone report

**Phase:** Foundation plus first integrated implementation across phases 1–4.

**Implemented:** Official Hermes plugin registration; mandatory and operator
policy rules; native approval escalation; redacted SQLite journal; read-only
Replay; persisted missions and seven templates; conflict-aware file checkpoints;
multi-session registry; authenticated local eight-view Control Room.

**Files changed:** Root plugin/package configuration, `sentinel/`, `tests/`,
`scripts/demo.py`, `.github/workflows/ci.yml`, and documentation/screenshots.

**Tests executed:** Installed Hermes Python unittest discovery, Ruff critical
lint and format checks, JavaScript syntax check, compile checks, isolated package
installation, wheel build, disposable runtime demo, and interactive browser QA.

**Tests passed:** 51 tests ran: 50 passed and one Windows symlink-creation test
skipped due to insufficient OS privilege. No failing tests in the final local run.
Ruff critical lint/format, JavaScript syntax, compilation, package install and
isolated wheel build passed. An initial no-isolation build failed because that
fresh environment lacked setuptools; the declared isolated build succeeded.
Initial restricted-socket API test errors were resolved by authorized localhost
test execution. These were environment failures, not hidden skipped API checks.

**Integration verified:** Real installed Hermes 0.20.0 loader discovers a copied
plugin in a fresh temporary profile and registers eight hooks. Its actual
dispatcher/native gate permits a safe request, blocks destructive/synthetic-secret
requests, denies a fixture human decision, accepts a once decision, and requires
a new decision for a changed operation/session. The human callback is a fixture;
no model call or terminal tool body runs in that test. Recovery tests perform
actual disposable file writes and restoration. HTTP tests use real sockets.

**Browser verified:** Authentication; policy evaluation returning an explained
BLOCK; mission draft creation, activation and pause; resulting persisted Replay
history; command center empty and populated states. Genuine screenshots under
`docs/screenshots/` show browser QA fixture activity, not live Hermes telemetry.

**Commit SHA:** See the first implementation commit and subsequent evidence
commit on `codex/sentinel-foundation`; actual SHA is reported in the chat and Git.

**Next implementation step:** Full live-model isolated Hermes scenario suite,
host CLI install validation, broader supported-tool classification and recovery
coverage, richer session/agent lifecycle integration, and release acceptance.

## Feature evidence matrix

- **Guard:** Implemented; unit tested; real host dispatcher/approval integration
  tested. Live model-driven tool execution not yet verified. Operator rule editing
  persists through authenticated API; mandatory protections cannot be relaxed.
- **Watch:** Implemented; persistence/redaction/concurrent writes/HTTP tested.
  Host hooks verified. Live model session/liveness and reconnect soak testing pending.
- **Replay:** Implemented; journal queries tested; browser history verified.
  Read-only export exists; UI exports loaded records and discloses completeness.
  Controlled re-execution intentionally absent.
- **Missions:** Implemented; schema/concurrency/expiry/pause/isolation tested;
  browser create/activate/pause verified. Full real-model mission scenario pending.
- **Recovery:** Implemented; automatic narrow write capture and actual file
  restoration tested. Manual checkpoint/seal/restore APIs exist; full browser
  restoration and real Hermes file-tool scenario pending.
- **Mesh:** Implemented registry/shared journal and agent/session restrictive rule
  selectors; concurrent attribution tested. Real subagent lifecycle end-to-end
  scenario and host cancellation controls not verified. No active-process liveness
  or OS isolation claim.
- **Control Room:** Implemented eight views; syntax/render/escaping checks and
  selected browser workflows verified. Full accessibility, responsive-device,
  failure/reconnect and keyboard end-to-end matrix pending.
- **Release:** CI configured; local package install/wheel build passed. Remote
  CI result, public license, catalog acceptance, final live demo and submission
  remain separate release gates. No module is marked final demo-ready yet.

## Known limitations and blockers

1. Personal Hermes installation was inspected read-only; its profile, memory,
   credentials and sessions were not modified. Gateway status is unverified.
2. No live LLM credentials were copied or used. A genuine final runtime demo and
   all ten requested live integration scenarios are not yet complete.
3. Installed `hermes plugins --help` lists install/update/remove/list/enable/disable;
   `doctor` and `validate` are unavailable. Current upstream catalog validation
   requires a compatible newer isolated host before claiming those checks passed.
4. Source verified no `register_approval_transport` method. Native approval is
   used; there is no dashboard approval button or unsupported MODIFY behavior.
5. Hermes host approval modes, plugin order and ignored hook exceptions impose
   boundaries documented in `HERMES_API.md`. Sentinel catches its own pre-hook
   errors, but cannot protect execution if it never loads.
6. Scoped missions reject shell operations that cannot be confined. A directory
   is not a sandbox. Unknown tools/scripts escalate rather than being presumed safe.
7. Automatic recovery covers explicit structured writes with a supplied call ID
   and exactly one mission root. Approve-gated writes and arbitrary patches/shell
   changes do not automatically gain recovery coverage. No universal rollback.
8. SQLite originals are plaintext local backups. Protect the state directory with
   OS permissions. Secret redaction is conservative but not a universal detector.
9. No license or public visibility change is authorized. Repository remains private.
10. No social post, live deployment, catalog PR or final submission was performed.

## Reproduce

`python -m unittest discover -v` with installed Hermes for optional host checks.
`node --check sentinel/web/app.js` for frontend syntax.
`uv build --wheel` for isolated distribution build.
`python scripts/demo.py` for a clearly disclosed disposable fixture workflow.
