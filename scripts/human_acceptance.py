"""Genuine human decisions through the public native Hermes approval callback.

No model traffic, preselected choices, primary profile changes or credentials.
An operator must relay an actual owner's answer to the nonce-bound decision file.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def validate_decision(payload, pending, current_time=None):
    """Parse an exact nonce-bound, unexpired, deliberately narrow decision."""
    current_time = current_time or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        raise ValueError("Decision must be an object")
    if payload.get("nonce") != pending["nonce"]:
        raise ValueError("Decision nonce does not match this operation")
    expiry = datetime.fromisoformat(pending["expires_at"])
    if expiry.tzinfo is None or current_time >= expiry:
        raise ValueError("Approval request expired")
    if payload.get("choice") not in {"deny", "once"}:
        raise ValueError("Only deny or once decisions are accepted")
    if payload.get("actor") != "owner-via-chat":
        raise ValueError("Decision must identify the owner-via-chat actor")
    return payload["choice"]


def atomic_json(path, data):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def summarize_decisions(requests, effects):
    """Separate genuine human input from whether both requested outcomes occurred.

    One operation can pass multiple native checkpoints. Never interpret an
    unexpected count or the owner's choice as evidence of a fabricated answer.
    """
    genuine = bool(requests) and all(
        p.get("actor") == "owner-via-chat" for p in requests
    )
    approvals = any(p.get("decision") == "once" for p in requests)
    denials = any(p.get("decision") == "deny" for p in requests)
    return {
        "genuine_owner_decisions_received": genuine,
        "human_approval_with_tool_effect_verified": genuine
        and approvals
        and any(e["marker_content_valid"] for e in effects),
        "human_rejection_verified": genuine
        and denials
        and any(not e["marker_created"] for e in effects),
        "both_human_outcomes_verified": genuine
        and approvals
        and denials
        and any(e["marker_content_valid"] for e in effects)
        and any(not e["marker_created"] for e in effects),
    }


class HumanBridge:
    def __init__(self, root, timeout=180):
        self.root = Path(root)
        self.timeout = min(max(float(timeout), 0), 180)
        self.operation = None
        self.requests = []

    def __call__(self, command, description, **kwargs):
        del kwargs
        if not self.operation:
            return "deny"
        index = len(self.requests) + 1
        now = datetime.now(timezone.utc)
        operation = dict(self.operation)
        pending = {
            "index": index,
            "nonce": uuid.uuid4().hex,
            "operation": operation,
            "operation_hash": hashlib.sha256(
                json.dumps(operation, sort_keys=True).encode()
            ).hexdigest(),
            "native_request": str(command),
            "native_reason": str(description),
            "requested_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.timeout)).isoformat(),
            "allowed_choices": ["deny", "once"],
            "status": "PENDING",
            "transport": "native Hermes callback; actual owner answer relayed through local chat bridge",
        }
        self.requests.append(pending)
        atomic_json(self.root / f"pending-{index}.json", pending)
        print(json.dumps({"pending_request": index}), flush=True)
        deadline = time.monotonic() + self.timeout
        decision_path = self.root / f"decision-{index}.json"
        choice = "deny"
        actor = "timeout"
        while time.monotonic() < deadline:
            if decision_path.exists():
                try:
                    payload = json.loads(decision_path.read_text(encoding="utf-8"))
                    choice = validate_decision(payload, pending)
                    actor = payload["actor"]
                except (ValueError, KeyError, TypeError):
                    actor = "invalid-decision-fail-closed"
                break
            time.sleep(0.25)
        pending.update(
            status="DECIDED",
            decision=choice,
            actor=actor,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        atomic_json(self.root / f"outcome-{index}.json", pending)
        return choice


def worker(root):
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from model_tools import handle_function_call
    from tools.approval import reset_current_session_key, set_current_session_key
    from tools.terminal_tool import set_approval_callback
    from sentinel.store import Store

    root = Path(root)
    discover_plugins(force=True)
    info = next(
        p for p in get_plugin_manager().list_plugins() if p["name"] == "sentinel"
    )
    assert info["enabled"] and not info["error"], "Sentinel did not load"
    bridge = HumanBridge(root)
    markers = [
        root / "workspace" / "first-marker.txt",
        root / "workspace" / "second-marker.txt",
    ]
    session = "sentinel-human-acceptance"
    token = set_current_session_key(session)
    set_approval_callback(bridge)
    observed = []
    try:
        for index, marker in enumerate(markers, 1):
            # Only a synthetic new-file write, never an external or real-data action.
            command = f"python -c \"open('{marker.as_posix()}','w').write('SENTINEL_HUMAN_ACCEPTANCE')\""
            bridge.operation = {
                "tool_name": "terminal",
                "args": {"command": command, "timeout": 15},
                "session_id": session,
                "tool_call_id": f"human-{index}",
            }
            result = handle_function_call(
                "terminal",
                bridge.operation["args"],
                session_id=session,
                task_id=session,
                tool_call_id=f"human-{index}",
            )
            del result
            observed.append(
                {
                    "index": index,
                    "marker_created": marker.exists(),
                    "marker_content_valid": marker.exists()
                    and marker.read_text(encoding="utf-8")
                    == "SENTINEL_HUMAN_ACCEPTANCE",
                }
            )
    finally:
        set_approval_callback(None)
        reset_current_session_key(token)
    actual = [
        {
            "index": p["index"],
            "decision": p.get("decision"),
            "actor": p.get("actor"),
            "operation_hash": p["operation_hash"],
        }
        for p in bridge.requests
    ]
    metrics = summarize_decisions(actual, observed)
    summary = {
        "mode": "genuine-human-native-callback-bridge",
        "live_model": False,
        "predetermined_decisions": False,
        "personal_profile_modified": False,
        "actual_decisions": actual,
        "tool_effects": observed,
        **metrics,
        "event_count": Store(root / "state").stats()["events"],
    }
    atomic_json(root / "human-acceptance.json", summary)
    print(json.dumps({"completed": True, **metrics}), flush=True)


def run(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "workspace").mkdir()
    home = root / "profile"
    plugin = home / "plugins" / "sentinel"
    plugin.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
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
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HERMES_", "SENTINEL_"))
        and not any(
            x in k.upper()
            for x in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "YOLO")
        )
    }
    env.update(
        HERMES_HOME=str(home),
        SENTINEL_HOME=str(root / "state"),
        HERMES_INTERACTIVE="1",
        TERMINAL_ENV="local",
        TERMINAL_CWD=str(root / "workspace"),
        PYTHONPATH=str(plugin),
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.call(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(root)],
        cwd=root / "workspace",
        env=env,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Required NEW disposable directory")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.worker:
        worker(options.worker)
    elif options.output:
        raise SystemExit(run(options.output))
    else:
        parser.error("--output is required")
