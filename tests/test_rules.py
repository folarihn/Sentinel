import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.rules import PolicyValidationError, RuleSet, validate


def rule(identifier="restricted", decision="BLOCK", **fields):
    return {
        "id": identifier,
        "priority": 100,
        "enabled": True,
        "tools": ["write_*"],
        "decision": decision,
        "reason": "Operator restriction",
        **fields,
    }


class RuleTests(unittest.TestCase):
    def test_domain_canonical_spellings_match_restrictions(self):
        with tempfile.TemporaryDirectory() as root:
            rules = RuleSet(root)
            rules.save({"rules": [rule(tools=["*"], domains=["example.com"])]})
            for url in [
                "HTTPS://EXAMPLE.COM",
                "https://example.com.",
                "https://%65xample.com",
            ]:
                self.assertEqual(
                    rules.evaluate("fetch", {"url": url}, {})["decision"], "BLOCK"
                )

    def test_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            rules = RuleSet(root)
            rules.path.write_text('{"rules":[],"rules":[]}', encoding="utf-8")
            with self.assertRaises(PolicyValidationError):
                rules.load()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.rules = RuleSet(self.directory.name)

    def test_atomic_persistence_and_match(self):
        self.assertEqual(self.rules.load(), {"rules": []})
        saved = self.rules.save({"rules": [rule()]})
        self.assertEqual(RuleSet(self.directory.name).load(), saved)
        self.assertEqual(
            self.rules.evaluate("write_file", {"path": "file"}, {})["decision"], "BLOCK"
        )
        self.assertIsNone(self.rules.evaluate("read_file", {}, {}))

    def test_validation_rejects_allow_and_malformed(self):
        for document in [
            {"rules": [rule(decision="ALLOW")]},
            {"rules": [rule(priority=True)]},
            {"rules": [rule(enabled="true")]},
            {"rules": [rule(tools=[])]},
            {"rules": [rule(), rule()]},
            {"rules": [rule(domains=["*.example.com"])]},
            {"rules": [rule(path_roots=["relative"])]},
            {"rules": [], "extra": 1},
        ]:
            with (
                self.subTest(document=document),
                self.assertRaises(PolicyValidationError),
            ):
                validate(document)

    def test_block_stronger_than_approval_priority(self):
        self.rules.save(
            {
                "rules": [
                    rule("approve", "APPROVAL_REQUIRED", priority=1000),
                    rule("block", priority=1),
                ]
            }
        )
        self.assertEqual(
            self.rules.evaluate("write_file", {}, {})["rule"], "operator:block"
        )

    def test_disabled_and_identity_isolation(self):
        self.rules.save({"rules": [rule(session_id="one", agent_id="a")]})
        self.assertIsNone(
            self.rules.evaluate(
                "write_file", {}, {"session_id": "two", "agent_id": "a"}
            )
        )
        self.assertIsNotNone(
            self.rules.evaluate(
                "write_file", {}, {"session_id": "one", "agent_id": "a"}
            )
        )
        self.rules.save({"rules": [rule(enabled=False)]})
        self.assertIsNone(self.rules.evaluate("write_file", {}, {}))

    def test_exact_domain_and_resolved_path(self):
        self.rules.save(
            {
                "rules": [
                    rule(
                        tools=["*"],
                        domains=["example.com"],
                        path_roots=[self.directory.name],
                    )
                ]
            }
        )
        args = {
            "url": "https://example.com",
            "path": str(Path(self.directory.name) / "file"),
        }
        self.assertIsNotNone(self.rules.evaluate("web", args, {}))
        args["url"] = "https://example.com.attacker.test"
        self.assertIsNone(self.rules.evaluate("web", args, {}))
        args["url"] = "https://example.com"
        args["path"] = str(Path(self.directory.name) / ".." / "outside")
        self.assertIsNone(self.rules.evaluate("web", args, {}))

    def test_corrupt_config_raises_and_failed_replace_preserves_old(self):
        original = self.rules.save({"rules": [rule()]})
        with patch("sentinel.rules.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.rules.save({"rules": []})
        self.assertEqual(self.rules.load(), original)
        self.assertEqual(list(Path(self.directory.name).glob(".policies-*")), [])
        self.rules.path.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(PolicyValidationError):
            self.rules.evaluate("write_file", {}, {})

    def test_invalid_save_preserves_existing(self):
        original = self.rules.save({"rules": [rule()]})
        with self.assertRaises(PolicyValidationError):
            self.rules.save({"rules": [rule(decision="ALLOW")]})
        self.assertEqual(self.rules.load(), original)


if __name__ == "__main__":
    unittest.main()
