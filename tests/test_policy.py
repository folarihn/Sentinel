import tempfile
import unittest
from pathlib import Path

from sentinel.policy import approval_key, evaluate


class PolicyTests(unittest.TestCase):
    def test_unresolved_network_and_mission_required_approval(self):
        mission = {"status": "ACTIVE", "allowed_domains": ["example.com"]}
        result = evaluate("web_search", {"query": "test"}, {}, mission)
        self.assertEqual(result["decision"], "BLOCK")
        mission["required_approvals"] = ["read_file"]
        result = evaluate("read_file", {"path": "fixture.txt"}, {}, mission)
        self.assertEqual(result["decision"], "APPROVAL_REQUIRED")

    def decision(self, command):
        return evaluate("terminal", {"command": command}, {"session_id": "one"})[
            "decision"
        ]

    def test_safe(self):
        self.assertEqual(self.decision("git status"), "ALLOW")

    def test_destructive_chains_and_quoting(self):
        for command in [
            "echo safe && rm -rf fixture",
            '"Remove-Item" -Recurse fixture',
            "git reset --hard",
            "git clean -fd",
            "sudo ls",
        ]:
            with self.subTest(command=command):
                self.assertEqual(self.decision(command), "BLOCK")

    def test_opaque_execution(self):
        for command in [
            "python -c 'print(1)'",
            "bash script.sh",
            "echo $(whoami)",
            "git -C .. push",
        ]:
            self.assertEqual(self.decision(command), "APPROVAL_REQUIRED")

    def test_secret_access(self):
        for path in [".env", "project/.env.local", "C:\\user\\.ssh\\id_ed25519"]:
            self.assertEqual(
                evaluate("read_file", {"path": path}, {})["decision"], "BLOCK"
            )

    def test_approval_binding(self):
        a = approval_key("terminal", {"command": "git push"}, {"session_id": "a"})
        self.assertNotEqual(
            a, approval_key("terminal", {"command": "git push"}, {"session_id": "b"})
        )
        self.assertNotEqual(
            a,
            approval_key(
                "terminal", {"command": "git push --force"}, {"session_id": "a"}
            ),
        )
        self.assertEqual(
            a, approval_key("terminal", {"command": "git push"}, {"session_id": "a"})
        )

    def test_scope_and_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            mission = {
                "status": "ACTIVE",
                "allowed_directories": [root],
                "approved_tools": ["read_file"],
            }
            self.assertEqual(
                evaluate(
                    "read_file", {"path": str(Path(root) / "safe.txt")}, {}, mission
                )["decision"],
                "ALLOW",
            )
            self.assertEqual(
                evaluate(
                    "read_file",
                    {"path": str(Path(root) / ".." / "outside.txt")},
                    {},
                    mission,
                )["decision"],
                "BLOCK",
            )
            mission["status"] = "PAUSED"
            self.assertEqual(
                evaluate("read_file", {}, {}, mission)["decision"], "BLOCK"
            )
            mission["status"] = "ACTIVE"
            mission["expires_at"] = "2000-01-01T00:00:00Z"
            self.assertEqual(
                evaluate("read_file", {}, {}, mission)["rule"], "mission-expired"
            )

    def test_network_exact_host(self):
        mission = {"status": "ACTIVE", "allowed_domains": ["example.com"]}
        self.assertEqual(
            evaluate("web", {"url": "https://example.com.attacker.test"}, {}, mission)[
                "decision"
            ],
            "BLOCK",
        )
        self.assertEqual(
            evaluate("web", {"url": "https://example.com"}, {}, mission)["decision"],
            "APPROVAL_REQUIRED",
        )

    def test_mandatory_precedence(self):
        mission = {"status": "ACTIVE", "approved_tools": ["terminal"]}
        self.assertEqual(
            evaluate("terminal", {"command": "rm safe"}, {}, mission)["rule"],
            "destructive-command",
        )

    def test_invalid_quoting(self):
        self.assertEqual(self.decision("echo 'unclosed"), "BLOCK")

    def test_redirection_and_expansion(self):
        self.assertEqual(self.decision("echo value > file.txt"), "APPROVAL_REQUIRED")
        self.assertEqual(self.decision("echo $TOKEN"), "APPROVAL_REQUIRED")

    def test_mission_shell_is_not_directory_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            mission = {"status": "ACTIVE", "allowed_directories": [root]}
            self.assertEqual(
                evaluate("terminal", {"command": "ls ..", "cwd": root}, {}, mission)[
                    "decision"
                ],
                "BLOCK",
            )
            self.assertEqual(
                evaluate(
                    "terminal",
                    {"command": "python arbitrary.py", "cwd": root},
                    {},
                    mission,
                )["rule"],
                "mission-shell-unconfined",
            )

    def test_resolved_symlink_escape(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as outside,
        ):
            link = Path(root) / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest(
                    "Creating symlinks requires Windows developer mode or privilege"
                )
            mission = {"status": "ACTIVE", "allowed_directories": [root]}
            self.assertEqual(
                evaluate("read_file", {"path": str(link / "data.txt")}, {}, mission)[
                    "decision"
                ],
                "BLOCK",
            )

    def test_control_plane_protection(self):
        with tempfile.TemporaryDirectory() as root:
            protected = Path(root) / "sentinel"
            identity = {"protected_directories": [str(protected)]}
            for path in [protected / "events.sqlite", Path(root)]:
                self.assertEqual(
                    evaluate("write_file", {"path": str(path)}, identity)["rule"],
                    "protected-control-plane",
                )

    def test_unknown_tool_requires_approval(self):
        self.assertEqual(
            evaluate("arbitrary_plugin", {}, {})["rule"], "unclassified-tool"
        )

    def test_nested_paths_inspected(self):
        self.assertEqual(
            evaluate("write_file", {"files": [{"path": ".ssh/key"}]}, {})["decision"],
            "BLOCK",
        )


if __name__ == "__main__":
    unittest.main()
