"""Optional real installed-Hermes contract tests; no LLM or real tool execution.

The host discovers a fresh plugin copy in a disposable HERMES_HOME. Only the
human decision is supplied by a fixture callback through the public host API.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("hermes_cli"), "Hermes is not installed")
class InstalledHermesTests(unittest.TestCase):
    def test_discovery_policy_and_native_approval_gate(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="sentinel-hermes-") as directory:
            home = Path(directory)
            plugin = home / "plugins" / "sentinel"
            plugin.mkdir(parents=True)
            for filename in ("__init__.py", "plugin.yaml"):
                shutil.copy2(repo / filename, plugin / filename)
            shutil.copytree(
                repo / "sentinel",
                plugin / "sentinel",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            (home / "config.yaml").write_text(
                "plugins:\n  enabled:\n    - sentinel\napprovals:\n  mode: manual\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("HERMES_") or key.startswith("SENTINEL_"):
                    del env[key]
            env.update(
                HERMES_HOME=str(home),
                SENTINEL_HOME=str(home / "sentinel-data"),
                HERMES_INTERACTIVE="1",
                PYTHONIOENCODING="utf-8",
            )
            script = r"""
import json
from hermes_cli.plugins import discover_plugins, get_plugin_manager, resolve_pre_tool_block, invoke_hook
from tools.approval import set_current_session_key, reset_current_session_key
from tools.terminal_tool import set_approval_callback

discover_plugins(force=True)
info = next(x for x in get_plugin_manager().list_plugins() if x["name"] == "sentinel")
assert info["enabled"] and not info["error"], info
assert info["hooks"] >= 2, info
assert resolve_pre_tool_block("terminal", {"command": "git status"}, session_id="one", tool_call_id="safe") is None
blocked = resolve_pre_tool_block("terminal", {"command": "rm -rf disposable-fixture"}, session_id="one", tool_call_id="blocked")
assert blocked and "Sentinel" in blocked, blocked
secret = resolve_pre_tool_block("read_file", {"path": ".env.synthetic"}, session_id="one", tool_call_id="secret")
assert secret and "protected-secrets" in secret, secret
requests = []
def deny(command, description, **kwargs):
    requests.append((command, description))
    return "deny"
set_approval_callback(deny)
token = set_current_session_key("one")
try:
    denied = resolve_pre_tool_block("terminal", {"command": "git push"}, session_id="one", tool_call_id="deny")
    assert denied and "BLOCKED" in denied, denied
    assert len(requests) == 1, requests
    def once(command, description, **kwargs):
        requests.append((command, description))
        return "once"
    set_approval_callback(once)
    allowed = resolve_pre_tool_block("terminal", {"command": "git push"}, session_id="one", tool_call_id="once")
    assert allowed is None, allowed
    assert len(requests) == 2, requests
    set_approval_callback(deny)
    changed = resolve_pre_tool_block("terminal", {"command": "git push --force"}, session_id="two", tool_call_id="different")
    assert changed and "BLOCKED" in changed, changed
    assert len(requests) == 3, requests
finally:
    reset_current_session_key(token)
    set_approval_callback(None)
invoke_hook("post_tool_call", tool_name="terminal", args={"command":"git status"}, result={"success":True}, session_id="one", tool_call_id="safe")
from tools.approval import enable_session_yolo, disable_session_yolo
yolo_token = set_current_session_key("isolated-yolo")
try:
    enable_session_yolo("isolated-yolo")
    assert resolve_pre_tool_block("terminal", {"command":"git push"}, session_id="isolated-yolo", tool_call_id="yolo-approval") is None
    assert resolve_pre_tool_block("terminal", {"command":"rm -rf disposable-fixture"}, session_id="isolated-yolo", tool_call_id="yolo-block")
finally:
    disable_session_yolo("isolated-yolo")
    reset_current_session_key(yolo_token)
print(json.dumps({"loaded":info["name"], "hooks": info["hooks"], "native_decisions":len(requests), "tool_execution":"not executed; host dispatch gate verified"}))
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(summary["loaded"], "sentinel")
            self.assertEqual(summary["native_decisions"], 3)


if __name__ == "__main__":
    unittest.main()
