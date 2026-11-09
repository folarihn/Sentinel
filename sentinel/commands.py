"""Operator commands for chat (/sentinel), the terminal (hermes sentinel) and alerts.

Everything reported here is read from the local journal, missions and alert
settings. Chat commands can only read state or toggle alerts; they cannot
change policy, missions or recovery.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from . import __version__

ALERT_FILE = "alerts.json"
ALERT_RISKS = {"high", "critical"}
_TARGET = re.compile(r"^[a-z][a-z0-9_-]{1,31}(:[^\s]{1,200})?$")


# ---------------------------------------------------------------- formatting
def _n(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _when(value):
    try:
        moment = datetime.fromisoformat(str(value))
        return moment.astimezone().strftime("%b %d %H:%M")
    except (TypeError, ValueError):
        return "time not recorded"


def _mission_state(mission, now=None):
    status = mission.get("status", "DRAFT")
    expiry = mission.get("expires_at")
    if status == "ACTIVE" and expiry:
        try:
            moment = datetime.fromisoformat(str(expiry))
            if moment.timestamp() <= (now or time.time()):
                return "EXPIRED"
        except ValueError:
            return "INVALID EXPIRY"
    return status


def _recent(store, types, limit):
    marks = ",".join("?" for _ in types)
    with store.connect() as db:
        rows = db.execute(
            f"SELECT payload FROM events WHERE event_type IN ({marks}) "
            "ORDER BY seq DESC LIMIT ?",
            [*types, limit],
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


# ---------------------------------------------------------------- alerts
def load_alerts(root):
    try:
        data = json.loads((Path(root) / ALERT_FILE).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                "enabled": bool(data.get("enabled")),
                "target": str(data.get("target") or ""),
            }
    except (OSError, ValueError):
        pass
    return {"enabled": False, "target": ""}


def save_alerts(root, enabled, target=""):
    if enabled and not _TARGET.match(target or ""):
        raise ValueError(
            "Use a delivery target such as telegram (its home channel) or telegram:<chat id>."
        )
    settings = {"enabled": bool(enabled), "target": target if enabled else ""}
    path = Path(root) / ALERT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return settings


def alert_message(tool_name, decision, identity):
    session = identity.get("session_id") or "unattributed session"
    return (
        f"🛡 Sentinel blocked {tool_name}\n"
        f"Reason: {decision.get('reason') or 'Policy decision'}\n"
        f"Rule: {decision.get('rule') or 'not recorded'} · risk {decision.get('risk') or 'unknown'}\n"
        f"Session: {session}\n"
        "The tool did not run. Send /sentinel blocks for recent decisions."
    )


def _default_sender(target, message):
    from tools.send_message_tool import send_message_tool

    result = send_message_tool({"action": "send", "target": target, "message": message})
    data = json.loads(result) if isinstance(result, str) else result
    return bool(isinstance(data, dict) and data.get("success")), (
        data.get("error") if isinstance(data, dict) else None
    )


class Alerts:
    """Sends opt-in block alerts through Hermes' own delivery engine.

    Delivery runs on a background thread so a slow or failing chat platform
    can never delay or change a policy decision. Repeated alerts for the same
    rule and tool are suppressed for a minute, and at most 20 are sent per hour.
    """

    def __init__(self, store, sender=None, clock=time.monotonic):
        self.store = store
        self.sender = sender or _default_sender
        self.clock = clock
        self.lock = threading.Lock()
        self.recent = {}
        self.sent = []

    def _allow(self, key):
        now = self.clock()
        with self.lock:
            self.sent = [t for t in self.sent if now - t < 3600]
            if now - self.recent.get(key, -1e9) < 60 or len(self.sent) >= 20:
                return False
            self.recent[key] = now
            self.sent.append(now)
            return True

    def notify(self, tool_name, decision, identity, wait=False):
        if (
            decision.get("decision") != "BLOCK"
            or decision.get("risk") not in ALERT_RISKS
        ):
            return None
        settings = load_alerts(self.store.root)
        if not settings["enabled"] or not self._allow(
            (decision.get("rule"), tool_name)
        ):
            return None
        message = alert_message(tool_name, decision, identity)

        def deliver():
            try:
                ok, error = self.sender(settings["target"], message)
            except Exception as exc:  # delivery must never affect enforcement
                ok, error = False, type(exc).__name__
            self.store.append(
                "alert.sent" if ok else "alert.failed",
                identity,
                tool_name=tool_name,
                rule=decision.get("rule"),
                target=settings["target"].split(":", 1)[0],
                **({} if ok else {"reason": str(error or "Delivery failed")[:200]}),
            )

        worker = threading.Thread(target=deliver, name="sentinel-alert", daemon=True)
        worker.start()
        if wait:
            worker.join(10)
        return worker


# ---------------------------------------------------------------- chat text
def status_text(store):
    stats = store.stats()
    by = stats.get("by_type", {})
    active = [m for m in store.missions() if _mission_state(m) == "ACTIVE"]
    last = _recent(store, ("tool_call_blocked",), 1)
    alerts = load_alerts(store.root)
    lines = [
        f"🛡 Sentinel {__version__} is active in this Hermes process.",
        (
            f"Journal: {_n(stats['events'], 'event')} · "
            f"{by.get('tool_call_blocked', 0)} blocked · "
            f"{by.get('approval_required', 0)} needed approval · "
            f"{_n(stats.get('sessions', 0), 'session')}"
        ),
        "Active missions: "
        + (", ".join(m.get("name", "unnamed") for m in active) or "none"),
    ]
    if last:
        event = last[0]
        lines.append(
            f"Last block: {_when(event.get('timestamp'))} · {event.get('tool_name', 'tool')} · "
            f"{event.get('reason', 'policy decision')} ({event.get('rule', 'no rule id')})"
        )
    else:
        lines.append("Last block: none recorded")
    lines.append(
        "Alerts: " + (f"on → {alerts['target']}" if alerts["enabled"] else "off")
    )
    from .agent import heartbeat_text

    lines.append(heartbeat_text(store.root))
    return "\n".join(lines)


def blocks_text(store, limit=5):
    events = _recent(store, ("tool_call_blocked", "approval_required"), limit)
    if not events:
        return "No blocked or approval-required tool calls are recorded."
    lines = [
        "Most recent intervention:"
        if len(events) == 1
        else f"Last {len(events)} interventions (newest first):"
    ]
    for event in events:
        kind = (
            "Blocked"
            if event.get("event_type") == "tool_call_blocked"
            else "Needed approval"
        )
        lines.append(
            f"• {_when(event.get('timestamp'))} {kind}: {event.get('tool_name', 'tool')} — "
            f"{event.get('reason', 'policy decision')} [{event.get('rule', 'no rule id')}]"
        )
    return "\n".join(lines)


def missions_text(store):
    missions = store.missions()
    if not missions:
        return (
            "No missions are configured. Create one from the dashboard's Missions view."
        )
    lines = ["Missions:"]
    for mission in missions:
        tools = ", ".join(mission.get("approved_tools") or []) or "no tools"
        lines.append(
            f"• {mission.get('name', 'unnamed')} — {_mission_state(mission)} · "
            f"session {mission.get('session_id') or 'unassigned'} · tools: {tools}"
        )
    return "\n".join(lines)


HELP = (
    "Sentinel commands:\n"
    "/sentinel status — protection summary\n"
    "/sentinel blocks [n] — recent blocked or approval-required calls\n"
    "/sentinel missions — mission scopes and states\n"
    "/sentinel digest [hours] — plain summary of recent activity (default 24)\n"
    "/sentinel alerts on telegram — alert this platform's home channel on high-risk blocks\n"
    "/sentinel alerts off — stop alerts\n"
    "Policy, missions and recovery can only be changed from the local dashboard."
)


def chat_command(store, raw_args):
    parts = (raw_args or "").split()
    action = parts[0].lower() if parts else "status"
    try:
        if action == "status":
            return status_text(store)
        if action == "blocks":
            count = int(parts[1]) if len(parts) > 1 else 5
            return blocks_text(store, max(1, min(count, 20)))
        if action == "missions":
            return missions_text(store)
        if action == "digest":
            from .agent import digest_text

            hours = int(parts[1]) if len(parts) > 1 else 24
            return digest_text(store, max(1, min(hours, 24 * 30)))
        if action == "alerts":
            choice = parts[1].lower() if len(parts) > 1 else ""
            if choice == "off":
                save_alerts(store.root, False)
                return "Sentinel alerts are off."
            if choice == "on":
                if len(parts) > 3:
                    raise ValueError(
                        "Use a delivery target such as telegram (its home channel) or telegram:<chat id>."
                    )
                target = parts[2] if len(parts) > 2 else "telegram"
                save_alerts(store.root, True, target)
                return (
                    f"Sentinel alerts are on → {target}. High and critical risk blocks "
                    "will be sent there. Alerts never change what is allowed."
                )
            settings = load_alerts(store.root)
            return "Alerts: " + (
                f"on → {settings['target']}" if settings["enabled"] else "off"
            )
    except ValueError as exc:
        return str(exc)
    return HELP


# ---------------------------------------------------------------- terminal
def doctor(home, check_hermes=True):
    """Return (ok, lines) describing whether Sentinel is set up correctly."""
    checks = []

    def add(ok, label, detail):
        checks.append((ok, f"{'✓' if ok else '✗'} {label}: {detail}"))

    add(
        sys.version_info >= (3, 11),
        "Python",
        sys.version.split()[0] + " (3.11+ required)",
    )
    add(True, "Sentinel version", __version__)
    home = Path(home)
    source = (
        "SENTINEL_HOME"
        if os.environ.get("SENTINEL_HOME")
        else ("HERMES_HOME" if os.environ.get("HERMES_HOME") else "default ~/.hermes")
    )
    add(True, "State folder", f"{home} (from {source})")
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, prefix=".doctor-", delete=True):
            pass
        add(True, "State folder writable", "yes")
    except OSError as exc:
        add(False, "State folder writable", f"no ({type(exc).__name__})")
    try:
        from .store import Store

        store = Store(home)
        stats = store.stats()
        last = _recent(store, tuple(stats.get("by_type", {}) or ("none",)), 1)
        add(
            True,
            "Journal",
            f"{_n(stats['events'], 'event')}, {_n(stats.get('sessions', 0), 'session')}, "
            f"last event {_when(last[0].get('timestamp')) if last else 'none yet'}",
        )
        alerts = load_alerts(home)
        add(True, "Alerts", f"on → {alerts['target']}" if alerts["enabled"] else "off")
        from .agent import Breaker, heartbeats

        live = [h for h in heartbeats(home) if h["live"] and h["role"] != "command"]
        add(
            True,
            "Plugin heartbeat",
            ", ".join(
                f"{h['role']} pid {h['pid']} {h['age_seconds']} s ago" for h in live[:3]
            )
            or "none yet (normal until the gateway restarts with Sentinel enabled)",
        )
        paused = Breaker(home)._load()
        add(True, "Paused sessions", ", ".join(paused) if paused else "none")
    except Exception as exc:
        add(False, "Journal", f"cannot be opened ({type(exc).__name__}: {exc})")
    if check_hermes:
        try:
            from hermes_cli.plugins import discover_plugins, get_plugin_manager

            discover_plugins(force=True)
            entry = next(
                (
                    p
                    for p in get_plugin_manager().list_plugins()
                    if p.get("name") == "sentinel"
                ),
                None,
            )
            if entry is None:
                add(False, "Hermes plugin", "not installed in this Hermes profile")
            elif not entry.get("enabled"):
                add(
                    False,
                    "Hermes plugin",
                    "installed but disabled; run: hermes plugins enable sentinel",
                )
            elif entry.get("error"):
                add(False, "Hermes plugin", f"failed to load: {entry['error']}")
            else:
                add(
                    True,
                    "Hermes plugin",
                    f"enabled, {entry.get('hooks', 0)} hooks, version {entry.get('version')}",
                )
        except ImportError:
            add(False, "Hermes plugin", "Hermes is not importable from this Python")
    ok = all(passed for passed, _ in checks)
    lines = [line for _, line in checks]
    lines.append(
        "Everything looks right. Restart the Hermes gateway if you just installed or updated Sentinel."
        if ok
        else "Fix the ✗ items above, then run this check again."
    )
    return ok, lines


def login_link(port, token):
    return f"http://127.0.0.1:{port}/#login={token}"


def run_dashboard(home, workspace, port, token=None, out=print):
    from .server import create_server

    server = create_server(
        home, workspace, port, token or os.environ.get("SENTINEL_TOKEN")
    )
    real_port = server.server_port
    out("Sentinel dashboard is running on this machine only.")
    out(
        f"Open this login link in a browser on this machine: {login_link(real_port, server.auth_token)}"
    )
    out(
        f"On a VPS, first run on your own computer: ssh -L {real_port}:127.0.0.1:{real_port} "
        "user@your-server, then open the same link there."
    )
    out(
        "Keep the link private; it contains this session's access token. Press Ctrl+C to stop."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def setup_cli(parser):
    sub = parser.add_subparsers(dest="sentinel_command")
    sub.add_parser(
        "doctor", help="Check that Sentinel is installed and recording correctly"
    )
    dash = sub.add_parser(
        "dashboard", help="Start the local dashboard and print a login link"
    )
    dash.add_argument("--workspace", type=Path, default=Path.cwd())
    dash.add_argument("--port", type=int, default=8765)
    sub.add_parser("status", help="Show the protection summary")
    blocks = sub.add_parser(
        "blocks", help="Show recent blocked or approval-required calls"
    )
    blocks.add_argument("count", nargs="?", type=int, default=5)
    sub.add_parser("missions", help="Show mission scopes and states")
    digest = sub.add_parser("digest", help="Plain summary of recent activity")
    digest.add_argument("hours", nargs="?", type=int, default=24)
    resume = sub.add_parser(
        "resume", help="Un-pause sessions stopped by the runaway breaker"
    )
    resume.add_argument(
        "session", nargs="?", help="Session to resume (default: all paused sessions)"
    )


def handle_cli(args, home=None):
    from .runtime import data_home
    from .store import Store

    home = home or data_home()
    command = getattr(args, "sentinel_command", None) or "doctor"
    if command == "doctor":
        ok, lines = doctor(home)
        print("\n".join(lines))
        return 0 if ok else 1
    if command == "dashboard":
        run_dashboard(home, args.workspace, args.port)
        return 0
    store = Store(home)
    if command == "status":
        print(status_text(store))
    elif command == "blocks":
        print(blocks_text(store, max(1, min(args.count, 50))))
    elif command == "missions":
        print(missions_text(store))
    elif command == "digest":
        from .agent import digest_text

        print(digest_text(store, max(1, args.hours)))
    elif command == "resume":
        from .agent import Breaker

        cleared = Breaker(home).resume(args.session)
        if cleared:
            store.append(
                "breaker.resumed", {}, sessions=cleared, actor="local-operator"
            )
        print(
            "Resumed: " + ", ".join(cleared)
            if cleared
            else "No paused sessions matched."
        )
    return 0
