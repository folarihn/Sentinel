# Prepared private history cleanup

Status: owner explicitly authorized the concrete force-with-lease update; remote branch synchronization completed and was verified. Repository visibility remains private. No catalog PR, X post or form submission is authorized by this operation.

## Before and after

Remote branch: refs/heads/codex/sentinel-foundation.
Expected remote lease: aa5d0334203b46a7f231e94a0051d6442ab19afe.
Pre-cleanup local head: 36c7c553dbf6e938ba1eae01c8742a54246cce08.
Rewritten equivalent: 414d4fe781b0bea573c2190560adabfddc512831.
Prepared final code pin after modern MIT package metadata: 92a3b1910b697a75a80b66f360445c335c1ec516.
The evidence-only follow-up head is recorded by Git, outside this self-referential document.

All eight legitimate commits were preserved. The rewritten equivalent has exactly the same source tree as the pre-cleanup head. The subsequent deliberate package change uses SPDX MIT metadata and setuptools >=77.0.3. The owner-approved LICENSE, genuine denial evidence and approval session-attribution fix are included.

## Narrow rewrite scope

- Replace personal-home/repository prefixes in historical text, including console-wrapped and JSON-escaped report strings. Preserve validator decisions, cautions and failures.
- Remove eight obsolete historical screenshots under docs/screenshots: control-room-browser-qa.jpg, replay-browser-qa.jpg, and the six phase5 captures. Genuine current release screenshots remain.
- Replace owner author/committer display/contact metadata with folarihn and folarihn@users.noreply.github.com. No unrelated repository or third-party history is modified.
- Exclude two editor-only tree capture refs from the publication mirror. They remain backed up and are never pushed to GitHub. No remote tag or other branch exists.

## Offline recovery

Private ignored bundle: .tools/private-history-backup/sentinel-before-cleanup.bundle in the original workspace. Ref inventory, pre-cleanup HEAD, SHA-256 and restore verification are beside it. It is an offline file, not uploaded. The bundle contains complete pre-cleanup refs, including editor snapshots. A mirror restored from the bundle passed git fsck --full, and every restored ref matched the recorded inventory. The working tree was clean before backup. Never publish this directory or mirror-push the original repository.

## Verification and remaining boundary

Full rewritten reachable-history scan: zero failing findings; remaining text findings are synthetic tests. Image metadata was scanned; image pixels require visual review and were inspected separately. No committed build artifacts, credentials, private endpoint or personal configuration was identified by these checks. Pattern matching and visual review cannot prove absence of arbitrary undiscovered secrets.

The final code candidate passed full local tests, exact-source doctor/admission and a fresh official file-URL installation. The fresh four-job GitHub matrix passed against the exact new code pin (run 42090229145). Four official remote install attempts timed out in Git clone, including process-only HTTP/1.1 and pre-authenticated GitHub CLI helper checks. Offline exact-pin official installation passed; remote installation remains BLOCKED. Older green runs remain historical only.

The only proposed remote write is replacement of refs/heads/codex/sentinel-foundation using --force-with-lease with the exact expected old SHA above, from the isolated cleaned review checkout. Do not use --mirror or a blanket --force. Recheck the remote lease immediately before pushing; stop if it changed. Fetch and inspect the resulting remote branch afterward.

Remote inspection found one private branch, no tags, no PRs and zero reported forks. GitHub may still retain old objects, Actions records, cached views, hidden references or inaccessible copies after a rewrite. No local operation guarantees erasure of every remotely retained copy. Review that limitation before separately approving public visibility.

## Confirmed remote retention

After synchronization, authenticated GitHub API lookup still returned the old commit aa5d0334203b46a7f231e94a0051d6442ab19afe. It is no longer advertised by branch/tag refs, but the object remains retrievable by a known SHA. Public visibility has not changed. Review this confirmed retention and, if required, ask GitHub Support to purge cached/unreachable sensitive objects before approving public visibility. No support message was sent.
