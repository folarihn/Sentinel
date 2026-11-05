import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sentinel.runtime import Runtime
from sentinel.store import Store
from sentinel.rules import RuleSet


class RuntimeTests(unittest.TestCase):
    def test_native_approval_session_key_is_searchable_without_overriding_identity(
        self,
    ):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            runtime = Runtime(store)
            runtime.observe(
                "approval_decided", session_key="native-session", choice="deny"
            )
            self.assertEqual(
                store.events(session_id="native-session")[0]["choice"], "deny"
            )
            runtime.observe(
                "approval_decided",
                session_id="explicit",
                session_key="fallback",
                choice="once",
            )
            self.assertEqual(len(store.events(session_id="explicit")), 1)
            self.assertEqual(store.events(session_id="fallback"), [])

    def test_json_tool_failure_and_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            runtime = Runtime(store)
            runtime.pre_tool(
                "terminal", {"command": "pwd"}, session_id="s", tool_call_id="call"
            )
            runtime.post_tool(
                "terminal",
                result='{"error":"synthetic failure"}',
                session_id="s",
                tool_call_id="call",
            )
            event = store.events()[-1]
            self.assertEqual(event["event_type"], "tool_execution_failed")
            self.assertGreaterEqual(event["duration_ms"], 0)

    def test_custom_rules_and_invalid_configuration_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            rules = RuleSet(store.root)
            rules.save(
                {
                    "rules": [
                        {
                            "id": "terminal-block",
                            "priority": 10,
                            "enabled": True,
                            "tools": ["terminal"],
                            "decision": "BLOCK",
                            "reason": "Maintenance pause",
                        }
                    ]
                }
            )
            runtime = Runtime(store)
            self.assertEqual(
                runtime.pre_tool("terminal", {"command": "pwd"})["action"], "block"
            )
            (store.root / "policies.json").write_text("broken")
            self.assertEqual(
                runtime.pre_tool("read_file", {"path": "fixture.txt"})["action"],
                "block",
            )

    def test_failure_explicitly_blocks(self):
        store = Mock()
        store.mission_for_session.side_effect = OSError("disk full")
        result = Runtime(store).pre_tool("terminal", {"command": "pwd"}, session_id="s")
        self.assertEqual(result["action"], "block")

    def test_lifecycle_real_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            runtime = Runtime(store)
            runtime.observe("session_started", session_id="s")
            self.assertIsNone(
                runtime.pre_tool("terminal", {"command": "pwd"}, session_id="s")
            )
            result = runtime.pre_tool(
                "terminal", {"command": "rm -rf /tmp/synthetic"}, session_id="s"
            )
            self.assertEqual(result["action"], "block")
            runtime.post_tool("terminal", result={"success": True}, session_id="s")
            self.assertGreaterEqual(len(store.events()), 5)

    def test_approval_keys_do_not_cross_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Runtime(Store(Path(folder)))
            first = runtime.pre_tool(
                "terminal", {"command": "git push origin main"}, session_id="a"
            )
            second = runtime.pre_tool(
                "terminal", {"command": "git push origin main"}, session_id="b"
            )
            self.assertEqual(first["action"], "approve")
            self.assertNotEqual(first["rule_key"], second["rule_key"])
