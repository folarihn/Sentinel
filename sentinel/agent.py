"""Agent-facing tools, the runaway circuit breaker, plugin heartbeats and the digest.

Agent tools are read-only or create backups only. The agent can ask what is
allowed and record a restore point; it can never loosen its own policy.
"""

from __future__ import annotations

import atexit
import json
import os
import socket
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__

MANDATORY = [
    "Destructive shell operations",
    "Secret and sensitive paths",
    "Privilege escalation",
    "Repository mutations",
    "Deployment and financial activity",
    "Mission directory and tool scope",
]
TOOL_NAMES = ("sentinel_preflight", "sentinel_scope", "sentinel_checkpoint")


# ------------------------------------------------------------ agent tools
PREFLIGHT_SCHEMA = {
    "name": "sentinel_preflight",
    "description": (
        "Ask Sentinel whether a tool call would be allowed BEFORE making it, and why. "
        "Use this when unsure whether a command, file path or action is permitted, so you "
        "can choose an allowed approach instead of retrying a blocked one. This is a dry run: "
        "nothing executes and no approval is granted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "The tool you intend to call, e.g. terminal or write_file.",
            },
            "arguments": {
                "type": "object",
                "description": "The exact arguments you intend to pass.",
            },
        },
        "required": ["tool_name", "arguments"],
    },
}
SCOPE_SCHEMA = {
    "name": "sentinel_scope",
    "description": (
        "Show the limits Sentinel enforces for this session: mission folders, approved and "
        "restricted tools, network domains, expiry, and the always-on protections. Use it to "
        "plan work that stays inside your authority."
    ),
    "parameters": {"type": "object", "properties": {}},
}
CHECKPOINT_SCHEMA = {
    "name": "sentinel_checkpoint",
    "description": (
        "Save a restore point of one workspace file before a risky edit. The operator can "
        "restore it later from the Sentinel dashboard. It only backs the file up; it does not "
        "change the file or grant any permission."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path of the file to back up."}
        },
        "required": ["path"],
    },
}


def _identity(kwargs, args=None):
    keys = ("session_id", "task_id", "agent_id", "turn_id")
    found = {k: str(kwargs[k]) for k in keys if kwargs.get(k)}
    if args and args.get("session_id") and "session_id" not in found:
        found["session_id"] = str(args["session_id"])
    return found


class AgentTools:
    def __init__(self, runtime):
        self.runtime = runtime

    def preflight(self, args, **kwargs):
        tool = str((args or {}).get("tool_name") or "").strip()
        call = (args or {}).get("arguments") or {}
        if not tool or not isinstance(call, dict):
            return json.dumps({"error": "Provide tool_name and an arguments object."})
        identity = _identity(kwargs, args)
        decision = self.runtime.decide(tool, call, identity)
        verdict = {
            "ALLOW": "allowed",
            "BLOCK": "blocked",
            "APPROVAL_REQUIRED": "needs the operator's approval",
        }[decision["decision"]]
        return json.dumps(
            {
                "decision": decision["decision"],
                "summary": f"{tool} would be {verdict}.",
                "rule": decision.get("rule"),
                "reason": decision.get("reason"),
                "risk": decision.get("risk"),
                "dry_run": True,
            }
        )

    def scope(self, args=None, **kwargs):
        identity = _identity(kwargs, args)
        mission = self.runtime.store.mission_for_session(identity.get("session_id", ""))
        body = {"mandatory_protections": MANDATORY, "mission": None}
        if mission:
            body["mission"] = {
                key: mission.get(key)
                for key in (
                    "name",
                    "status",
                    "allowed_directories",
                    "restricted_directories",
                    "approved_tools",
                    "restricted_tools",
                    "allowed_domains",
                    "expires_at",
                )
            }
        body["note"] = (
            "Mission limits narrow what you may do; they never relax mandatory protections."
            if mission
            else "No mission is assigned to this session; mandatory protections still apply."
        )
        return json.dumps(body)

    def checkpoint(self, args, **kwargs):
        from .recovery import Recovery

        path = str((args or {}).get("path") or "").strip()
        if not path:
            return json.dumps({"error": "Provide the path of the file to back up."})
        identity = _identity(kwargs, args)
        mission = self.runtime.store.mission_for_session(identity.get("session_id", ""))
        roots = (mission or {}).get("allowed_directories") or []
        workspace = Path(roots[0]) if len(roots) == 1 else Path.cwd()
        try:
            record = Recovery(self.runtime.store, workspace).checkpoint(path, identity)
        except (ValueError, PermissionError, FileNotFoundError, OSError) as exc:
            return json.dumps({"error": f"Checkpoint not created: {exc}"})
        return json.dumps(
            {
                "checkpoint_id": record["id"],
                "status": record.get("status", "OPEN"),
                "note": "Restore point saved. The operator can seal and restore it from the Sentinel dashboard.",
            }
        )


def register_tools(ctx, runtime):
    if not hasattr(ctx, "register_tool"):
        return []
    tools = AgentTools(runtime)
    specs = (
        (PREFLIGHT_SCHEMA, tools.preflight, "🛡"),
        (SCOPE_SCHEMA, tools.scope, "🧭"),
        (CHECKPOINT_SCHEMA, tools.checkpoint, "💾"),
    )
    for schema, handler, emoji in specs:
        ctx.register_tool(
            name=schema["name"],
            toolset="sentinel",
            schema=schema,
            handler=handler,
            description=schema["description"].split(".")[0],
            emoji=emoji,
        )
    return [schema["name"] for schema, _, _ in specs]


# ------------------------------------------------------------ circuit breaker
BREAKER_FILE = "breakers.json"


class Breaker:
    """Pauses a session that loops on blocked actions or fires an unusual burst.

    Trips when the same tool is blocked by the same rule 3 times within 5
    minutes, or when a session requests more than 40 tool calls within 60
    seconds. A tripped session is paused for 10 minutes; the pause is shared
    through the state folder so `hermes sentinel resume` can clear it.
    """

    def __init__(
        self,
        root,
        clock=time.time,
        burst=40,
        burst_window=60,
        repeats=3,
        repeat_window=300,
        cooldown=600,
    ):
        self.path = Path(root) / BREAKER_FILE
        self.clock = clock
        self.burst, self.burst_window = burst, burst_window
        self.repeats, self.repeat_window, self.cooldown = (
            repeats,
            repeat_window,
            cooldown,
        )
        self.lock = threading.Lock()
        self.calls = defaultdict(deque)
        self.blocks = defaultdict(deque)

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    def paused(self, session):
        entry = self._load().get(session or "unattributed")
        if not entry:
            return None
        remaining = float(entry.get("until", 0)) - self.clock()
        return {**entry, "remaining": int(remaining)} if remaining > 0 else None

    def _trip(self, session, reason):
        until = self.clock() + self.cooldown
        with self.lock:
            data = self._load()
            data[session] = {"until": until, "reason": reason}
            self._save(data)
            self.calls.pop(session, None)
            self.blocks.pop(session, None)
        return {"session": session, "reason": reason, "minutes": self.cooldown // 60}

    def record(self, session, tool, decision):
        """Record a call; return a trip dict if this call trips the breaker."""
        session = session or "unattributed"
        now = self.clock()
        with self.lock:
            calls = self.calls[session]
            calls.append(now)
            while calls and now - calls[0] > self.burst_window:
                calls.popleft()
            burst = len(calls) > self.burst
            repeated = False
            if decision.get("decision") == "BLOCK":
                key = (tool, decision.get("rule"))
                blocks = self.blocks[session]
                blocks.append((now, key))
                while blocks and now - blocks[0][0] > self.repeat_window:
                    blocks.popleft()
                repeated = sum(1 for _, k in blocks if k == key) >= self.repeats
        if repeated:
            return self._trip(
                session,
                f"{tool} was blocked by {decision.get('rule')} {self.repeats} times within "
                f"{self.repeat_window // 60} minutes",
            )
        if burst:
            return self._trip(
                session,
                f"more than {self.burst} tool calls within {self.burst_window} seconds",
            )
        return None

    def resume(self, session=None):
        with self.lock:
            data = self._load()
            cleared = (
                list(data) if session is None else [s for s in data if s == session]
            )
            for key in cleared:
                data.pop(key, None)
            self._save(data)
        return cleared


# ------------------------------------------------------------ heartbeat
HEARTBEAT_DIR = "heartbeats"


def process_role(argv=None):
    words = [w.lower() for w in (argv if argv is not None else sys.argv)]
    joined = " ".join(words)
    if "gateway" in joined:
        return "gateway"
    if len(words) > 1 and words[1] in {
        "sentinel",
        "plugins",
        "tools",
        "config",
        "doctor",
        "update",
    }:
        return "command"
    return "agent"


class Heartbeat:
    """Writes a small liveness record for this process while the plugin is loaded."""

    def __init__(self, root, interval=30, role=None, clock=time.time):
        self.dir = Path(root) / HEARTBEAT_DIR
        self.interval = interval
        self.role = role or process_role()
        self.clock = clock
        self.started = clock()
        self.name = f"{socket.gethostname()}-{os.getpid()}.json"
        self.thread = None
        self.last_activity = None

    def beat(self, activity=False):
        if activity:
            self.last_activity = self.clock()
            # Tool calls can be frequent; refresh the file at most every 5 seconds.
            if self.clock() - getattr(self, "_written", 0) < 5:
                return
        self._written = self.clock()
        record = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "role": self.role,
            "version": __version__,
            "started": self.started,
            "beat": self.clock(),
            "last_activity": self.last_activity,
        }
        try:
            self.dir.mkdir(exist_ok=True)
            temp = self.dir / (self.name + ".tmp")
            temp.write_text(json.dumps(record), encoding="utf-8")
            os.replace(temp, self.dir / self.name)
        except OSError:
            pass

    def start(self):
        if self.thread or self.role == "command":
            return
        self.beat()

        def loop():
            while True:
                time.sleep(self.interval)
                self.beat()

        self.thread = threading.Thread(
            target=loop, name="sentinel-heartbeat", daemon=True
        )
        self.thread.start()
        atexit.register(self.stop)

    def stop(self):
        """Remove this process's record on clean exit so it never looks live afterwards."""
        try:
            (self.dir / self.name).unlink()
        except OSError:
            pass


def heartbeats(root, now=None, live_window=120):
    now = now or time.time()
    folder = Path(root) / HEARTBEAT_DIR
    found = []
    for item in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        age = now - float(data.get("beat", 0))
        if age > 86400:
            try:
                item.unlink()
            except OSError:
                pass
            continue
        activity = data.get("last_activity")
        found.append(
            {
                "role": data.get("role", "agent"),
                "pid": data.get("pid"),
                "host": data.get("host"),
                "version": data.get("version"),
                "age_seconds": int(age),
                "live": age <= live_window,
                "last_activity_seconds": int(now - activity) if activity else None,
            }
        )
    return sorted(found, key=lambda h: h["age_seconds"])


def heartbeat_text(root):
    live = [h for h in heartbeats(root) if h["live"]]
    if not live:
        return "Plugin heartbeat: none in the last 2 minutes (restart the gateway if Sentinel should be running)"
    parts = [f"{h['role']} pid {h['pid']} {h['age_seconds']} s ago" for h in live[:3]]
    return "Plugin heartbeat: " + ", ".join(parts)


# ------------------------------------------------------------ digest
def digest_text(store, hours=24, now=None):
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).isoformat()
    with store.connect() as db:
        rows = db.execute(
            "SELECT payload FROM events WHERE timestamp >= ? ORDER BY seq", (since,)
        ).fetchall()
    events = [json.loads(r["payload"]) for r in rows]
    if not events:
        return f"Nothing was recorded in the last {hours} hours."
    kinds = Counter(e.get("event_type") for e in events)
    tools = Counter(
        e.get("tool_name")
        for e in events
        if e.get("event_type") == "tool_call_requested"
    )
    rules = Counter(
        e.get("rule") for e in events if e.get("event_type") == "tool_call_blocked"
    )
    sessions = {e.get("session_id") for e in events if e.get("session_id")}
    lines = [f"🛡 Sentinel digest — last {hours} hours"]
    lines.append(
        f"Tool calls: {kinds['tool_call_requested']} requested · {kinds['tool_call_allowed']} allowed · "
        f"{kinds['tool_call_blocked']} blocked · {kinds['approval_required']} needed approval · "
        f"{kinds['tool_execution_failed']} failed"
    )
    lines.append(f"Sessions active: {len(sessions)}")
    if tools:
        lines.append(
            "Most used: " + ", ".join(f"{t} ×{n}" for t, n in tools.most_common(4))
        )
    if rules:
        lines.append(
            "Blocks by rule: " + ", ".join(f"{r} ×{n}" for r, n in rules.most_common(4))
        )
    recovery = kinds["checkpoint.created"] + kinds["recovery.completed"]
    if recovery:
        lines.append(
            f"Recovery: {kinds['checkpoint.created']} checkpoints, {kinds['recovery.completed']} restores"
        )
    attention = []
    if kinds["breaker.tripped"]:
        attention.append(f"{kinds['breaker.tripped']} runaway pause(s)")
    critical = sum(
        1
        for e in events
        if e.get("event_type") == "tool_call_blocked" and e.get("risk") == "critical"
    )
    if critical:
        attention.append(f"{critical} critical block(s)")
    if kinds["alert.failed"]:
        attention.append(f"{kinds['alert.failed']} alert(s) failed to deliver")
    lines.append(
        "Needs attention: " + (", ".join(attention) if attention else "nothing")
    )
    return "\n".join(lines)
