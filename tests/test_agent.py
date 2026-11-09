import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from sentinel.agent import (
    AgentTools,
    Breaker,
    Heartbeat,
    digest_text,
    heartbeats,
    process_role,
    register_tools,
)
from sentinel.commands import chat_command
from sentinel.runtime import Runtime
from sentinel.store import Store


def runtime_in(folder):
    store = Store(Path(folder) / "state")
    return Runtime(store), store


class AgentToolTests(unittest.TestCase):
    def test_preflight_matches_enforcement_and_records_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            tools = AgentTools(runtime)
            answer = json.loads(
                tools.preflight(
                    {"tool_name": "terminal", "arguments": {"command": "rm -rf /"}},
                    session_id="s",
                )
            )
            self.assertEqual(answer["decision"], "BLOCK")
            self.assertEqual(answer["rule"], "destructive-command")
            self.assertTrue(answer["dry_run"])
            self.assertEqual(store.events(), [])
            enforced = runtime.pre_tool(
                "terminal", {"command": "rm -rf /"}, session_id="s"
            )
            self.assertEqual(enforced["action"], "block")
            self.assertIn("error", json.loads(tools.preflight({"tool_name": ""})))

    def test_scope_reports_mission_and_mandatory_protections(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            tools = AgentTools(runtime)
            empty = json.loads(tools.scope({}, session_id="s"))
            self.assertIsNone(empty["mission"])
            self.assertIn("Secret and sensitive paths", empty["mandatory_protections"])
            store.save_mission(
                {
                    "name": "Docs",
                    "status": "ACTIVE",
                    "session_id": "s",
                    "allowed_directories": [folder],
                    "approved_tools": ["read_file"],
                }
            )
            scoped = json.loads(tools.scope({}, session_id="s"))
            self.assertEqual(scoped["mission"]["name"], "Docs")
            self.assertEqual(scoped["mission"]["approved_tools"], ["read_file"])

    def test_checkpoint_backs_up_a_workspace_file_only(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            work = Path(folder) / "work"
            work.mkdir()
            (work / "notes.txt").write_text("original", encoding="utf-8")
            store.save_mission(
                {
                    "name": "Edit",
                    "status": "ACTIVE",
                    "session_id": "s",
                    "allowed_directories": [str(work)],
                    "approved_tools": ["write_file"],
                }
            )
            tools = AgentTools(runtime)
            made = json.loads(
                tools.checkpoint({"path": str(work / "notes.txt")}, session_id="s")
            )
            self.assertIn("checkpoint_id", made)
            self.assertEqual(
                (work / "notes.txt").read_text(encoding="utf-8"), "original"
            )
            outside = json.loads(
                tools.checkpoint(
                    {"path": str(Path(folder) / "other.txt")}, session_id="s"
                )
            )
            self.assertIn("error", outside)

    def test_sentinel_tools_are_allowed_and_journaled(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            self.assertIsNone(runtime.pre_tool("sentinel_scope", {}, session_id="s"))
            self.assertEqual(store.events()[-1]["rule"], "sentinel-tool")

    def test_register_tools_adds_three_tools_to_one_toolset(self):
        added = []

        class Ctx:
            def register_tool(self, **kw):
                added.append((kw["name"], kw["toolset"]))

        with tempfile.TemporaryDirectory() as folder:
            runtime, _ = runtime_in(folder)
            register_tools(Ctx(), runtime)
            self.assertEqual(
                sorted(added),
                [
                    ("sentinel_checkpoint", "sentinel"),
                    ("sentinel_preflight", "sentinel"),
                    ("sentinel_scope", "sentinel"),
                ],
            )
            self.assertEqual(register_tools(object(), runtime), [])


class BreakerTests(unittest.TestCase):
    def test_repeated_blocks_pause_the_session_until_resumed(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            runtime.breaker = Breaker(store.root)
            notified = []
            runtime.alerts = mock.Mock(notify=lambda *a, **k: notified.append(a))
            for _ in range(3):
                runtime.pre_tool("terminal", {"command": "rm -rf /"}, session_id="loop")
            self.assertTrue(
                any(e["event_type"] == "breaker.tripped" for e in store.events())
            )
            self.assertTrue(any(a[1]["rule"] == "runaway-breaker" for a in notified))
            blocked = runtime.pre_tool(
                "terminal", {"command": "git status"}, session_id="loop"
            )
            self.assertEqual(blocked["action"], "block")
            self.assertIn("runaway-breaker", blocked["message"])
            self.assertIsNone(
                runtime.pre_tool(
                    "terminal", {"command": "git status"}, session_id="other"
                )
            )
            self.assertIsNotNone(Breaker(store.root).paused("loop"))
            self.assertEqual(Breaker(store.root).resume("loop"), ["loop"])
            self.assertIsNone(
                runtime.pre_tool(
                    "terminal", {"command": "git status"}, session_id="loop"
                )
            )

    def test_burst_trips_and_pause_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            clock = [1000.0]
            breaker = Breaker(folder, clock=lambda: clock[0], burst=5, cooldown=60)
            allow = {"decision": "ALLOW"}
            trips = [breaker.record("s", "read_file", allow) for _ in range(6)]
            self.assertIsNotNone(trips[-1])
            self.assertIn("more than 5 tool calls", trips[-1]["reason"])
            self.assertIsNotNone(breaker.paused("s"))
            clock[0] += 61
            self.assertIsNone(breaker.paused("s"))

    def test_preflight_reports_a_paused_session(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            runtime.breaker = Breaker(store.root)
            runtime.breaker._trip("s", "a test reason")
            answer = json.loads(
                AgentTools(runtime).preflight(
                    {"tool_name": "read_file", "arguments": {"path": "x"}},
                    session_id="s",
                )
            )
            self.assertEqual(answer["rule"], "runaway-breaker")


class HeartbeatAndDigestTests(unittest.TestCase):
    def test_heartbeat_records_live_processes_and_prunes_old_files(self):
        with tempfile.TemporaryDirectory() as folder:
            beat = Heartbeat(folder, role="gateway")
            beat.beat(activity=True)
            live = heartbeats(folder)
            self.assertEqual(live[0]["role"], "gateway")
            self.assertTrue(live[0]["live"])
            self.assertEqual(live[0]["pid"], os.getpid())
            old = Path(folder) / "heartbeats" / "old-1.json"
            old.write_text(json.dumps({"beat": time.time() - 90000}), encoding="utf-8")
            heartbeats(folder)
            self.assertFalse(old.exists())
            self.assertIn("gateway pid", chat_command(Store(Path(folder)), "status"))

    def test_process_role_and_command_processes_do_not_beat(self):
        self.assertEqual(process_role(["hermes", "gateway", "run"]), "gateway")
        self.assertEqual(
            process_role(["python", "/opt/hermes/stage2-gateway-runner.py"]), "gateway"
        )
        self.assertEqual(process_role(["hermes", "sentinel", "doctor"]), "command")
        self.assertEqual(process_role(["hermes"]), "agent")
        with tempfile.TemporaryDirectory() as folder:
            Heartbeat(folder, role="command").start()
            self.assertEqual(heartbeats(folder), [])

    def test_digest_summarises_recent_recorded_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, store = runtime_in(folder)
            self.assertIn("Nothing was recorded", digest_text(store))
            runtime.pre_tool("terminal", {"command": "git status"}, session_id="s")
            runtime.pre_tool("read_file", {"path": ".env"}, session_id="s")
            text = digest_text(store, now=datetime.now(timezone.utc))
            self.assertIn("2 requested", text)
            self.assertIn("1 blocked", text)
            self.assertIn("protected-secrets ×1", text)
            self.assertIn("critical block", text)
            self.assertIn("Sentinel digest", chat_command(store, "digest 12"))


if __name__ == "__main__":
    unittest.main()
