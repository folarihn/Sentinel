import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sentinel.server import create_server
from sentinel.store import Store
from sentinel.runtime import Runtime


class ServerTests(unittest.TestCase):
    def test_malformed_requests_are_actionable(self):
        for body in (
            [],
            "not-an-object",
            {"tool_name": "terminal", "identity": [], "args": {}},
            {"tool_name": 4},
        ):
            with self.subTest(body=body), self.assertRaises(HTTPError) as error:
                self.request("/api/evaluate", body)
            self.assertEqual(error.exception.code, 400)

    def test_policy_change_controls_actual_runtime_and_survives_restart(self):
        root = Path(self.folder.name)
        rules = {
            "rules": [
                {
                    "id": "restrict-session",
                    "priority": 1,
                    "enabled": True,
                    "tools": ["terminal"],
                    "session_id": "restricted",
                    "decision": "BLOCK",
                    "reason": "QA restriction",
                }
            ]
        }
        self.request("/api/policies", rules)
        runtime = Runtime(Store(root / "state"))
        self.assertEqual(
            runtime.pre_tool("terminal", {"command": "pwd"}, session_id="restricted")[
                "action"
            ],
            "block",
        )
        self.assertIsNone(
            runtime.pre_tool("terminal", {"command": "pwd"}, session_id="other")
        )
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server = create_server(
            root / "state", root, port=0, token="test-only-token"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("/api/policies"), rules)
        self.assertEqual(len(self.request("/api/sessions")), 2)
        self.assertEqual(len(self.request("/api/events")), 5)

    def test_large_history_paginates_without_loss(self):
        store = Store(Path(self.folder.name) / "state")
        for n in range(1205):
            store.append("acceptance_record", {"session_id": str(n % 3)}, ordinal=n)
        events, cursor = [], 0
        while True:
            page = self.request(f"/api/events?limit=500&after={cursor}")
            if not page:
                break
            events.extend(page)
            cursor = page[-1]["seq"]
        self.assertEqual([e["ordinal"] for e in events], list(range(1205)))
        self.assertEqual(len(self.request("/api/sessions")), 3)

    def test_actual_file_restore_api(self):
        target = Path(self.folder.name) / "recovery.txt"
        target.write_text("before")
        point = self.request("/api/checkpoints", {"path": str(target)})
        displayed = self.request("/api/checkpoints")[0]
        self.assertEqual(displayed["display_path"], "recovery.txt")
        self.assertEqual(displayed["path"], str(target.resolve()))
        target.write_text("after")
        self.request("/api/checkpoints/seal", {"id": point["id"]})
        self.request("/api/restore", {"id": point["id"], "authorized": True})
        self.assertEqual(target.read_text(), "before")

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.server = create_server(
            root / "state", root, port=0, token="test-only-token"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, path, body=None, auth=True, headers=None):
        h = {"Authorization": "Bearer test-only-token"} if auth else {}
        h.update(headers or {})
        request = Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=h,
        )
        with urlopen(request) as response:
            return json.load(response)

    def test_auth_and_origin(self):
        for headers, auth in [
            ({}, False),
            ({"Origin": "https://evil.example"}, True),
            ({"Host": "evil.example"}, True),
        ]:
            with self.assertRaises(HTTPError) as error:
                self.request("/api/events", auth=auth, headers=headers)
            self.assertEqual(error.exception.code, 401)

    def test_mission_roundtrip_and_evaluation(self):
        mission = self.request(
            "/api/missions",
            {
                "name": "Fixture",
                "session_id": "s",
                "status": "ACTIVE",
                "restricted_tools": ["terminal"],
            },
        )
        self.assertEqual(self.request("/api/missions")[0]["id"], mission["id"])
        changed = self.request("/api/missions/" + mission["id"], {"status": "PAUSED"})
        self.assertEqual(changed["status"], "PAUSED")
        decision = self.request(
            "/api/evaluate",
            {"tool_name": "terminal", "args": {"command": "rm -rf fixture"}},
        )
        self.assertEqual(decision["decision"], "BLOCK")
        self.assertGreater(self.request("/api/status")["stats"]["events"], 0)

    def test_static_traversal_and_malformed_json(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/../sentinel.sqlite3")
        self.assertEqual(error.exception.code, 404)
        with self.assertRaises(HTTPError) as error:
            self.request("/api/missions", {"name": "bad", "status": "invalid"})
        self.assertEqual(error.exception.code, 400)

    def test_policies_templates_and_retention(self):
        self.assertEqual(len(self.request("/api/templates")), 7)
        rules = {
            "rules": [
                {
                    "id": "pause",
                    "priority": 1,
                    "enabled": True,
                    "tools": ["terminal"],
                    "decision": "BLOCK",
                    "reason": "Operator pause",
                }
            ]
        }
        self.assertEqual(self.request("/api/policies", rules), rules)
        self.assertEqual(self.request("/api/policies"), rules)
        decision = self.request(
            "/api/evaluate", {"tool_name": "terminal", "args": {"command": "pwd"}}
        )
        self.assertEqual(decision["decision"], "BLOCK")
        self.assertGreater(
            self.request("/api/retention", {"before": "2099-01-01T00:00:00+00:00"})[
                "deleted"
            ],
            0,
        )
