import tempfile
import unittest
from pathlib import Path

from sentinel.recovery import Recovery
from sentinel.runtime import Runtime
from sentinel.store import Store


class RuntimeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        self.store = Store(Path(self.temp.name) / "state")
        self.runtime = Runtime(self.store)
        self.mission = self.store.save_mission(
            {
                "name": "fixture",
                "session_id": "a",
                "status": "ACTIVE",
                "allowed_directories": [str(self.workspace)],
                "approved_tools": ["write_file", "read_file"],
            }
        )

    def test_auto_recovery_between_actual_write_callbacks(self):
        target = self.workspace / "file.txt"
        target.write_text("before")
        args = {
            "path": str(target),
            "content": "arbitrary-credential-not-pattern-matched",
        }
        self.assertIsNone(
            self.runtime.pre_tool(
                "write_file", args, session_id="a", tool_call_id="call-1"
            )
        )
        self.assertEqual(len(self.runtime.pending), 1)
        target.write_text("after")
        self.runtime.post_tool(
            "write_file", args, {"success": True}, session_id="a", tool_call_id="call-1"
        )
        self.assertEqual(self.runtime.pending, {})
        recovery = Recovery(self.store, self.workspace)
        point = recovery.checkpoints()[0]
        self.assertEqual(point["status"], "SEALED")
        recovery.restore(point["id"], authorized=True)
        self.assertEqual(target.read_text(), "before")
        self.assertNotIn(args["content"], str(self.store.events()))

    def test_mission_pause_expiry_and_session_association(self):
        args = {"path": str(self.workspace / "file.txt")}
        paused = {**self.mission, "status": "PAUSED"}
        self.store.save_mission(paused)
        self.assertEqual(
            self.runtime.pre_tool("read_file", args, session_id="a")["action"], "block"
        )
        self.assertIsNone(self.runtime.pre_tool("read_file", args, session_id="b"))
        expired = {
            **self.mission,
            "status": "ACTIVE",
            "expires_at": "2000-01-01T00:00:00+00:00",
        }
        self.store.save_mission(expired)
        self.assertEqual(
            self.runtime.pre_tool("read_file", args, session_id="a")["action"], "block"
        )
        self.assertIsNone(self.runtime.pre_tool("read_file", args, session_id="b"))

    def test_call_correlation_cannot_cross_sessions(self):
        target = self.workspace / "file.txt"
        target.write_text("before")
        args = {"path": str(target), "content": "after"}
        self.assertIsNone(
            self.runtime.pre_tool(
                "write_file", args, session_id="a", tool_call_id="same-id"
            )
        )
        target.write_text("after")
        self.runtime.post_tool(
            "write_file",
            args,
            {"success": True},
            session_id="b",
            tool_call_id="same-id",
        )
        self.assertEqual(
            Recovery(self.store, self.workspace).checkpoints()[0]["status"], "OPEN"
        )
        self.runtime.post_tool(
            "write_file",
            args,
            {"success": True},
            session_id="a",
            tool_call_id="same-id",
        )
        self.assertEqual(
            Recovery(self.store, self.workspace).checkpoints()[0]["status"], "SEALED"
        )

    def test_arbitrary_source_payloads_omitted(self):
        for field in ("content", "text", "code", "script"):
            self.store.append("fixture", args={field: "unrecognizable-sensitive-bytes"})
        self.assertNotIn("unrecognizable-sensitive-bytes", str(self.store.events()))
