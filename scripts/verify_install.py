"""Exercise the official installer in a disposable, credential-free profile."""

import json
import os
import subprocess
import sys
import tempfile


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
