import argparse
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel import __version__
from sentinel.commands import (
    Alerts,
    alert_message,
    chat_command,
    doctor,
    handle_cli,
    load_alerts,
    login_link,
    save_alerts,
    setup_cli,
)
from sentinel.runtime import Runtime, register
from sentinel.store import Store


def blocked(store, tool="read_file", rule="protected-secrets", session="s1"):
    store.append(
        "tool_call_blocked",
        {"session_id": session},
        tool_name=tool,
        decision="BLOCK",
        rule=rule,
        reason="Access to secret-related paths is prohibited.",
        risk="critical",
    )


class ChatCommandTests(unittest.TestCase):
    def test_status_blocks_and_missions_report_recorded_state_only(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            self.assertIn("Last block: none recorded", chat_command(store, "status"))
            self.assertIn("No blocked", chat_command(store, "blocks"))
            self.assertIn("No missions", chat_command(store, "missions"))
            blocked(store)
            status = chat_command(store, "")
            self.assertIn(f"Sentinel {__version__} is active", status)
            self.assertIn("1 blocked", status)
            self.assertIn("protected-secrets", status)
            self.assertIn("Alerts: off", status)
            self.assertIn("Blocked: read_file", chat_command(store, "blocks 3"))
            store.save_mission(
                {
                    "name": "Expired job",
                    "status": "ACTIVE",
                    "session_id": "s1",
                    "allowed_directories": [folder],
                    "approved_tools": ["read_file"],
                    "expires_at": "2000-01-01T00:00:00+00:00",
                }
            )
            self.assertIn("Expired job — EXPIRED", chat_command(store, "missions"))
            self.assertIn("Active missions: none", chat_command(store, "status"))
            self.assertIn("/sentinel status", chat_command(store, "unknown"))

    def test_chat_can_toggle_alerts_but_rejects_malformed_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            self.assertIn("on → telegram", chat_command(store, "alerts on"))
            self.assertEqual(
                load_alerts(folder), {"enabled": True, "target": "telegram"}
            )
            self.assertIn(
                "Use a delivery target", chat_command(store, "alerts on bad target")
            )
            self.assertIn(
                "Use a delivery target", chat_command(store, "alerts on ../etc")
            )
            self.assertIn("are off", chat_command(store, "alerts off"))
            self.assertFalse(load_alerts(folder)["enabled"])


class AlertTests(unittest.TestCase):
    decision = {
        "decision": "BLOCK",
        "rule": "destructive-command",
        "reason": "No.",
        "risk": "critical",
    }

    def test_alerts_are_opt_in_high_risk_only_rate_limited_and_journaled(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            sent = []
            clock = [0.0]
            alerts = Alerts(
                store,
                sender=lambda t, m: sent.append((t, m)) or (True, None),
                clock=lambda: clock[0],
            )
            self.assertIsNone(
                alerts.notify("terminal", self.decision, {"session_id": "s"})
            )
            save_alerts(folder, True, "telegram")
            self.assertIsNone(
                alerts.notify("terminal", {**self.decision, "risk": "low"}, {})
            )
            self.assertIsNone(
                alerts.notify("terminal", {**self.decision, "decision": "ALLOW"}, {})
            )
            alerts.notify("terminal", self.decision, {"session_id": "s"}, wait=True)
            self.assertIsNone(
                alerts.notify("terminal", self.decision, {"session_id": "s"})
            )
            clock[0] = 61
            alerts.notify("terminal", self.decision, {"session_id": "s"}, wait=True)
            self.assertEqual(len(sent), 2)
            self.assertEqual(sent[0][0], "telegram")
            self.assertIn("did not run", sent[0][1])
            self.assertEqual(
                [e["event_type"] for e in store.events()], ["alert.sent", "alert.sent"]
            )

    def test_alert_text_never_includes_tool_arguments(self):
        text = alert_message("terminal", self.decision, {"session_id": "s"})
        self.assertNotIn("rm -rf", text)
        self.assertIn("destructive-command", text)

    def test_delivery_failure_is_recorded_and_never_changes_the_block(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            save_alerts(folder, True, "telegram:123")
            runtime = Runtime(store)
            done = threading.Event()

            def broken(target, message):
                try:
                    raise ConnectionError("platform offline")
                finally:
                    done.set()

            runtime.alerts = Alerts(store, sender=broken)
            result = runtime.pre_tool(
                "terminal", {"command": "rm -rf /"}, session_id="s", tool_call_id="c1"
            )
            self.assertEqual(result["action"], "block")
            self.assertTrue(done.wait(5))
            for _ in range(50):
                failures = [
                    e for e in store.events() if e["event_type"] == "alert.failed"
                ]
                if failures:
                    break
                threading.Event().wait(0.05)
            self.assertEqual(failures[0]["target"], "telegram")
            self.assertNotIn("telegram:123", json.dumps(failures[0]))
            self.assertEqual(failures[0]["reason"], "ConnectionError")


class TerminalCommandTests(unittest.TestCase):
    def test_doctor_reports_plain_checks_without_hermes(self):
        with tempfile.TemporaryDirectory() as folder:
            ok, lines = doctor(Path(folder) / "state", check_hermes=False)
            self.assertTrue(ok)
            self.assertTrue(any(line.startswith("✓ Journal") for line in lines))
            self.assertIn("Everything looks right", lines[-1])

    def test_cli_parser_and_read_commands(self):
        parser = argparse.ArgumentParser()
        setup_cli(parser)
        self.assertEqual(parser.parse_args(["dashboard", "--port", "9000"]).port, 9000)
        with tempfile.TemporaryDirectory() as folder:
            blocked(Store(Path(folder)))
            output = io.StringIO()
            with redirect_stdout(output):
                code = handle_cli(parser.parse_args(["blocks", "2"]), home=Path(folder))
            self.assertEqual(code, 0)
            self.assertIn("Blocked: read_file", output.getvalue())

    def test_login_link_keeps_the_token_in_the_fragment(self):
        self.assertEqual(
            login_link(8765, "abc_DEF-123"), "http://127.0.0.1:8765/#login=abc_DEF-123"
        )

    def test_register_adds_chat_and_terminal_commands_when_host_supports_them(self):
        class Ctx:
            def __init__(self):
                self.hooks, self.commands, self.cli = {}, {}, {}

            def register_hook(self, name, fn):
                self.hooks[name] = fn

            def register_command(self, name, handler, description="", args_hint=""):
                self.commands[name] = handler

            def register_cli_command(
                self, name, help, setup_fn, handler_fn=None, description=""
            ):
                self.cli[name] = setup_fn

        with tempfile.TemporaryDirectory() as folder:
            import os
            from unittest import mock

            with mock.patch.dict(os.environ, {"SENTINEL_HOME": folder}):
                ctx = Ctx()
                register(ctx)
                self.assertIn("pre_tool_call", ctx.hooks)
                self.assertIn("is active", ctx.commands["sentinel"]("status"))
                self.assertIn("sentinel", ctx.cli)

                class Old:
                    def register_hook(self, name, fn):
                        pass

                register(Old())  # older hosts without command APIs still load


if __name__ == "__main__":
    unittest.main()
