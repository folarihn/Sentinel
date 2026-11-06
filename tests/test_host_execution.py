"""Optional actual installed Hermes tool-dispatch acceptance (no LLM)."""

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("hermes_cli"), "Hermes is not installed")
class HostExecutionTests(unittest.TestCase):
    def test_actual_dispatch_and_recovery(self):
        from scripts.host_acceptance import run_acceptance

        evidence = run_acceptance()
        self.assertFalse(evidence["live_model"])
        self.assertEqual(len(evidence["checks"]), 6)
        self.assertTrue(all(evidence["checks"].values()))
