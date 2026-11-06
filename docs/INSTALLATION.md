# Installation and local configuration

Sentinel requires Python 3.11+ and the Hermes plugin hook contract described in
[HERMES_API.md](HERMES_API.md). Installed-Hermes execution has been exercised on
Hermes 0.20.0 on Windows. CI covers unit/frontend behavior on Windows and Linux;
that does not establish every host or gateway mode is supported.

## Choose a profile

Hermes discovers user plugins beneath `$HERMES_HOME/plugins`. If HERMES_HOME is
unset, Hermes uses its normal user profile. For evaluation, select a **new**
disposable profile through HERMES_HOME before installation. Do not overwrite an
existing configuration or copy personal credentials into a test profile. Use the
same selected profile when enabling, listing, and running Hermes.

The official installer is:

```shell
hermes plugins install https://github.com/folarihn/Sentinel.git --enable
hermes plugins list
```

Review source before enabling a privileged plugin. Restart the selected Hermes
process after installation and check its diagnostics for load errors. Safe mode,
a disabled plugin, or unsupported dispatch can prevent enforcement.

## Pin a reviewed commit

Use an exact 40-character commit from the release you reviewed. Newer Hermes CLIs
may support a ref option; inspect your installed `hermes plugins install --help`.
The inspected 0.20.0 CLI lacks that option. Its supported fallback is a Git checkout
inside the selected profile's plugins/sentinel directory, followed by official
enablement:

```shell
git clone https://github.com/folarihn/Sentinel.git SENTINEL_PLUGIN_DIRECTORY
git -C SENTINEL_PLUGIN_DIRECTORY checkout --detach REVIEWED_40_CHARACTER_SHA
hermes plugins enable sentinel
hermes plugins list
```

Replace SENTINEL_PLUGIN_DIRECTORY with the selected profile's plugins/sentinel
path. Use a full clone so an older reviewed pin remains available after later
commits. Keep root plugin.yaml, root __init__.py, and the sentinel package together.
A separately performed clone also avoids the inspected host's fixed 60-second
convenience-installer clone limit on slow connections. Enabling and discovery
still use the official Hermes manager. Private repositories require existing Git
authentication; never embed tokens in clone URLs or configuration examples.

## Start the dashboard

From the reviewed checkout, create and activate a separate Python virtual
environment, install the package, and start the local service:

```shell
python -m pip install .
python -m sentinel.server --workspace PATH_TO_YOUR_WORKSPACE --port 8765
```

With uv, an equivalent isolated setup is `uv venv .venv`, then
`uv pip install --python .venv/Scripts/python.exe .` on Windows; use that
interpreter to run `-m sentinel.server`. This does not upgrade Hermes' Python.

The service prints its loopback URL and a fresh session token. Enter the token in
Settings. The browser keeps it in tab session storage and sends it to the same
origin. Never publish it or reverse-proxy the service to the internet.

## Share the correct local state

Both processes resolve state as SENTINEL_HOME, otherwise HERMES_HOME/sentinel,
otherwise ~/.hermes/sentinel. The server's `--data` overrides its data location;
`--workspace` sets the root for supported manual file recovery. A dashboard with
an empty or different journal is not evidence that an agent did nothing.

Operator policy is stored as policies.json under that state directory. Missions,
events, and original backup bytes are local. Protect them with OS permissions.
See [policies](POLICIES.md) and [security](SECURITY.md).

## Troubleshooting

- **No events:** verify plugin loading, selected profile, shared data directory,
  and supported dispatch before checking the browser connection.
- **Approval differs by host mode:** Hermes owns the transport, timeout, YOLO,
  and cron behavior. Recorded approval requests may no longer be pending.
- **Locked database or initialization error:** inspect local diagnostics and
  state permissions. Do not disable protections to conceal the error.
- **Restore refused:** check that the checkpoint is sealed, hashes match, the
  path is supported, and no newer edit would be overwritten.
