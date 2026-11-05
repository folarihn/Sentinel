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

The owner authorized offline history cleanup on November 5. An isolated publication mirror now removes the eight known unsafe historical captures, sanitizes wrapped and JSON-escaped personal-home prefixes, and replaces personal author/committer contact with the owner's public noreply identity. All eight legitimate commits remain. Its full reachable-history scan has no failing findings and only synthetic fixture review findings. Current release captures, including the genuine denial screenshot, are retained.

The original repository and verified offline bundle intentionally retain private pre-cleanup history for recovery. They must not be published. The owner explicitly approved the single-branch force-with-lease update, which completed. No visibility change has occurred. GitHub may retain old objects and cached views after synchronization; no rewrite guarantees erasure of every remote copy. See HISTORY_CLEANUP.md for exact scope and authorization boundary.

## Verification

`python -m unittest tests.test_release_audit -v`: eight tests passed, including
wrapped-path cleanup, JSON-escaped paths, finding-value confidentiality,
placeholder/fixture classification, image metadata and explicit audit scope.
Critical Ruff lint and formatting checks passed for the owned audit/verifier
files. Final counts should be regenerated after screenshots and release files
have been staged.
