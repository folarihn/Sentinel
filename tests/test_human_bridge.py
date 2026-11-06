"""Decision-parser tests only; no claim that a human has approved anything."""

import unittest
from datetime import datetime, timedelta, timezone

from scripts.human_acceptance import validate_decision, summarize_decisions


class HumanBridgeTests(unittest.TestCase):
    def test_multiple_checkpoints_are_genuine_without_faking_rejection(self):
        metrics = summarize_decisions(
            [{"actor": "owner-via-chat", "decision": "once"}] * 4,
            [{"marker_created": True, "marker_content_valid": True}] * 2,
        )
        self.assertTrue(metrics["genuine_owner_decisions_received"])
        self.assertTrue(metrics["human_approval_with_tool_effect_verified"])
        self.assertFalse(metrics["human_rejection_verified"])
        self.assertFalse(metrics["both_human_outcomes_verified"])

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.pending = {
            "nonce": "exact-operation-random-nonce",
            "expires_at": (self.now + timedelta(seconds=180)).isoformat(),
        }

    def test_exact_nonce_and_choices(self):
        for choice in ("deny", "once"):
            result = validate_decision(
                {
                    "nonce": self.pending["nonce"],
                    "choice": choice,
                    "actor": "owner-via-chat",
                },
                self.pending,
                self.now,
            )
            self.assertEqual(result, choice)

    def test_rejects_reuse_and_broad_grants(self):
        for payload in (
            {"nonce": "another-operation", "choice": "once", "actor": "owner-via-chat"},
            {
                "nonce": self.pending["nonce"],
                "choice": "always",
                "actor": "owner-via-chat",
            },
            {"nonce": self.pending["nonce"], "choice": "once", "actor": "fixture"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_decision(payload, self.pending, self.now)

    def test_expiry_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            validate_decision(
                {
                    "nonce": self.pending["nonce"],
                    "choice": "once",
                    "actor": "owner-via-chat",
                },
                self.pending,
                self.now + timedelta(seconds=181),
            )

    def test_malformed_input(self):
        with self.assertRaises(ValueError):
            validate_decision(None, self.pending, self.now)
