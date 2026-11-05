# Owner review and submission packet

Prepared for the November 10, 2026 internal target. Nothing in this packet has
been posted, submitted or made public. The authoritative final pin, CI run and
installer/validator evidence belong in `RELEASE_EVIDENCE.json`; do not submit an
older pin while release changes are still being reviewed.

## Catalog PR draft

**Title:** Add SENTINEL OS: local policy, execution evidence and file recovery for Hermes

**Body:**

SENTINEL OS evaluates supported Hermes tool requests before execution and records
redacted runtime events in a local journal. Its independent loopback Control Room
provides policy explanations, Watch, forensic Replay, mission authority,
supported-file recovery and multi-session visibility.

This entry proposes a community plugin maintained by `folarihn`, installed from
`https://github.com/folarihn/Sentinel`. The catalog YAML must pin the exact reviewed
40-character release commit and copy its manifest capabilities. It registers
pre/post tool, session, subagent and native approval observation hooks. No model
tool, middleware or mandatory provider credential is declared. Refer to the
final `docs/catalog/sentinel.yaml` and release evidence for the concrete pin.

### Privilege and security disclosures

- This is trusted in-process Python code with the Hermes process's privileges,
  not an OS sandbox. Protection depends on enabled loading, host dispatch
  surfaces and plugin ordering. No Hermes core monkey-patching is performed.
- Mandatory blocks and narrower missions govern supported requests. Unknown
  shell behavior receives conservative approval/block decisions. Native Hermes
  approval modes remain authoritative; YOLO can bypass escalation but does not
  turn an explicit Sentinel BLOCK into ALLOW. No unsupported MODIFY directive or
  dashboard approval transport is claimed.
- The journal, policies, missions and backup originals remain local. Original
  checkpoint bytes are plaintext local backups requiring OS access controls.
  Event redaction is conservative, not a universal detector of arbitrary secrets.
- The separately started dashboard binds to loopback and requires a bearer token
  for its APIs. It is not an internet-facing service. Closing it does not disable
  the plugin. A connected browser alone does not prove Hermes plugin health.
- File restoration requires authorization, valid hashes and conflict checks.
  It cannot undo APIs, emails, transactions, deployments or arbitrary shell
  side effects. Filesystem races remain outside an OS-isolation guarantee.
- No automatic runtime telemetry or mandatory SaaS is included. Optional live
  acceptance tooling uses explicitly authorized synthetic model requests;
  provider keys are kept in process memory and are not plugin requirements.
- Doctor/admission results and all scanner cautions are retained in the release
  reports. Cautions include defensive command-denylist text and host imports in
  acceptance tooling. A local admission pass is not reviewer/catalog acceptance.

### Evidence scope

- Genuine model-driven safe terminal/file operations and automatic recovery:
  `docs/LIVE_ACCEPTANCE.json`.
- Real host execution, restricted-operation blocks, native deny/once **fixtures**,
  missions, separate sessions and persistence: `docs/HOST_ACCEPTANCE.json`.
- Actual owner decisions relayed through the official native callback:
  `docs/ACTUAL_HUMAN_ACCEPTANCE.json`. Four owner choices approved two distinct
  writes; changed operations requested fresh decisions. This is not a CLI-button
  or gateway UI test. A subsequent run recorded two explicit owner denials at
  the Sentinel escalation and native shell gates; neither marker was created.
  Fixture denial remains separately labeled.
- `docs/FINAL_LIVE_ACCEPTANCE.json` verifies a genuine mission-scoped coding task,
  model-attempted destructive/secret/out-of-mission operations being blocked,
  session attribution, automatic checkpointing and restoration. Five bounded API
  requests were made. A Windows short/long-path comparison error in the acceptance
  harness was corrected locally before restoration, without another model call;
  the initial harness failure remains disclosed. Generated source was validated
  through a constrained AST, not executed unrestricted. This is not completion of
  every live scenario, concurrent live sessions or manual human rejection.
- Final screenshots and demonstration must be linked only after their artifacts
  exist and pass privacy/claim review.
- Copy the final CI URL and exact installer/doctor/admission pin from
  `docs/RELEASE_EVIDENCE.json`. Do not reuse an earlier green run for changed code.

Repository visibility and licensing are still owner decisions. This draft is
not ready to send until the final checklist below is complete.

## X announcement draft

The following text is under 280 characters, excluding any links the owner later
adds. It is an unpublished draft and does not claim catalog admission:

> Built SENTINEL OS for Hermes: runtime policy checks, native approvals, live execution visibility, forensic Replay and conflict-aware file recovery. Real Hermes tests, explicit limits. Autonomy with accountability. @NousResearch

Add only the approved public repository/demo links after they exist. Keep the
wording factual if the submitted feature or evidence scope changes.

## Form details to prepare

- Project: **SENTINEL OS**.
- Creator/maintainer: **folarihn**.
- Tagline: **The control plane for autonomous AI agents.**
- Repository: `https://github.com/folarihn/Sentinel` — currently private until
  owner-approved visibility change.
- Runtime: Hermes; actual execution evidence is recorded per host version.
- Summary: Local policy enforcement, redacted execution history, bounded mission
  authority, supported-file recovery and multi-session visibility through an
  authenticated local Control Room.
- Version, full release SHA, CI, installer and validator results: use the final
  `RELEASE_EVIDENCE.json`, not this document's preparation date.
- Catalog PR URL: **not created**; fill only after owner approval and creation.
- Demo URL: **not published**; fill only after the genuine recording is approved
  and uploaded through an authorized destination.
- License: **MIT, owner approved**; complete LICENSE and verified wheel metadata.
- Official form: https://form.typeform.com/to/FwJLvOln. Six questions and the first required Plugin Title field were inspected. Other entrant/contact fields and eligibility terms require owner review; do not infer missing fields.

The supplied competition deadline is November 11, 2026, 5 PM US Eastern Standard
Time / 11 PM Africa/Lagos. November 10 remains the internal submission target.
Verify the official deadline and requirements before final submission.

## Exact remaining owner decisions

Official announcement verified on November 5: [Nous Research announcements](https://nousresearch.com/) confirms catalog PR + X demo tagging @NousResearch + both links in the form, with a demo **under** 90 seconds and November 11 at 5 PM EST. The official short link resolved to [Hermes Agent Plugin Hackathon form](https://form.typeform.com/to/FwJLvOln). Read-only browser inspection confirmed the form title, six questions, and required first field **Plugin Title**. No field was filled and nothing was submitted. Remaining form questions/terms need owner inspection; they have not been guessed.

1. Review the final evidence, candid limitations and genuine media. Actual human rejection is now verified by two explicit owner denials through native callbacks; the original approval evidence is preserved.
2. MIT adoption is approved and complete. Review the license and verified wheel metadata.
3. Review current-snapshot privacy and historical private commits. Earlier
   captures contained personal paths. The concrete force-with-lease synchronization was explicitly approved and completed. Review confirmed retained GitHub objects in GITHUB_RETENTION.md before public visibility.
4. Approve the final repository visibility change. Do not make it public merely
   because this packet or a candidate YAML exists.
5. Approve opening the catalog PR with the final immutable YAML and disclosures.
   Reviewer acceptance remains outside Sentinel's control.
6. Confirm the official form, required identity/contact information, eligibility
   and submission links. Approve the final form submission separately.
7. Approve the final X text and destination/account separately before posting.

Technical preparation must be completed before asking for these publication
actions. Public visibility, license adoption, posting and submission are not
implied by approval of a local runtime test.
