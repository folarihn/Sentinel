"""Run current official catalog checks from a separate upstream checkout.

No primary Hermes upgrade and no dependency mutation. Stage only Git-tracked
and nonignored project files, excluding local environments and runtime state.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def sanitize_output(text, roots):
    """Replace known local prefixes even when a console wraps them mid-path.

    This changes display locations only. It never drops checks, decisions,
    warnings or exception types from the official validator's output.
    """
    for root, label in sorted(roots, key=lambda item: len(str(item[0])), reverse=True):
        pieces = []
        for character in str(root):
            if character in "\\/":
                pieces.append(r"[\\/]+[ \t\r\n]*")
            elif character.isspace():
                pieces.append(r"\s+")
            else:
                pieces.append(re.escape(character) + r"[ \t\r\n]*")
        if pieces:
            text = re.sub("".join(pieces), lambda _: label, text, flags=re.I)
    return text


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(".private-evidence/catalog-validation.json")
    )
    args = parser.parse_args()
    source = args.host_source.resolve()
    repo = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=repo,
        )
        .decode()
        .split("\0")
    )
    report = {
        "upstream_sha": revision,
        "primary_installation_modified": False,
        "path_redaction": "Known local path prefixes replaced; official decisions and warnings retained",
        "checks": [],
    }
    with tempfile.TemporaryDirectory(prefix="sentinel-catalog-") as folder:
        staged = Path(folder) / "sentinel"
        staged.mkdir()
        for name in names:
            if name and (repo / name).is_file():
                dest = staged / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo / name, dest)
        env = os.environ.copy()
        env.update(
            PYTHONPATH=str(source),
            HERMES_HOME=str(Path(folder) / "profile"),
            PYTHONIOENCODING="utf-8",
        )
        env.pop("SENTINEL_HOME", None)
        roots = [
            (staged, "<plugin>"),
            (folder, "<temporary>"),
            (source, "<validator>"),
            (repo, "<repository>"),
            (Path.home(), "<home>"),
        ]
        for command in (
            ["doctor", str(staged), "--ci"],
            ["validate", str(staged), "--json"],
        ):
            result = subprocess.run(
                [sys.executable, "-m", "hermes_cli.main", "plugins", *command],
                cwd=folder,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            entry = {
                "command": "hermes plugins " + command[0],
                "exit_code": result.returncode,
                "stdout": sanitize_output(result.stdout, roots),
                "stderr": sanitize_output(result.stderr, roots),
            }
            report["checks"].append(entry)
            print(json.dumps(entry, indent=2))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(any(c["exit_code"] != 0 for c in report["checks"]))


if __name__ == "__main__":
    main()
