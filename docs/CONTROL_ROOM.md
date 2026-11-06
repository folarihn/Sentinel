# BLACKSITE Control Room

The buildless interface uses local HTML, CSS and JavaScript. No runtime font CDN,
charting service, analytics, UI framework or remote dashboard service is required.

![Guard workbench and an actual dry-run policy response](images/guard-desktop.jpg)

Guard's pictured result is a policy evaluation. The proposed command was not
executed. [Mobile Guard](images/guard-mobile.jpg) uses the same backend semantics.

## Eight operator views

- **Overview** reports journal totals, observed sessions, recorded blocks, recent
  events, mission focus and security decisions. It does not invent trends, risk
  scores or uptime. A connection attests only dashboard transport.
- **Guard** is a dry-run policy workbench and restrictive-rule editor. Decision,
  rule and explanation appear together; raw JSON can be expanded. Saving rules
  changes future requests and never overrides mandatory protections.
- **Watch** polls persisted events. Timestamps, type, session, decision and
  inspection controls come from recorded data. Search filters the loaded window;
  the export explicitly identifies that scope. New-record highlights correspond
  only to newly received journal records.
- **Replay** queries the stored journal by search/session, paginates history and
  exports the loaded scope. It never re-executes tools. Unavailable history keeps
  prior records with a stale-data notice.
- **Missions** shows recorded authority, expiry, session identity and lifecycle.
  Creation groups assignment, file scope, tools/network and expiry. Full paths
  are expandable; abbreviated labels do not change authorization data. Conflicting
  or expired activation is disabled with an explanation.
- **Recovery** shows recorded checkpoint state, creation/restoration timestamps,
  original/post-write hashes, and supported actions. Restore requires confirmation
  and backend checks. No file contents or invented diff are exposed.
- **Mesh** is an observed session registry. No parent-child connections or live
  process state are inferred without corresponding data. Long identities are
  available in accessible disclosure controls; cards retain useful width on
  narrow screens.
- **Settings** authenticates to the local service, shows available diagnostics,
  and applies confirmed event retention. Tokens are not put in URLs or rendered
  as page text; closing/disconnecting the browser does not disable the plugin.

## Navigation, motion and failure states

The desktop sidebar can collapse. On smaller screens, a drawer provides module
navigation, keyboard focus containment, Escape dismissal and focus restoration.
A compact command bar keeps page context, refresh and last synchronization in
view. Forms and expanded disclosures survive polling without granting authority.

Motion marks navigation, actual metric changes, newly observed events and active
refreshes. prefers-reduced-motion disables animations/transitions. The interface
uses IBM Plex Sans, IBM Plex Mono and Space Grotesk served locally under OFL 1.1;
see [font notices](../THIRD_PARTY_NOTICES.md).

Disconnected views retain the last recorded snapshot and explicitly label it
as offline or stale. Unknown totals are unavailable rather than fabricated.
Dark surfaces, focus rings and touch-size controls support compact operation.

The dashboard is not an OS sandbox or a native approval authority. See the
[security boundary](SECURITY.md), [installation](INSTALLATION.md) and
[testing](TESTING.md) guides before enabling Sentinel.
