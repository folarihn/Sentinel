# Release privacy audit

This report concerns the Git-tracked **working snapshot**, not all earlier commits
or arbitrary local files. Reproduce it with `python scripts/audit_release.py`
after staging the intended release files. The checker prints locations, categories
and severities without printing matched credential values. It is a conservative
release aid, not a guarantee that every possible secret has been detected.

## Findings and corrections

- The stored official doctor output in `CATALOG_VALIDATION.json` contained a
  personal home-directory prefix. Rich console wrapping had inserted a newline
  inside that path, defeating the old exact-string replacement. That display
  location is now `<temporary>/sentinel`; official exit codes, checks and warnings
  are unchanged.
- `scripts/verify_catalog.py` now removes known local prefixes even when console
  wrapping splits them or JSON doubles the separators. Regression tests confirm
  failure decisions and warning text remain present; no validator finding is
  suppressed.
- The current automated tracked-text/metadata pass reports no failing credential,
  personal home-path or private-endpoint finding. Two review findings in
  `tests/test_store.py` are deliberate synthetic redaction fixtures: a private-key
  header with the literal dummy body and a dummy URL credential. They are not
  operational credentials. The checker retains them as review findings.
- Older screenshots were removed from the current tree and replaced with genuine
  final browser captures under `screenshots/release/`. All eight desktop and
  mobile views were checked for rendered personal/absolute filesystem paths;
  checkpoint and matching workspace labels are derived relative display values,
  while actual stored authorization paths remain unchanged. No image pixels were
  altered to hide evidence. Actual-human event detail was checked before capture.
  The automated pass still marks image pixels for review because it is not OCR;
  that review is covered by the browser inspection, not silently suppressed.

The web assets inspected are project-authored HTML, CSS and JavaScript. No
external font import or bundled third-party font asset was found in that surface;
the screenshots are genuine browser captures. This is not a legal clearance of
every dependency or a substitute for the owner's license decision.

## Historical content and publication gate

Snapshot cleanup does not remove paths visible in earlier committed reports or
screenshots. Earlier private commits contain such historical captures. No
history rewrite, force push, repository visibility change or external publication
was performed. Before making this repository public, the owner must review the
historical path exposure as well as the final tree and decide whether to authorize
history cleanup. Do not describe a clean current snapshot as a clean Git history.

## Verification

`python -m unittest tests.test_release_audit -v`: eight tests passed, including
wrapped-path cleanup, JSON-escaped paths, finding-value confidentiality,
placeholder/fixture classification, image metadata and explicit audit scope.
Critical Ruff lint and formatting checks passed for the owned audit/verifier
files. Final counts should be regenerated after screenshots and release files
have been staged.
