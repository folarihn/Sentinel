# Release candidate 0.1.1

SENTINEL OS is an installable Hermes policy, observability and supported-file recovery plugin with a local Control Room. This prepares a release candidate; it does not declare completion of all ten live scenarios, catalog admission or final submission.

## Install and verify

Use Python 3.11+ and a compatible Hermes installation. Actual host and live-model execution were verified on installed Hermes 0.20.0 on Windows. Review [SECURITY.md](SECURITY.md) before enabling a trusted runtime plugin.

After owner approval for public visibility, a discovery install is:

```powershell
hermes plugins install https://github.com/folarihn/Sentinel.git --enable
hermes plugins list
```

A stable install must use the **exact 40-character SHA in the reviewed release record**. Newer Hermes versions support official `--ref`; the inspected 0.20.0 CLI does not. On 0.20.0, clone the repository into the selected profile's plugin directory, use Git to check out the exact reviewed SHA, and enable `sentinel` with the official CLI. The fresh installer verifier additionally checks that the remote revision it installed equals the supplied expected SHA; this verifies that run without making a branch URL immutable. Private installs require existing Git authentication; never put tokens in Git URLs or command arguments.

Restart the relevant Hermes process and verify Sentinel is enabled without load errors. From a reviewed checkout, start its independent local Control Room:

```powershell
python -m pip install -e .
python -m sentinel.server --workspace . --port 8765
```

Default journal storage follows `SENTINEL_HOME`, otherwise `HERMES_HOME/sentinel`. Pass `--data` explicitly for disposable or recorded journals. Enter the locally printed token in the browser without recording or sharing it. Keep the service on loopback; public deployment is outside this release's scope.

## Evidence and disclosures

- [HOST_ACCEPTANCE.json](HOST_ACCEPTANCE.json): real Hermes tool execution, blocked operations, native approval **fixture** decisions, mission pause, two sessions and persistence.
- [LIVE_ACCEPTANCE.json](LIVE_ACCEPTANCE.json): approved `openrouter/free` model session, two API requests, actual terminal/file write, automatic checkpoint and restoration. The initial configured model failed with HTTP 404.
- Current doctor/validation checks passed with disclosed cautions: defensive `mkfs` denylist text and host imports in acceptance/test tooling. Findings are unsuppressed; passing validation is not catalog admission.
- Hooks run inside trusted Hermes. Coverage requires an active loaded plugin and supported tool dispatch. This is not an OS sandbox. Native host approval modes, including YOLO, remain authoritative for escalation.
- Runtime Sentinel requires no external SaaS, provider credential or automatic telemetry. Optional live acceptance sends explicitly authorized synthetic data to the model provider; that tooling is not a plugin requirement.
- Events are redacted and stored locally. Recovery retains original file bytes locally. Operator permissions must protect backups and dashboard tokens. Unrecognized secrets and hostile concurrent filesystem races remain residual risks.
- Recovery cannot undo emails, APIs, blockchain transfers, arbitrary shell side effects or deployments. Mission pause blocks future associated calls; it does not cancel running tools.

## Owner licensing decision

**Recommendation requiring owner approval: MIT.** Its permissive terms suit a reusable community plugin. No `LICENSE` file has been added because the directive reserves the choice for the owner. Do not advertise MIT licensing or distribute under it until the owner approves and the actual text/copyright notice are committed. Review third-party assets separately.

## Public release checklist

- [ ] Owner approves the license and public visibility; commit the approved license.
- [ ] Version metadata consistently identifies 0.1.1; freeze a clean reviewed commit and record its exact SHA.
- [ ] Run required local checks and inspect completed CI for that SHA; retain genuine screenshots.
- [ ] Run official doctor/validation against the pinned tree and preserve all cautions.
- [ ] Install the exact SHA in a fresh disposable profile; verify loading and Control Room data connection.
- [ ] Review protections, native approval host modes, backup permissions and API tokens.
- [ ] Keep incomplete evidence explicit: all ten live scenarios, manual human native approval interaction, gateway/Desktop and concurrent live-model operation remain separate checks.
- [ ] Owner changes visibility after review; do not change it automatically.
- [ ] Generate/validate the catalog entry once the public pin is reachable; obtain approval before opening the PR.
- [ ] Record/review the genuine under-90-second demo using [DEMO.md](DEMO.md).
- [ ] Prepare links/social text and obtain explicit approval before posting or submitting.

November 10 is the engineering release target. The stated deadline is November 11, 2026, 5:00 PM US Eastern Standard Time / 11:00 PM Africa/Lagos. Verify official competition requirements again before submission.
