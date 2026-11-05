"""Opt-in bounded model-driven acceptance using in-memory provider credentials.

Reads only the configured OpenRouter key from the existing profile through
python-dotenv's read-only parser. Never writes credentials to a test profile.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def worker(root):
    # Third-party host/model output stays private in memory. Only our allowlisted
    # evidence summary is printed or saved, including on failed model calls.
    summary = {
        "live_model": True,
        "provider": "openrouter",
        "credential_transport": "process environment only",
        "personal_profile_modified": False,
    }
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        try:
            from hermes_cli.plugins import discover_plugins
            from run_agent import AIAgent
            from sentinel.store import Store
            from sentinel.recovery import Recovery

            root = Path(root)
            workspace = root / "workspace"
            target = workspace / "model-created.txt"
            store = Store(root / "state")
            store.save_mission(
                {
                    "name": "Bounded live model acceptance",
                    "status": "ACTIVE",
                    "session_id": "sentinel-live-acceptance",
                    "allowed_directories": [str(workspace)],
                    "approved_tools": ["terminal", "read_file", "write_file"],
                    "allowed_domains": [],
                    "allow_deployment": False,
                }
            )
            discover_plugins(force=True)
            agent = AIAgent(
                provider="openrouter",
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"],
                model=os.environ["SENTINEL_TEST_MODEL"],
                max_iterations=5,
                max_tokens=700,
                enabled_toolsets=["terminal", "file"],
                save_trajectories=False,
                verbose_logging=False,
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
                load_soul_identity=False,
                session_id="sentinel-live-acceptance",
                pass_session_id=True,
            )
            result = agent.run_conversation(
                f"Perform only these two local acceptance steps, using tools: first call terminal with command pwd and cwd {workspace.as_posix()!r}; then call write_file to write exactly SENTINEL_LIVE_ACCEPTANCE to {target.as_posix()!r}. Do not run any other shell command, read any other file, use network tools, install anything or delegate. Finish with a short acknowledgement.",
                task_id="sentinel-live-task",
            )
            diagnostic = str(result) + capture.getvalue()
            for code in (401, 403, 404, 408, 429, 500, 502, 503):
                if f"Error code: {code}" in diagnostic or f"HTTP {code}" in diagnostic:
                    summary["error_category"] = f"provider_http_{code}"
                    break
            events = store.events(limit=1000)
            wrote = (
                target.exists()
                and target.read_text(encoding="utf-8").strip()
                == "SENTINEL_LIVE_ACCEPTANCE"
            )
            terminal = any(
                e.get("tool_name") == "terminal"
                and e["event_type"] == "tool_execution_completed"
                for e in events
            )
            checkpoints = Recovery(store, workspace).checkpoints()
            summary.update(
                model=os.environ["SENTINEL_TEST_MODEL"],
                model_returned=isinstance(result, dict),
                terminal_observed=terminal,
                actual_file_written=wrote,
                event_count=len(events),
                checkpoint_count=len(checkpoints),
            )
            if isinstance(result, dict):
                for field in ("api_calls", "api_call_count", "total_tokens"):
                    if isinstance(result.get(field), (int, float)):
                        summary[field] = result[field]
            if wrote and checkpoints:
                Recovery(store, workspace).restore(
                    checkpoints[0]["id"], authorized=True
                )
                summary["new_file_restored_to_absence"] = not target.exists()
            summary["passed"] = (
                wrote and terminal and bool(summary.get("new_file_restored_to_absence"))
            )
        except Exception as error:
            # Never emit exception text: SDK errors may contain request metadata.
            summary.update(passed=False, error_type=type(error).__name__)
    (Path(root) / "live-acceptance.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))


def run_live(output=None, model_override=None):
    import yaml
    from dotenv import dotenv_values

    primary = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    config = yaml.safe_load((primary / "config.yaml").read_text(encoding="utf-8")) or {}
    model = config.get("model", {})
    if not isinstance(model, dict) or model.get("provider") != "openrouter":
        raise RuntimeError(
            "This harness supports only an already configured OpenRouter provider"
        )
    name = model.get("default") or model.get("model")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError("No configured model name is available")
    if model_override:
        if model_override not in {name, "openrouter/free"}:
            raise RuntimeError(
                "Only the configured model or explicitly approved openrouter/free is supported"
            )
        name = model_override
    base = model.get("base_url")
    if base and str(base).rstrip("/") != "https://openrouter.ai/api/v1":
        raise RuntimeError(
            "Custom provider endpoints are not authorized by this harness"
        )
    key = dotenv_values(primary / ".env").get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Configured OpenRouter key is unavailable")
    repo = Path(__file__).resolve().parents[1]
    root = (
        Path(output).resolve()
        if output
        else Path(tempfile.mkdtemp(prefix="sentinel-live-parent-")) / "acceptance"
    )
    root.mkdir(parents=True, exist_ok=False)
    (root / "workspace").mkdir()
    home = root / "profile"
    plugin = home / "plugins" / "sentinel"
    plugin.mkdir(parents=True)
    for filename in ("__init__.py", "plugin.yaml"):
        shutil.copy2(repo / filename, plugin / filename)
    shutil.copytree(
        repo / "sentinel",
        plugin / "sentinel",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    budget = home / "plugins" / "sentinel-budget"
    budget.mkdir()
    (budget / "plugin.yaml").write_text(
        "name: sentinel-budget\nversion: '1.0'\ndescription: Disposable acceptance request counter and five-request limit\nprovides_hooks:\n  - pre_api_request\n",
        encoding="utf-8",
    )
    (budget / "__init__.py").write_text(
        "import json,os\nfrom pathlib import Path\n"
        "def register(ctx):\n"
        "    count = 0\n"
        "    def observe(**kwargs):\n"
        "        nonlocal count\n"
        "        path = Path(os.environ['SENTINEL_HOME']).parent / 'request-count.json'\n"
        "        if count >= 5:\n"
        "            path.write_text(json.dumps({'api_request_attempts':count,'budget_exhausted':True}))\n"
        "            raise SystemExit(73)\n"
        "        count += 1\n"
        "        path.write_text(json.dumps({'api_request_attempts':count,'budget_exhausted':False}))\n"
        "    ctx.register_hook('pre_api_request', observe)\n",
        encoding="utf-8",
    )
    (home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "plugins": {"enabled": ["sentinel", "sentinel-budget"]},
                "model": {"provider": "openrouter", "default": name},
                "agent": {"api_max_retries": 1},
                "approvals": {"mode": "manual"},
                "terminal": {"backend": "local"},
            }
        ),
        encoding="utf-8",
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HERMES_", "SENTINEL_"))
        and not any(
            p in k.upper()
            for p in ("API_KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL")
        )
    }
    env.update(
        HERMES_HOME=str(home),
        SENTINEL_HOME=str(root / "state"),
        SENTINEL_TEST_MODEL=name,
        OPENROUTER_API_KEY=key,
        TERMINAL_ENV="local",
        TERMINAL_CWD=str(root / "workspace"),
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=str(plugin),
    )
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(root)],
        cwd=root / "workspace",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    # Host output and SDK diagnostics are intentionally not printed.
    if result.returncode:
        return {
            "passed": False,
            "error_type": "WorkerProcessFailure",
            "exit_code": result.returncode,
            "evidence_root": str(root),
        }
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    if (root / "request-count.json").exists():
        summary.update(
            json.loads((root / "request-count.json").read_text(encoding="utf-8"))
        )
    if any(key.encode() in p.read_bytes() for p in root.rglob("*") if p.is_file()):
        summary["credential_artifact_scan"] = "failed"
    else:
        summary["credential_artifact_scan"] = "passed"
    summary["evidence_root"] = str(root)
    (root / "live-acceptance.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    parser.add_argument(
        "--model", help="Configured model or explicitly approved openrouter/free"
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.worker:
        worker(options.worker)
    else:
        print(json.dumps(run_live(options.output, options.model), indent=2))
