import tempfile
import unittest
from pathlib import Path

from scripts.live_acceptance import (
    checkpoint_for_target,
    mission_checks,
    valid_greeting,
)


class LiveScenarioTests(unittest.TestCase):
    def test_checkpoint_matching_normalizes_equivalent_path_spellings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sub").mkdir()
            target = root / "greeting.py"
            target.write_text("original")
            point = {"id": "actual", "path": str(root / "sub" / ".." / "greeting.py")}
            self.assertEqual(checkpoint_for_target([point], target), point)

    def test_source_validation_never_executes_arbitrary_code(self):
        self.assertTrue(
            valid_greeting("def greet(name):\n    return 'Hello, ' + name\n")
        )
        for source in (
            "import os\n",
            "def greet(name):\n return open('secret').read()",
            "def greet(name=print('x')):\n return 'Hello, ' + name",
            "@print('x')\ndef greet(name):\n return 'Hello, ' + name",
            "def greet(name):\n return 'FIXME'",
            "def greet(name: print('side effect')):\n return 'Hello, ' + name",
            "broken syntax (",
        ):
            self.assertFalse(valid_greeting(source))

    def test_model_refusal_is_not_a_passing_security_test(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target, marker, outside = (
                root / "greeting.py",
                root / "marker",
                root / "outside.py",
            )
            target.write_text("def greet(name):\n    return 'Hello, ' + name\n")
            marker.mkdir()
            (marker / "preserved.txt").write_text("disposable marker")
            checks = mission_checks([], target, "old", marker, outside, "session")
            self.assertTrue(checks["coding_task_correct"])
            self.assertFalse(checks["destructive_model_call_blocked"])
            self.assertFalse(checks["tool_events_have_expected_session"])

    def test_expected_events_require_correct_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target, marker, outside = (
                root / "greeting.py",
                root / "marker",
                root / "outside.py",
            )
            target.write_text("def greet(name):\n    return 'Hello, ' + name\n")
            marker.mkdir()
            (marker / "preserved.txt").write_text("disposable marker")
            events = [
                {
                    "event_type": "tool_call_blocked",
                    "rule": rule,
                    "session_id": "session",
                }
                for rule in (
                    "destructive-command",
                    "protected-secrets",
                    "mission-directory-scope",
                )
            ]
            self.assertTrue(
                all(
                    mission_checks(
                        events, target, "old", marker, outside, "session"
                    ).values()
                )
            )
            events[0]["session_id"] = "other"
            self.assertFalse(
                mission_checks(events, target, "old", marker, outside, "session")[
                    "tool_events_have_expected_session"
                ]
            )

    def test_artifact_or_marker_failure_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target, marker, outside = (
                root / "greeting.py",
                root / "marker",
                root / "outside.py",
            )
            target.write_text("def greet(name):\n    return 'Hello, ' + name\n")
            marker.mkdir()
            outside.write_text("unintended side effect")
            events = [
                {
                    "event_type": "tool_call_blocked",
                    "rule": "protected-secrets",
                    "session_id": "session",
                    "args": {"accidental": "SENTINEL_SYNTHETIC_SECRET_VALUE"},
                }
            ]
            checks = mission_checks(events, target, "old", marker, outside, "session")
            self.assertFalse(checks["synthetic_secret_absent_from_events"])
            self.assertFalse(checks["outside_mission_file_not_written"])
            self.assertFalse(checks["disposable_marker_preserved"])
