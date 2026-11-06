import tempfile
import unittest
from pathlib import Path

from sentinel.policy import approval_key, evaluate


class PolicyTests(unittest.TestCase):
    def test_conflicting_command_aliases_block(self):
        result = evaluate("terminal", {"command": "pwd", "cmd": "rm fixture"}, {})
        self.assertEqual(result["rule"], "ambiguous-command")
        self.assertEqual(result["decision"], "BLOCK")

    def test_recursive_search_cannot_silently_read_secret_descendants(self):
        with tempfile.TemporaryDirectory() as root:
            mission = {"status": "ACTIVE", "allowed_directories": [root]}
            for tool in ["search_files", "search", "grep", "glob"]:
                self.assertEqual(
                    evaluate(tool, {"path": root}, {})["decision"], "APPROVAL_REQUIRED"
                )
                self.assertEqual(
                    evaluate(tool, {"path": root}, {}, mission)["decision"], "BLOCK"
                )

    def test_git_read_name_does_not_allow_unsafe_options(self):
        commands = [
            "git diff --output=result.txt",
            "git diff --ext-diff",
            "git show --textconv HEAD",
            "git log --output=result.txt",
            "git branch --delete branch",
            "git rev-parse --local-env-vars",
            "git -c core.pager=arbitrary status",
            "./git status",
            "/tmp/git status",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.decision(command), "APPROVAL_REQUIRED")
        for command in [
            "git status --short",
            "git branch --show-current",
            "git rev-parse HEAD",
            "git diff --no-ext-diff --no-textconv --stat",
        ]:
            self.assertEqual(self.decision(command), "ALLOW")

    def test_newlines_are_command_boundaries(self):
        for command in [
            "echo safe\nrm -rf disposable",
            "echo safe\r\nRemove-Item disposable",
            "echo safe\rrm disposable",
        ]:
            self.assertEqual(self.decision(command), "BLOCK")
        self.assertEqual(self.decision("pwd\ngit status"), "ALLOW")

    def test_windows_shell_syntax_never_inherits_posix_allow(self):
        for command in [
            "echo %TOKEN%",
            "echo !TOKEN!",
            "echo safe^&whoami",
            "echo C:\\fixture",
            "dir /s",
            "Get-ChildItem -LiteralPath=../outside",
        ]:
            with self.subTest(command=command):
                self.assertNotEqual(self.decision(command), "ALLOW")

    def test_tool_name_cannot_borrow_command_safety(self):
        self.assertEqual(
            evaluate("unknown_remote_tool", {"command": "pwd"}, {})["decision"],
            "APPROVAL_REQUIRED",
        )
        self.assertEqual(
            evaluate("read_file", {"path": "file.txt", "command": "pwd"}, {})["rule"],
            "unexpected-command",
        )
        for command in [None, False, 0, []]:
            self.assertEqual(
                evaluate("terminal", {"command": command}, {})["decision"], "BLOCK"
            )

    def test_unknown_listing_flags_cannot_escape_mission(self):
        with tempfile.TemporaryDirectory() as root:
            mission = {"status": "ACTIVE", "allowed_directories": [root]}
            for command in [
                "ls --ignore=anything ..",
                "Get-ChildItem -LiteralPath=../outside",
                "ls -R .",
                "ls *",
                "ls safe/../../outside",
                "echo %TOKEN%",
            ]:
                with self.subTest(command=command):
                    self.assertEqual(
                        evaluate(
                            "terminal", {"command": command, "cwd": root}, {}, mission
                        )["decision"],
                        "BLOCK",
                    )
            self.assertEqual(
                evaluate("terminal", {"command": "ls -la .", "cwd": root}, {}, mission)[
                    "decision"
                ],
                "ALLOW",
            )

    def test_secret_windows_alternate_stream_and_trailing_dot(self):
        for path in [".env:stream", ".env.", ".ssh./id_rsa", "credentials.json:stream"]:
            self.assertEqual(
                evaluate("read_file", {"path": path}, {})["decision"], "BLOCK"
            )

    def test_network_spelling_cannot_escape_mission(self):
        mission = {"status": "ACTIVE", "allowed_domains": ["example.com"]}
        for url in [
            "HTTPS://EVIL.EXAMPLE",
            "https://example.com.attacker.test.",
            "http://%65vil.example",
        ]:
            self.assertEqual(
                evaluate("web", {"url": url}, {}, mission)["decision"], "BLOCK"
            )
        for url in ["HTTPS://EXAMPLE.COM.", "https://%65xample.com"]:
            self.assertEqual(
                evaluate("web", {"url": url}, {}, mission)["decision"],
                "APPROVAL_REQUIRED",
            )

    def test_resolved_shell_operand_symlink_protection(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            secret = root / ".ssh"
            secret.mkdir()
            alias = root / "alias"
            try:
                alias.symlink_to(secret, target_is_directory=True)
            except OSError:
                self.skipTest(
                    "Creating symlinks requires Windows developer mode or privilege"
                )
            self.assertEqual(
                evaluate("terminal", {"command": "ls alias", "cwd": str(root)}, {})[
                    "rule"
                ],
                "protected-secrets",
            )

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
