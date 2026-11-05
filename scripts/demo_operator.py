"""Live local Hermes tool sequence for recording; no model/provider request.

Only operate on a disposable acceptance directory containing profile/workspace.
The delayed worker lets the Control Room observe actual host events as they occur.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def worker(root):
    from hermes_cli.plugins import discover_plugins
    from model_tools import handle_function_call
    from sentinel.store import Store
    from sentinel.recovery import Recovery

    root = Path(root).resolve()
    workspace = root / "workspace"
    store = Store(root / "state")
    session = "live-host-demonstration"
    target = workspace / "operator-note.txt"
    if target.exists():
        raise ValueError("Disposable demonstration marker already exists")
    target.write_text("Original operator note\n", encoding="utf-8")
    store.save_mission(
        {
            "name": "Live host tool demonstration",
            "status": "ACTIVE",
            "session_id": session,
            "allowed_directories": [str(workspace)],
            "approved_tools": ["write_file", "read_file"],
            "allowed_domains": [],
        }
    )
    discover_plugins(force=True)
    time.sleep(15)
    result = handle_function_call(
        "write_file",
        {"path": str(target), "content": "Actual Hermes host write\n"},
        session_id=session,
        task_id=session,
        tool_call_id="operator-write",
    )
    if target.read_text(encoding="utf-8") != "Actual Hermes host write\n":
        raise RuntimeError("Real host write did not occur")
    del result
    time.sleep(8)
    recovery = Recovery(store, workspace)
    point = next(
        c
        for c in recovery.checkpoints()
        if c.get("session_id") == session and c["status"] == "SEALED"
    )
    recovery.restore(point["id"], authorized=True)
    if target.read_text(encoding="utf-8") != "Original operator note\n":
        raise RuntimeError("Real host restoration did not occur")
    store.save_mission({**store.mission_for_session(session), "status": "COMPLETED"})
    summary = {
        "mode": "actual-live-host-tool-demo",
        "live_model": False,
        "write_executed": True,
        "file_restored": True,
        "session_id": session,
    }
    (root / "operator-demo.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if (
        not (root / "profile" / "config.yaml").is_file()
        or not (root / "workspace").is_dir()
    ):
        raise ValueError("A disposable acceptance profile/workspace is required")
    if args.worker:
        worker(root)
        return
    plugin = root / "profile" / "plugins" / "sentinel"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HERMES_", "SENTINEL_"))
        and not any(
            s in k.upper()
            for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "YOLO")
        )
    }
    env.update(
        HERMES_HOME=str(root / "profile"),
        SENTINEL_HOME=str(root / "state"),
        PYTHONPATH=str(plugin),
        PYTHONIOENCODING="utf-8",
        TERMINAL_ENV="local",
        TERMINAL_CWD=str(root / "workspace"),
    )
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--root",
                str(root),
                "--worker",
            ],
            cwd=root / "workspace",
            env=env,
        )
    )


if __name__ == "__main__":
    main()
