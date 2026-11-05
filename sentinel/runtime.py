"""Official Hermes lifecycle adapter. Never patches the host dispatcher."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .policy import evaluate
from .store import Store
from .recovery import Recovery
from .rules import RuleSet


def data_home():
    return Path(
        os.environ.get(
            "SENTINEL_HOME",
            str(
                Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
                / "sentinel"
            ),
        )
    )


def identity_of(kwargs):
    return {
        key: str(kwargs[key])
        for key in (
            "session_id",
            "agent_id",
            "task_id",
            "turn_id",
            "tool_call_id",
            "api_request_id",
            "mission_id",
        )
        if kwargs.get(key)
    }


class Runtime:
    def __init__(self, store):
        self.store = store
        self.pending = {}
        self.lock = threading.Lock()
        self.started = {}

    def pre_tool(self, tool_name, args, **kwargs):
        # Hermes ignores exceptions raised by hooks. Return an explicit block
        # on Sentinel failures so a storage/policy error cannot silently allow.
        try:
            identity = identity_of(kwargs)
            identity["protected_directories"] = [
                str(self.store.root),
                str(Path(__file__).resolve().parent.parent),
            ]
            mission = self.store.mission_for_session(identity.get("session_id", ""))
            if mission:
                identity["mission_id"] = mission["id"]
            decision = evaluate(tool_name, args, identity, mission)
            custom = RuleSet(self.store.root).evaluate(tool_name, args, identity)
            if custom and decision["decision"] != "BLOCK":
                if custom["decision"] == "BLOCK" or decision["decision"] == "ALLOW":
                    decision = custom
            self.store.append(
                "tool_call_requested", identity, tool_name=tool_name, args=args
            )
            event = {
                "ALLOW": "tool_call_allowed",
                "BLOCK": "tool_call_blocked",
                "APPROVAL_REQUIRED": "approval_required",
            }[decision["decision"]]
            self.store.append(event, identity, tool_name=tool_name, **decision)
            if decision["decision"] == "ALLOW":
                if identity.get("tool_call_id"):
                    with self.lock:
                        self.started[
                            (identity.get("session_id"), identity["tool_call_id"])
                        ] = time.monotonic()
                # Automatic recovery is deliberately restricted to structured
                # writes with a real host call ID and an explicit mission root.
                if (
                    tool_name in {"write_file", "file_write", "apply_patch", "patch"}
                    and identity.get("tool_call_id")
                    and mission
                    and len(mission.get("allowed_directories", [])) == 1
                ):
                    path = args.get("path") or args.get("file_path")
                    if path:
                        recovery = Recovery(
                            self.store, Path(mission["allowed_directories"][0])
                        )
                        checkpoint = recovery.checkpoint(path, identity)
                        with self.lock:
                            self.pending[
                                (identity.get("session_id"), identity["tool_call_id"])
                            ] = (recovery, checkpoint["id"])
                return None
            scope = json.dumps(
                [identity, tool_name, args], sort_keys=True, separators=(",", ":")
            )
            # Bind host permanent/session approval grants to the exact request,
            # including call ID when supplied: never a blanket tool grant.
            key = "sentinel:" + hashlib.sha256(scope.encode()).hexdigest()
            return {
                "action": "block" if decision["decision"] == "BLOCK" else "approve",
                "message": f"Sentinel [{decision['rule']}]: {decision['reason']}",
                "rule_key": key,
            }
        except Exception:
            return {
                "action": "block",
                "message": "Sentinel could not evaluate or persist this operation. Execution blocked; inspect local storage and policy configuration.",
            }

    def post_tool(self, tool_name, args=None, result=None, **kwargs):
        key = (kwargs.get("session_id"), kwargs.get("tool_call_id"))
        with self.lock:
            pending = self.pending.pop(key, None)
            started = self.started.pop(key, None)
        if pending:
            recovery, checkpoint_id = pending
            recovery.seal(checkpoint_id)
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (ValueError, TypeError):
                result = None
        failed = isinstance(result, dict) and bool(
            result.get("error") or result.get("success") is False
        )
        # Tool results may contain arbitrary secret bytes; record only status.
        data = {"tool_name": tool_name}
        if started is not None:
            data["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        self.store.append(
            "tool_execution_failed" if failed else "tool_execution_completed",
            identity_of(kwargs),
            **data,
        )

    def observe(self, event_type, **kwargs):
        identity = identity_of(kwargs)
        # Do not persist prompts, command bodies or arbitrary host objects.
        data = {
            key: kwargs[key]
            for key in (
                "choice",
                "decided_by",
                "surface",
                "pattern_key",
                "duration_ms",
                "status",
                "session_key",
            )
            if key in kwargs
        }
        self.store.append(event_type, identity, **data)


def register(ctx):
    runtime = Runtime(Store(data_home()))
    ctx.register_hook("pre_tool_call", runtime.pre_tool)
    ctx.register_hook("post_tool_call", runtime.post_tool)
    mapping = {
        "on_session_start": "session_started",
        "on_session_end": "session_ended",
        "subagent_start": "subagent_started",
        "subagent_stop": "subagent_stopped",
        "pre_approval_request": "approval_requested",
        "post_approval_response": "approval_decided",
    }
    for hook, event in mapping.items():

        def observer(_event=event, **kwargs):
            runtime.observe(_event, **kwargs)

        ctx.register_hook(hook, observer)
