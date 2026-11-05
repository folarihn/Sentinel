"""Exercise the official installer in a disposable, credential-free profile."""

import json
import argparse
import os
import subprocess
import sys
import tempfile


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-sha",
        help="Require the installed remote commit to match this release",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sentinel-install-") as folder:
        env = os.environ.copy()
        for key in list(env):
            if key.startswith(("HERMES_", "SENTINEL_")):
                del env[key]
        env.update(HERMES_HOME=folder, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hermes_cli.main",
                "plugins",
                "install",
                "https://github.com/folarihn/Sentinel.git",
                "--enable",
            ],
            env=env,
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        print(result.stdout)
        if result.returncode:
            print(result.stderr)
            raise SystemExit(result.returncode)
        if args.expected_sha:
            from pathlib import Path

            installed = Path(folder) / "plugins" / "sentinel"
            actual = subprocess.check_output(
                ["git", "-C", str(installed), "rev-parse", "HEAD"], text=True
            ).strip()
            if actual != args.expected_sha:
                raise RuntimeError(
                    "Installed revision differs from the requested release commit"
                )
            print(json.dumps({"installed_sha": actual, "release_pin_matched": True}))
        script = "from hermes_cli.plugins import discover_plugins,get_plugin_manager; import json; discover_plugins(force=True); p=next(p for p in get_plugin_manager().list_plugins() if p['name']=='sentinel'); assert p['enabled'] and not p['error'],p; print(json.dumps(p))"
        checked = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if checked.returncode:
            print(checked.stderr)
            raise SystemExit(checked.returncode)
        print(checked.stdout)
        print(
            json.dumps(
                {
                    "official_install": "passed",
                    "profile": "temporary; removed on exit",
                    "personal_profile_modified": False,
                }
            )
        )


if __name__ == "__main__":
    main()
