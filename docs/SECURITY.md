# Security model and limitations

Trusted: Hermes host, Sentinel plugin code, local operator, state directory,
dashboard bearer token, and enabled plugin order. Untrusted: model-produced
tool names/arguments, remote content, policy-test input, recorded payloads.

Mandatory protections precede mission permissions. Sentinel returns an explicit
block on internal pre-tool failures because Hermes otherwise ignores hook
exceptions. Storage initialization failures prevent plugin loading and must be
noticed in host diagnostics; they do not install a host-independent safety layer.

Native approval keys hash the exact arguments and supplied identity. Sentinel
does not retain a broad tool-wide grant. Native host modes and callbacks remain
authoritative. CLI/gateway timeout handling belongs to Hermes; Sentinel does not
invent a dashboard transport. Recorded approval requests are not proof that a
human decision is currently pending.

Sensitive argument keys and common credential patterns are redacted before
event persistence. Tool result bodies are intentionally omitted. Arbitrary
unrecognized secrets remain a residual risk. Do not expose the state directory
or use actual production secrets in a demonstration. Backups contain original
file bytes and require local OS access controls. The service never exposes backup
bytes through its API.

The local server requires bearer authentication on every API, validates Host and
Origin, limits request bodies, allows only explicit static assets, and sets a
restrictive content security policy. It is a local operator service, not an
internet-facing hardened deployment. Do not reverse-proxy it publicly.

File confinement resolves existing symlinks; recovery rejects symlink components.
Atomic replacement and hash rechecks reduce races without preventing a hostile
concurrent writer. Shell parsers cannot establish complete behavior of arbitrary
scripts, network redirects or installed commands. Unknown execution escalates;
directory-scoped missions block shell work that cannot be confined.

Recovery cannot undo external API calls, database operations, financial transfers,
emails or deployments. It does not overwrite newer local edits automatically.
Emergency pause affects future calls associated with a paused mission; it does
not cancel a tool already executing. No OS-level sandbox is advertised.

Phase 5 regression tests exercise the actual native gate under a temporary
session YOLO setting: approval escalation can pass without a human, while an
explicit Sentinel BLOCK still vetoes execution. The test executes no dangerous
tool body, restores the temporary session mode, and never changes personal settings.

The safe-shell grammar is deliberately small. Explicit executable paths,
unverified flags, interpreter execution, Windows escape/expansion syntax,
configured Git diff/textconv behavior and recursive implicit access require
approval or are blocked by mission scope. This reduces known bypasses without
claiming arbitrary installed commands have been sandboxed.

Restoration claims are serialized by a SQLite transaction. A crash after a claim
can leave RESTORING; a caught failure records FAILED. Neither state is automatically
replayed. Inspect the actual file and checkpoint before any operator recovery.
OS permissions, symlink/junction races and external concurrent writers remain
outside the guarantee. Database locks cause pre-execution blocking and are tested
with an actual SQLite writer lock rather than a mocked exception.

Report security issues privately to the repository owner. Avoid including real
credentials or private user data in an issue or test fixture.

SQLite journal mode is selected from the linked library's patch level. Versions
affected by SQLite's documented WAL-reset corruption issue use rollback mode;
patched versions may use WAL. This changes neither Hermes core nor the user's
embedded Python. See the [SQLite advisory](https://sqlite.org/wal.html#walresetbug).
Busy-timeout, concurrent writer, restore-claim and persistence tests cover the
selected mode; a mode-change lock failure is surfaced rather than ignored.
