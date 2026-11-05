import json
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.audit_release import audit, scan_text
from scripts.verify_catalog import sanitize_output


class ReleaseAuditTests(unittest.TestCase):
    def test_validator_output_sanitizes_wrapped_known_paths_only(self):
        root = r"C:\Users\Alice Name\AppData\Local\Temp\catalog-example"
        wrapped = "Plugin Doctor: C:\\Users\\Alice \nName\\AppData\\Local\\Temp\\catalog-example\\sentinel\n  OK: registration passed\n  warnings: 2\n"
        actual = sanitize_output(wrapped, [(root, "<temporary>")])
        self.assertEqual(
            actual,
            "Plugin Doctor: <temporary>\\sentinel\n  OK: registration passed\n  warnings: 2\n",
        )
        self.assertEqual(scan_text("docs/report.json", actual), [])

    def test_validator_output_sanitizes_json_escaped_paths(self):
        text = json.dumps(
            {
                "path": r"C:\Users\Alice\repository\plugin.py",
                "ok": False,
                "warning": "review required",
            }
        )
        actual = sanitize_output(text, [(r"C:\Users\Alice\repository", "<repository>")])
        self.assertNotIn("Alice", actual)
        self.assertIn('"ok": false', actual)
        self.assertIn("review required", actual)

    def test_personal_paths_and_private_endpoints(self):
        text = "C:\\Users\\Alice\\work\nC:\\\\Users\\\\Alice\\\\work\n/home/alice/project\n/Users/alice/project\nhttp://192.168.1.2/service\nhttps://private-machine.internal"
        findings = scan_text("docs/result.json", text)
        self.assertEqual(len(findings), 6)
        self.assertTrue(all(item["severity"] == "fail" for item in findings))
        self.assertNotIn("Alice", json.dumps(findings))
        self.assertNotIn("192.168", json.dumps(findings))

    def test_loopback_and_documentation_placeholders_allowed(self):
        text = "http://127.0.0.1:8765\nhttp://localhost:8765\nC:\\Users\\username\\work\nC:\\Users\\<username>\\work\n%USERPROFILE%/project\nhttp://192.0.2.1/demo\nhttps://example.internal"
        self.assertEqual(scan_text("README.md", text), [])

    def test_secret_values_not_returned_and_fixtures_require_review(self):
        token = "ghp_" + "A" * 30
        real = scan_text("docs/accidental.txt", token)
        fixture = scan_text("tests/test_redaction.py", token)
        self.assertEqual(real[0]["severity"], "fail")
        self.assertEqual(fixture[0]["severity"], "review")
        self.assertNotIn(token, json.dumps(real + fixture))

    def test_placeholder_assignments_not_secret_candidates(self):
        self.assertEqual(
            scan_text("README.md", 'api_key="YOUR_API_KEY_PLACEHOLDER"'), []
        )

    def test_png_metadata_and_pixel_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"Comment\0/home/alice/project"
            png = (
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", len(payload))
                + b"tEXt"
                + payload
                + b"\x00" * 4
            )
            (root / "image.png").write_bytes(png)
            result = audit(root, ["image.png"])
            self.assertEqual(result["scanned_files"], 1)
            self.assertEqual(result["counts"], {"fail": 1, "review": 1})
            self.assertNotIn("alice", json.dumps(result))

    def test_snapshot_scope_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("safe", encoding="utf-8")
            result = audit(root, ["README.md"])
            self.assertEqual(result["counts"], {})
            self.assertIn("excludes git history", result["scope"])


if __name__ == "__main__":
    unittest.main()
