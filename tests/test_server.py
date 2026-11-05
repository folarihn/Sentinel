import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sentinel.server import create_server


class ServerTests(unittest.TestCase):
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
