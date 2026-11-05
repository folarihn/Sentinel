"""Generate a real Sentinel journal using explicitly labelled disposable fixtures.

This does not launch Hermes or execute shell commands. It directly exercises
the Sentinel runtime callbacks, writes one disposable file and restores it.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sentinel.recovery import Recovery
from sentinel.runtime import Runtime
from sentinel.store import Store
from sentinel.templates import mission_template


def run_demo(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "disposable-workspace"
    workspace.mkdir()
    store = Store(root / "state")
    runtime = Runtime(store)
    fixture = {"session_id": "fixture-coding-session", "agent_id": "fixture-agent"}
    runtime.observe("fixture_demo_started", **fixture)
    store.append(
        "fixture_disclosure",
        fixture,
        description="Synthetic fixture calls into the real Sentinel runtime; not a live Hermes session.",
    )
    mission = mission_template("safe-coding", workspace, fixture["session_id"])
    mission["status"] = "ACTIVE"
    store.save_mission(mission)
    target = workspace / "example.txt"
    target.write_text("Original disposable fixture\n", encoding="utf-8")
    args = {"path": str(target), "content": "Updated disposable fixture\n"}
    call = {**fixture, "tool_call_id": "fixture-write-001"}
    directive = runtime.pre_tool("write_file", args, **call)
    if directive is not None:
        raise RuntimeError(f"Fixture write unexpectedly rejected: {directive}")
    target.write_text(args["content"], encoding="utf-8")
    runtime.post_tool("write_file", args, result={"success": True}, **call)
    blocked = runtime.pre_tool(
        "terminal",
        {"command": "rm -rf disposable-fixture", "cwd": str(workspace)},
        **fixture,
    )
    if not blocked or blocked["action"] != "block":
        raise RuntimeError("Destructive fixture was not blocked")
    synthetic_secret = workspace / ".env"
    synthetic_secret.write_text("SYNTHETIC_SECRET=fixture-only\n", encoding="utf-8")
    sensitive = runtime.pre_tool(
        "read_file", {"path": str(synthetic_secret)}, **fixture
    )
    if not sensitive or sensitive["action"] != "block":
        raise RuntimeError("Synthetic secret path was not blocked")
    approval = runtime.pre_tool(
        "terminal",
        {"command": "git push origin fixture-branch"},
        session_id="fixture-approval-session",
        tool_call_id="fixture-approval-001",
    )
    if not approval or approval["action"] != "approve":
        raise RuntimeError("Approval directive was not generated")
    # No human decision is fabricated. No push or terminal command executes.
    recovery = Recovery(store, workspace)
    checkpoint = recovery.checkpoints()[0]
    recovery.restore(checkpoint["id"], authorized=True)
    if target.read_text(encoding="utf-8") != "Original disposable fixture\n":
        raise RuntimeError("Fixture restoration failed")
    runtime.observe("fixture_demo_completed", **fixture)
    summary = {
        "mode": "synthetic-fixture-runtime",
        "hermes_live": False,
        "root": str(root),
        "state": str(store.root),
        "restored_file": str(target),
        "events": store.stats()["events"],
        "approval": "Native approval directive generated; human decision not exercised",
    }
    (root / "FIXTURE_DISCLOSURE.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", help="New disposable directory; an existing directory is rejected"
    )
    args = parser.parse_args()
    if args.output:
        root = Path(args.output)
    else:
        root = Path(tempfile.mkdtemp(prefix="sentinel-demo-parent-")) / "fixture"
    print(json.dumps(run_demo(root), indent=2))


if __name__ == "__main__":
    main()
