# Catalog submission preparation

No catalog PR has been opened by this document. Public visibility and licensing require owner approval. Generate the final entry only after the clean reviewed release commit is pushed and publicly reachable. Never submit a branch tip, illustrative SHA or pin predating reviewed changes.

## Verified schema and proposed values

The inspected official sources are `scripts/validate_plugin_catalog.py` and `plugin-catalog/README.md` in the local official Hermes validator checkout. Required fields are `name`, `repo`, exact 40-hex `sha`, `description` and `maintainer`. Capability keys are `provides_tools`, `provides_hooks`, `provides_middleware` and `requires_env`. Contributors use `tier: community`; Nous maintainers assign other tiers.

- Name/title: `sentinel` / `SENTINEL OS`; repo: `https://github.com/folarihn/Sentinel`.
- Maintainer: `folarihn`; category: `tools`; tier: `community`.
- Version: read the actual release manifest, expected candidate 0.1.1. Do not label an older pin 0.1.1.
- Compatibility: propose `requires_hermes: ">=0.20.0"` only when the same floor is in the pinned manifest and release checks confirm it. Hermes 0.20.0 is the actual execution evidence.
- Platforms: initially `windows`, the directly verified host. Broaden with corresponding integration evidence.
- Tools, middleware and required environment variables: empty lists. Sentinel itself requires no model-provider credential.
- Hooks: copy the exact pinned manifest list: pre/post tool calls, session/subagent lifecycle and approval observation. Do not declare MODIFY or unregistered hooks.
- README: true. Include only genuine screenshots with GitHub-hosted URLs pinned to the same commit. Omit image fields until files/URLs actually exist.

The exact release SHA is intentionally not fabricated here. The release owner will supply it after committing the final tree. `git rev-parse HEAD` gives the local candidate; verify that identical commit is remotely reachable and reviewed. Later code changes require a new pin and validation.

## Reviewer disclosures

Proposed description, subject to reviewer editing:

“Local runtime policy, redacted execution history and supported-file recovery for Hermes. Trusted in-process hooks; no OS sandbox. Local dashboard uses bearer authentication; backups retain original file bytes. Native Hermes approval modes apply.”

The PR body and README must disclose:

- Registration uses official hooks; no production monkey-patching or Hermes-core changes.
- Selected workspace reads/checkpoints, local event/backup persistence and a separately started local Control Room process.
- No runtime telemetry or mandatory external service. Optional acceptance tooling sends approved synthetic data to OpenRouter and reads the configured key only in memory; it is not plugin registration.
- Native Hermes approval remains authoritative. Acceptance decisions are explicit fixtures; manual human UI interaction is not claimed before recording it.
- Hook coverage, shell-analysis uncertainty, YOLO behavior, filesystem races and non-recoverable external actions.
- Passed doctor/validation with unsuppressed defensive `mkfs` and host-import cautions in test/acceptance tooling. A scanner pass is not catalog admission.
- Passed live `openrouter/free` safe execution/recovery and initial configured-model HTTP 404. All ten live scenarios, gateway/Desktop and concurrent live-model operation are not fully verified.

## Validate and submit

1. Obtain owner approval for licensing/public visibility; make the reviewed commit reachable. Posting and final submission remain separate approvals.
2. Generate `sentinel.yaml` from the exact release SHA and pinned manifest. Omit `subdir` for this root-level plugin. Include factual `known_issues` covering the major hook/approval/recovery limits.
3. From the official Hermes checkout run `python scripts/validate_plugin_catalog.py /absolute/path/to/sentinel.yaml` with its documented `ruamel.yaml` dependency. This checks structure, not runtime safety/admission.
4. Run official `hermes plugins doctor` and `hermes plugins validate` against the pinned tree with supported options. Inspect every caution; do not suppress or weaken validation.
5. On a newer host supporting it, test official install with `--ref` followed by the exact recorded SHA in a new disposable profile. The inspected 0.20.0 CLI lacks `--ref`; use the fresh installer verifier's expected-SHA assertion for that run, or Git-checkout the reviewed SHA in the disposable plugin directory and enable through the official CLI. Verify enabled loading and behavior without copying personal credentials.
6. Prepare a PR to `NousResearch/hermes-agent` adding `plugin-catalog/sentinel.yaml`: immutable pin, evidence links, truthful limitations, licensing, disclosures and genuine demo. Obtain approval before opening it.
7. Inspect admission CI/reviewer findings. Do not claim the entry exists, installs by bare name or is admitted until merged.
