# Verified Hermes integration contracts

Verified on November 5, 2026 against installed Hermes **0.20.0** (both
`hermes_cli.__version__` and the installed `pyproject.toml`) at
`%LOCALAPPDATA%/hermes/hermes-agent`. The executable and source were present;
the primary profile, memory, credentials, and configuration were not modified.

Sources of truth are the installed `hermes_cli/plugins.py`,
`hermes_cli/lifecycle.py`, `tools/approval.py`, and `tools/terminal_tool.py`,
alongside the [official plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins).
The installed host contract takes precedence over speculative extension names.

## Registration and discovery

A plugin directory contains `plugin.yaml` and `__init__.py` exporting
`register(ctx)`. Sentinel uses `ctx.register_hook(hook_name, callback)`.
The host discovers user plugins in `$HERMES_HOME/plugins/`, and explicitly
enabled plugins are listed under `plugins.enabled` in `config.yaml`.
`HERMES_SAFE_MODE` skips discovery. Project plugin discovery requires the
separate `HERMES_ENABLE_PROJECT_PLUGINS` opt-in.

Public `discover_plugins(force=True)` and
`get_plugin_manager().list_plugins()` provide discovery and load evidence.

## Enforcement

`pre_tool_call` receives `tool_name`, `args`, `task_id`, `session_id`,
`tool_call_id`, `turn_id`, `api_request_id`, and `middleware_trace` where
provided by the caller. Do not assume an agent identifier is always present.

Return `None` for no restriction, or a dictionary:

```python
{"action": "block", "message": "Human-readable reason"}
{"action": "approve", "message": "Approval reason", "rule_key": "exact-operation-hash"}
```

The first valid host directive wins. `block` requires a nonempty message.
The inspected host accepts `block` and `approve`; argument modification is
not part of this contract. Sentinel does not advertise MODIFY.

`resolve_pre_tool_block(...)` invokes lifecycle hooks and, for an `approve`
directive, calls `tools.approval.request_tool_approval`. Denial, timeout, or
an approval-gate exception becomes a block. Sentinel keys the request to
the exact tool, arguments, and supplied execution identity, preventing a
grant from silently covering a different operation.

Native Hermes approval modes remain authoritative: host YOLO mode can
bypass recoverable approval prompts, and cron approval policy is host-owned.
Sentinel's explicit BLOCK directives remain blocks. Do not describe approval
escalation as an unconditional human prompt under every host configuration.

Host hook exceptions are logged and ignored. Sentinel therefore catches its
own evaluation/storage failures and returns an explicit block. A plugin that
never loaded, a disabled plugin, or a host-level hook failure cannot provide
protection. No independent OS sandbox or universal fail-closed runtime is
claimed. No hook timeout guarantee was found in the inspected synchronous
callback invocation loop.

## Observation and approvals

Supported hooks used by Sentinel: `post_tool_call`, `on_session_start`,
`on_session_end`, `subagent_start`, `subagent_stop`,
`pre_approval_request`, `post_approval_response`.
Approval observer hooks report native request/decision events; returning a
value from these observer hooks does not grant approval.

`PluginContext` exposes tool, hook, slash-command, CLI-command, middleware,
and a public `subagent_lifecycle` service. No
`ctx.register_approval_transport` method exists in this installed version.
Sentinel uses native CLI/gateway approval and offers no dashboard button
that purports to decide a request it cannot control.

## Real-host integration test and limits

Run `python -m unittest discover -s tests -p test_hermes_integration.py -v`
with the installed Hermes Python environment, or a compatible environment
that imports Hermes. It skips if Hermes is unavailable.

The test copies Sentinel into a disposable `HERMES_HOME`, enables it through
the real host config, discovers and loads it, and checks the actual host
dispatch gate for a safe command, destructive command, synthetic secret
path, denied native approval, once-approved native approval, and a changed
operation that requires a new decision. The approval human callback is an
explicit fixture installed through `set_approval_callback`; the policy,
plugin loader, lifecycle, and approval gate are real installed Hermes code.

This is a host contract integration test. It does not invoke an LLM, run
terminal tool bodies, contact a gateway, or prove a live personal agent
session. No credentials are copied into the disposable profile. Full live
LLM and gateway scenarios require separate evidence before claiming them.
