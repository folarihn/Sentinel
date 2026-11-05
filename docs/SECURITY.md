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

Report security issues privately to the repository owner. Avoid including real
credentials or private user data in an issue or test fixture.
