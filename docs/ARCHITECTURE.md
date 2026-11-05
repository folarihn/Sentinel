# Architecture

The root manifest and `register(ctx)` load a Python adapter through Hermes'
official plugin manager. The adapter delegates to `Runtime`; the mandatory policy
engine has no dependency on the dashboard. Before execution, the adapter resolves
session authority, evaluates policy, persists redacted request/decision events,
then returns the host's documented block/approve directive or no restriction.

SQLite is the common local authority and journal. Each operation uses its own
connection, a busy timeout, and explicit close. WAL is used only on SQLite
versions containing the WAL-reset corruption fix (3.51.3+, 3.50.7, or 3.44.6
backports); affected embedded builds use rollback journaling. The local host
does not need to be upgraded or patched by Sentinel. Journal mode is visible
in service diagnostics.
Mission activation uses a write transaction to prevent duplicate authority for
one session. Schema version 1 is explicit; unknown versions are rejected.

The authenticated threaded localhost HTTP service reads the same state. Its
buildless HTML/CSS/JavaScript client uses polling and cursor pagination. Replay
only reads events and downloads a sanitized report; it has no re-execution route.
Mission mutations persist server-side, so browser state never grants authority.

Recovery stores original bytes separately from the event payload. A checkpoint
must be sealed with the observed post-write hash before restoration. Restore
requires authorization and matching current hash, validates confinement and
backup integrity, and writes atomically where the filesystem supports replacement.
Automatic pre/post capture requires a structured write tool, an explicit path,
a supplied tool-call ID and one mission root. Arbitrary patch formats and shell
side effects do not imply recovery support.

The session registry derives recorded activity rather than asserting process
liveness. Agent and cross-agent correlation are retained only when host events
provide them. Missions can narrow an identified agent's/session's authority;
there is no remote kill switch or unsupported host cancellation mechanism.

Future runtimes should supply a separate lifecycle adapter over these contracts,
without placing runtime-specific authorization in the web client.
