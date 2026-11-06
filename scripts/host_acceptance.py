"""Real Hermes tool-dispatch acceptance in a new credential-free profile.

No model is called. Approval decisions are explicit fixture callbacks through
Hermes' public approval API, never represented as live human decisions.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def worker(root):
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from model_tools import handle_function_call
    from tools.approval import set_current_session_key, reset_current_session_key
    from tools.terminal_tool import set_approval_callback
    from sentinel.store import Store
    from sentinel.recovery import Recovery

    root = Path(root)
    workspace = root / "workspace"
    discover_plugins(force=True)
    info = next(
        p for p in get_plugin_manager().list_plugins() if p["name"] == "sentinel"
    )
    assert info["enabled"] and not info["error"], info
    store = Store(root / "state")
    evidence = {
        "host_dispatch": "model_tools.handle_function_call",
        "live_model": False,
        "human_decisions": "fixture callbacks",
        "checks": {},
    }

    def call(name, args, session, call_id):
        result = handle_function_call(
            name, args, session_id=session, task_id=session, tool_call_id=call_id
        )
        return json.loads(result) if isinstance(result, str) else result

    safe = call(
        "terminal",
        {"command": "echo SENTINEL_REAL_TERMINAL", "timeout": 10},
        "host-one",
        "safe-terminal",
    )
    assert "SENTINEL_REAL_TERMINAL" in str(safe) and not safe.get("error"), safe
    evidence["checks"]["actual_terminal"] = True
    target = workspace / "example.txt"
    target.write_text("original fixture", encoding="utf-8")
    store.save_mission(
        {
            "name": "Host file acceptance",
            "status": "ACTIVE",
            "session_id": "host-one",
            "allowed_directories": [str(workspace)],
            "approved_tools": ["read_file", "write_file"],
        }
    )
    written = call(
        "write_file",
        {"path": str(target), "content": "actual Hermes write"},
        "host-one",
        "actual-write",
    )
    assert target.read_text(encoding="utf-8") == "actual Hermes write", written
    recovery = Recovery(store, workspace)
    point = recovery.checkpoints()[0]
    assert point["status"] == "SEALED", point
    recovery.restore(point["id"], authorized=True)
    assert target.read_text(encoding="utf-8") == "original fixture"
    evidence["checks"]["actual_write_automatic_checkpoint_restore"] = True
    secret = workspace / ".env.synthetic"
    secret.write_text("SYNTHETIC_ONLY_VALUE=never-log-me", encoding="utf-8")
    blocked = call("read_file", {"path": str(secret)}, "host-two", "blocked-secret")
    assert "protected-secrets" in str(blocked) and "never-log-me" not in str(blocked), (
        blocked
    )
    marker = workspace / "disposable-sentinel-marker"
    marker.mkdir()
    (marker / "preserve.txt").write_text("disposable block evidence", encoding="utf-8")
    destructive = call(
        "terminal",
        {"command": "rm -rf disposable-sentinel-marker"},
        "host-two",
        "blocked-destructive",
    )
    assert (
        "destructive-command" in str(destructive) and (marker / "preserve.txt").exists()
    ), destructive
    evidence["checks"]["blocked_secret_and_destructive_dispatch"] = True
    decisions = []

    def deny(command, description, **kwargs):
        decisions.append("deny")
        return "deny"

    def once(command, description, **kwargs):
        decisions.append("once")
        return "once"

    token = set_current_session_key("host-two")
    try:
        set_approval_callback(deny)
        denied_file = workspace / "denied.txt"
        denied = call(
            "terminal",
            {
                "command": f"python -c \"open('{denied_file.as_posix()}','w').write('denied')\""
            },
            "host-two",
            "fixture-deny",
        )
        assert not denied_file.exists() and "BLOCKED" in str(denied), denied
        set_approval_callback(once)
        # Only a harmless terminal echo is allowed after fixture approval.
        allowed = call(
            "terminal",
            {"command": "printf SENTINEL_APPROVED_FIXTURE", "timeout": 10},
            "host-two",
            "fixture-once",
        )
        assert "SENTINEL_APPROVED_FIXTURE" in str(allowed) and not allowed.get(
            "error"
        ), allowed
        assert decisions == ["deny", "once"], decisions
    finally:
        reset_current_session_key(token)
        set_approval_callback(None)
    evidence["checks"]["native_fixture_deny_prevents_body_and_once_executes"] = True
    mission = store.mission_for_session("host-one")
    store.save_mission({**mission, "status": "PAUSED"})
    paused = call("read_file", {"path": str(target)}, "host-one", "paused")
    assert "mission-inactive" in str(paused), paused
    separate = call("read_file", {"path": str(target)}, "host-two", "separate-session")
    assert "original fixture" in str(separate), separate
    evidence["checks"]["mission_pause_and_session_isolation"] = True
    assert "never-log-me" not in str(store.events(limit=1000))
    persisted = Store(root / "state")
    assert len(persisted.events()) >= 20 and len(persisted.sessions()) == 2
    evidence["checks"]["persistence_and_redaction"] = True
    evidence["events"] = persisted.stats()["events"]
    evidence["state"] = str(store.root)
    evidence["plugin_hooks"] = info["hooks"]
    (root / "acceptance.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence))


def run_acceptance(output=None):
    repo = Path(__file__).resolve().parents[1]
    root = (
        Path(output).resolve()
        if output
        else Path(tempfile.mkdtemp(prefix="sentinel-host-parent-")) / "acceptance"
    )
    root.mkdir(parents=True, exist_ok=False)
    (root / "workspace").mkdir()
    home = root / "profile"
    plugin = home / "plugins" / "sentinel"
    plugin.mkdir(parents=True)
    for name in ("__init__.py", "plugin.yaml"):
        shutil.copy2(repo / name, plugin / name)
    shutil.copytree(
        repo / "sentinel",
        plugin / "sentinel",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - sentinel\napprovals:\n  mode: manual\nterminal:\n  backend: local\n",
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("HERMES_", "SENTINEL_"))
        and not any(
            part in key.upper()
            for part in ("API_KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL")
        )
    }
    env.update(
        HERMES_HOME=str(home),
        SENTINEL_HOME=str(root / "state"),
        HERMES_INTERACTIVE="1",
        TERMINAL_ENV="local",
        TERMINAL_CWD=str(root / "workspace"),
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=str(plugin),
    )
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(root)],
        cwd=root / "workspace",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            f"Host acceptance failed; evidence root {root}\n{result.stdout}\n{result.stderr}"
        )
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    summary["evidence_root"] = str(root)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", help="New disposable directory; existing directories rejected"
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.worker:
        worker(options.worker)
    else:
        print(json.dumps(run_acceptance(options.output), indent=2))
