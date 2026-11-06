# Testing and maintenance

Run checks from the repository root using Python 3.11+ and Node.js 22:

```shell
python -m pip install . ruff build
python -m unittest discover -v
node --test tests/frontend.test.cjs
node --check sentinel/web/app.js
python -m compileall -q sentinel
ruff check --select E9,F63,F7,F82 sentinel tests
ruff format --check sentinel tests scripts __init__.py
python scripts/audit_release.py
python -m build --wheel
```

The CI matrix uses Windows/Linux and Python 3.11/3.12. Windows symlink tests can
skip when the OS denies symlink creation. Installed-Hermes tests skip if Hermes is
unavailable. Report these skips; do not present them as verified host coverage.

## Distinguish the test layers

- Unit and frontend contract tests exercise actual Sentinel code with disposable
  data and explicit fixtures. They do not establish that a model or human acted.
- test_hermes_integration.py uses the real installed loader/lifecycle/native gate
  with explicitly fixture-driven approval decisions; it does not run an LLM or
  terminal tool body.
- test_host_execution.py and scripts/host_acceptance.py run harmless actual host
  tools with temporary state, fixture decisions, and real file recovery.
- scripts/demo.py is a labeled synthetic runtime fixture, useful for learning the
  journal and recovery workflow. Its output is not live Hermes evidence.
- scripts/human_acceptance.py is an optional native-callback relay harness. It
  requires actual operator decisions bound to fresh request nonces and expires
  closed. It is not a CLI-button or gateway UI test. Never fabricate or reuse an
  answer to make acceptance pass. Keep its decision files private.
- scripts/live_acceptance.py is an opt-in synthetic model scenario. It requires
  configured provider credentials and sends data to OpenRouter. Inspect and
  authorize provider/destination/model usage before running it. It is not invoked
  by normal tests or CI. Its request and output-token bounds must remain intact.

Never use personal profiles, production secrets, or destructive real-data tasks.
Generated journals, screenshots of private sessions, recordings, logs and reports
belong outside the public source tree or under ignored .private-evidence/.

## Official host checks

With a separate reviewed official Hermes source checkout:

```shell
python scripts/verify_catalog.py --host-source PATH_TO_HERMES_SOURCE
```

This runs official doctor/admission checks in a disposable profile and writes an
ignored .private-evidence/catalog-validation.json report. Inspect every caution;
a local pass is not catalog reviewer acceptance. Defensive policy strings and
host imports in integration tooling can produce cautions; never suppress a
scanner merely to obtain a green result.

To check official installation in a fresh disposable profile:

```shell
python scripts/verify_install.py --source REPOSITORY_GIT_URL --expected-sha REVIEWED_40_CHARACTER_SHA
```

The source may also be a file URL for a reviewed offline Git checkout. Remote and
offline installation are distinct checks. The primary Hermes profile is not
modified. A slow remote clone can exceed the host CLI's timeout; use the exact
checkout/official enable procedure in [installation](INSTALLATION.md).

Security issues should be reported privately to the repository owner. Keep real
credentials, personal paths, private endpoints and raw runtime records out of
issues, fixtures and commits.
