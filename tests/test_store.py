import concurrent.futures
import tempfile
import unittest
from pathlib import Path

from sentinel.store import Store
from sentinel.runtime import Runtime


class StoreTests(unittest.TestCase):
    def test_real_database_lock_blocks_execution_then_recovers(self):
        contender = Store(self.temp.name, timeout=0.05)
        runtime = Runtime(contender)
        with self.store.connect() as locker:
            locker.execute("BEGIN IMMEDIATE")
            directive = runtime.pre_tool(
                "terminal", {"command": "pwd"}, session_id="locked"
            )
            self.assertEqual(directive["action"], "block")
        self.assertIsNone(
            runtime.pre_tool("terminal", {"command": "pwd"}, session_id="unlocked")
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))

    def test_redaction_persistence_and_pagination(self):
        self.store.append(
            "tool.requested",
            {"session_id": "a"},
            args={"api_key": "real-secret", "command": "echo token=real-token"},
        )
        self.store.append("tool.allowed", {"session_id": "b"})
        first = Store(self.temp.name).events(limit=1)
        self.assertEqual(len(first), 1)
        self.assertNotIn("real-secret", str(first))
        self.assertNotIn("real-token", str(first))
        self.assertEqual(self.store.events(after=first[0]["seq"])[0]["session_id"], "b")
        self.assertEqual(len(self.store.events(session_id="a")), 1)
        self.assertEqual(len(self.store.events(search="tool.allowed")), 1)

    def test_concurrent_writers(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(
                pool.map(
                    lambda n: self.store.append(
                        "tool.allowed", {"session_id": str(n % 2)}
                    ),
                    range(60),
                )
            )
        events = self.store.events()
        self.assertEqual(len(events), 60)
        self.assertEqual(len({e["id"] for e in events}), 60)
        self.assertEqual([e["seq"] for e in events], sorted(e["seq"] for e in events))
        self.assertEqual(self.store.stats()["sessions"], 2)

    def test_mission_validation_and_isolation(self):
        mission = self.store.save_mission(
            {"name": "Safe coding", "status": "ACTIVE", "session_id": "a"}
        )
        self.assertEqual(self.store.mission_for_session("a")["id"], mission["id"])
        self.assertIsNone(self.store.mission_for_session("b"))
        with self.assertRaises(ValueError):
            self.store.save_mission(
                {"name": "conflict", "status": "ACTIVE", "session_id": "a"}
            )
        with self.assertRaises(ValueError):
            self.store.save_mission({"name": "bad", "status": "WHATEVER"})
        with self.assertRaises(ValueError):
            self.store.save_mission(
                {"name": "bad", "expires_at": "2026-11-05T12:00:00"}
            )

    def test_retention(self):
        self.store.append("test")
        self.assertEqual(self.store.retain("2099-01-01T00:00:00+00:00"), 1)
        self.assertEqual(self.store.events(), [])

    def test_retention_requires_timezone_and_normalizes_offset(self):
        self.store.append("test")
        with self.assertRaises(ValueError):
            self.store.retain("2099-01-01T00:00:00")
        self.assertEqual(self.store.retain("2099-01-01T01:00:00+01:00"), 1)

    def test_common_embedded_credentials(self):
        self.store.append(
            "test",
            value="https://alice:password@example.com/ -----BEGIN RSA PRIVATE KEY-----\nfixture\n-----END RSA PRIVATE KEY----- Bearer topsecret",
        )
        payload = str(self.store.events())
        self.assertNotIn("password@", payload)
        self.assertNotIn("fixture", payload)
        self.assertNotIn("topsecret", payload)

    def test_mission_policy_fields_and_unbound_session(self):
        self.store.save_mission(
            {"name": "unbound", "session_id": "", "status": "ACTIVE"}
        )
        self.assertIsNone(self.store.mission_for_session(""))
        for extra in (
            {"allow_deployment": "yes"},
            {"allowed_domains": "example.com"},
            {"allowed_domains": ["https://example.com"]},
            {"session_id": []},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.store.save_mission({"name": "invalid", **extra})

    def test_unknown_schema_rejected(self):
        with self.store.connect() as db:
            db.execute("UPDATE schema_version SET version=99")
        with self.assertRaisesRegex(ValueError, "Unsupported Sentinel schema"):
            Store(self.temp.name)

    def test_concurrent_active_mission_uniqueness(self):
        def create(n):
            try:
                self.store.save_mission(
                    {"name": str(n), "session_id": "same", "status": "ACTIVE"}
                )
                return True
            except ValueError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(create, range(12)))
        self.assertEqual(sum(results), 1)

    def test_seven_templates_are_independent(self):
        from sentinel.templates import TEMPLATES, mission_template

        self.assertEqual(len(TEMPLATES), 7)
        for key in TEMPLATES:
            mission = mission_template(key, self.temp.name)
            self.assertEqual(self.store.save_mission(mission)["status"], "DRAFT")
            mission["allowed_directories"].append("changed")
            self.assertEqual(
                len(mission_template(key, self.temp.name)["allowed_directories"]), 1
            )
