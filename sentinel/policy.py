"""Deterministic hook-level policy, not an operating-system sandbox.

Unknown shell execution is escalated rather than presumed safe. Filesystem
checks resolve existing symbolic links, but cannot eliminate TOCTOU races.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit


def approval_key(tool_name: str, args: dict, identity: dict) -> str:
    """Bind native approval grants to the full operation and its identity."""
    payload = json.dumps(
        {"tool": tool_name, "args": args, "identity": identity},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "sentinel:" + hashlib.sha256(payload.encode()).hexdigest()


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _url_hosts(value):
    """Canonical HTTP hostnames, without trusting URL spelling variations."""
    hosts = set()
    for text in _strings(value):
        for url in re.findall(r"https?://[^\s'\"<>]+", text, re.IGNORECASE):
            host = urlsplit(url).hostname
            if not host:
                raise ValueError("URL has no hostname")
            host = unquote(host).rstrip(".").encode("idna").decode("ascii").lower()
            if not host or any(char in host for char in "/\\@%\x00\r\n\t "):
                raise ValueError("URL hostname is malformed")
            hosts.add(host)
    return hosts


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve(value: str, cwd: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else cwd / path).resolve()


_PATH_KEYS = {
    "path",
    "file_path",
    "filepath",
    "target_path",
    "directory",
    "cwd",
    "destination",
    "source",
    "paths",
}


def _path_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PATH_KEYS and not isinstance(item, dict):
                yield from (
                    p
                    for p in _strings(item)
                    if not p.startswith(("https://", "http://"))
                )
            elif isinstance(item, (dict, list)):
                yield from _path_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _path_values(item)


def _safe_segment(segment):
    """Return safety and explicit operands for a deliberately small grammar.

    Do not strip executable directories: /tmp/git is not the trusted PATH git.
    Unknown flags cannot inherit the safety of a familiar command name.
    """
    name, operands = segment[0].lower(), segment[1:]
    if name in {"pwd", "get-location", "whoami"}:
        return not operands, []
    if name in {"echo", "write-output"}:
        return True, []
    if name in {"ls", "dir", "get-childitem"}:
        paths = []
        positional = False
        flags = {
            "-a",
            "-l",
            "-la",
            "-al",
            "-h",
            "-lh",
            "-hl",
            "-lah",
            "-alh",
            "--all",
            "--long",
            "-force",
            "-name",
        }
        for operand in operands:
            if name == "dir" and operand.startswith("/"):
                return False, []
            if operand == "--" and not positional:
                positional = True
            elif operand.startswith("-") and not positional:
                if operand.lower() not in flags:
                    return False, []
            elif any(char in operand for char in "*?[]"):
                return False, []
            else:
                paths.append(operand)
        return True, paths
    if name == "git" and operands:
        subcommand, options = operands[0], operands[1:]
        if subcommand == "status":
            return all(
                option
                in {
                    "--short",
                    "-s",
                    "--porcelain",
                    "--porcelain=v1",
                    "--porcelain=v2",
                    "--branch",
                    "-b",
                    "--untracked-files=no",
                }
                for option in options
            ), []
        if subcommand == "branch":
            return all(
                option in {"--list", "--show-current", "-a", "--all"}
                for option in options
            ), []
        if subcommand == "rev-parse":
            return bool(options) and all(
                option
                in {
                    "HEAD",
                    "--show-toplevel",
                    "--is-inside-work-tree",
                    "--show-prefix",
                    "--verify",
                }
                for option in options
            ), []
        if subcommand in {"diff", "show"}:
            safe_flags = {
                "--no-ext-diff",
                "--no-textconv",
                "--stat",
                "--numstat",
                "--name-only",
                "--name-status",
                "--shortstat",
                "--check",
                "--",
                "HEAD",
            }
            return "--no-ext-diff" in options and "--no-textconv" in options and all(
                option in safe_flags for option in options
            ), []
    return False, []


def _secret(value: str) -> bool:
    return bool(
        re.search(
            r"(?:^|[\\/\s'\"])(?:\.env(?:[.][\w-]+)?|\.ssh|\.aws|\.gnupg|"
            r"credentials(?:[.][\w-]+)?|id_rsa|id_ed25519|secrets?(?:[.][\w-]+)?)(?:$|[\\/:\s'\"]|[.]*(?:$|[\\/\s'\"]))",
            value,
            re.IGNORECASE,
        )
    )


def _result(decision, rule, reason, risk, tool_name, args, identity):
    return {
        "decision": decision,
        "rule": rule,
        "reason": reason,
        "risk": risk,
        "approval_key": approval_key(tool_name, args, identity),
    }


def evaluate(
    tool_name: str, args: dict, identity: dict, mission: dict | None = None
) -> dict:
    """Evaluate mandatory protections before narrower mission permissions.

    Mission fields: status, expires_at (ISO-8601), allowed_directories,
    restricted_directories, approved_tools, restricted_tools, allowed_domains,
    allow_deployment. Empty allowed_domains denies network access.
    """

    def decide(decision, rule, reason, risk="low"):
        return _result(decision, rule, reason, risk, tool_name, args, identity)

    if (
        not isinstance(tool_name, str)
        or not tool_name
        or not isinstance(args, dict)
        or not isinstance(identity, dict)
    ):
        # Reject malformed runtime calls without attempting to hash them.
        return {
            "decision": "BLOCK",
            "rule": "invalid-operation",
            "reason": "Arguments and identity must be objects.",
            "risk": "high",
        }
    values = list(_strings(args))
    if any(_secret(value) for value in values):
        return decide(
            "BLOCK",
            "protected-secrets",
            "Access to secret-related paths is prohibited.",
            "critical",
        )
    try:
        cwd = (
            Path(args.get("cwd", identity.get("cwd", Path.cwd())))
            .expanduser()
            .resolve()
        )
        operation_paths = [_resolve(p, cwd) for p in _path_values(args)]
        protected = [
            _resolve(p, cwd) for p in identity.get("protected_directories", [])
        ]
        for path in operation_paths:
            if _secret(str(path)):
                return decide(
                    "BLOCK",
                    "protected-secrets",
                    "The resolved path accesses protected secret material.",
                    "critical",
                )
            if any(_within(path, root) or _within(root, path) for root in protected):
                return decide(
                    "BLOCK",
                    "protected-control-plane",
                    "Sentinel runtime and authorization storage are protected from tool access.",
                    "critical",
                )
    except (ValueError, OSError, RuntimeError, TypeError):
        return decide(
            "BLOCK",
            "invalid-path",
            "A filesystem path could not be safely resolved.",
            "high",
        )
    command = args.get("command", args.get("cmd", ""))
    if "command" in args and "cmd" in args and args["command"] != args["cmd"]:
        return decide(
            "BLOCK",
            "ambiguous-command",
            "Conflicting command aliases cannot be safely classified.",
            "high",
        )
    if not isinstance(command, str):
        return decide("BLOCK", "invalid-command", "Command must be a string.", "high")
    segments = []
    if command:
        try:
            lexer = shlex.shlex(
                command.replace("\r\n", ";").replace("\n", ";").replace("\r", ";"),
                posix=True,
                punctuation_chars=";&|()<>",
            )
            lexer.whitespace_split = True
            lexer.commenters = ""
            tokens = list(lexer)
        except ValueError:
            return decide(
                "BLOCK",
                "invalid-command",
                "Command quoting could not be parsed.",
                "high",
            )
        current = []
        for token in tokens + [";"]:
            if token and all(char in ";&|()<>" for char in token):
                if current:
                    segments.append(current)
                    current = []
            else:
                current.append(token)
        for segment in segments:
            name = (
                segment[0]
                .replace("\\", "/")
                .rsplit("/", 1)[-1]
                .lower()
                .removesuffix(".exe")
            )
            lower = [part.lower() for part in segment]
            if name.split(".", 1)[0] in {
                "rm",
                "rmdir",
                "rd",
                "del",
                "erase",
                "remove-item",
                "ri",
                "clear-content",
                "format",
                "mkfs",
                "diskpart",
                "shred",
            }:
                return decide(
                    "BLOCK",
                    "destructive-command",
                    "Destructive filesystem commands require a separately isolated workflow.",
                    "critical",
                )
            if name == "git" and (
                ("reset" in lower and "--hard" in lower)
                or (
                    "clean" in lower
                    and any(x.startswith("-") and "f" in x for x in lower)
                )
            ):
                return decide(
                    "BLOCK",
                    "destructive-git",
                    "This Git operation can discard uncommitted work.",
                    "high",
                )
            if name in {
                "sudo",
                "su",
                "doas",
                "runas",
                "chmod",
                "chown",
                "icacls",
                "takeown",
            }:
                return decide(
                    "BLOCK",
                    "privilege-change",
                    "Privilege and permission changes are prohibited.",
                    "critical",
                )
            if name in {"set-item", "remove-variable"} and any(
                "sentinel" in x or "hermes_safe_mode" in x for x in lower
            ):
                return decide(
                    "BLOCK",
                    "protection-bypass",
                    "Runtime protection configuration cannot be changed by tools.",
                    "critical",
                )
        # POSIX tokenization cannot establish Windows cmd/PowerShell quoting
        # or expansion semantics. Such syntax is never auto-allowed.
        ambiguous_shell = bool(
            re.search(r"[\\^%!`$<>]|[\x00-\x08\x0b\x0c\x0e-\x1f]", command)
        )
        try:
            for segment in segments:
                safe, operands = _safe_segment(segment)
                if safe:
                    operation_paths.extend(_resolve(path, cwd) for path in operands)
            for path in operation_paths:
                if _secret(str(path)):
                    return decide(
                        "BLOCK",
                        "protected-secrets",
                        "The resolved shell operand accesses protected secret material.",
                        "critical",
                    )
                if any(
                    _within(path, root) or _within(root, path) for root in protected
                ):
                    return decide(
                        "BLOCK",
                        "protected-control-plane",
                        "A shell operand accesses Sentinel runtime or authorization storage.",
                        "critical",
                    )
        except (ValueError, OSError, RuntimeError, TypeError):
            return decide(
                "BLOCK",
                "invalid-path",
                "A shell path could not be safely resolved.",
                "high",
            )
    if mission:
        if mission.get("status", "DRAFT") != "ACTIVE":
            return decide(
                "BLOCK",
                "mission-inactive",
                "The associated mission is not active.",
                "high",
            )
        expiry = mission.get("expires_at", mission.get("expiration"))
        if expiry:
            try:
                parsed = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("Timezone required")
                expired = parsed <= datetime.now(timezone.utc)
            except ValueError:
                return decide(
                    "BLOCK",
                    "mission-invalid-expiry",
                    "Mission expiry must be an ISO-8601 timestamp with timezone.",
                    "high",
                )
            if expired:
                return decide(
                    "BLOCK", "mission-expired", "The mission has expired.", "high"
                )
        if tool_name in mission.get("restricted_tools", []):
            return decide(
                "BLOCK",
                "mission-tool-deny",
                "This tool is restricted by the mission.",
                "high",
            )
        approved = mission.get("approved_tools")
        if approved is not None and tool_name not in approved:
            return decide(
                "BLOCK",
                "mission-tool-scope",
                "This tool is outside the mission allowlist.",
                "high",
            )
        try:
            roots = [_resolve(p, cwd) for p in mission.get("allowed_directories", [])]
            restricted = [
                _resolve(p, cwd) for p in mission.get("restricted_directories", [])
            ]
            paths = [cwd] if command else []
            paths.extend(operation_paths)
            if command and (roots or restricted):
                if ambiguous_shell:
                    return decide(
                        "BLOCK",
                        "mission-shell-unconfined",
                        "Shell expansion or platform-specific syntax cannot be confined by this hook.",
                        "high",
                    )
                for segment in segments:
                    # A shell is not confined by cwd. Only inspect a tiny,
                    # explicit set of read-only commands inside scoped missions.
                    safe, _ = _safe_segment(segment)
                    if safe and segment[0].lower() not in {"echo", "write-output"}:
                        continue
                    return decide(
                        "BLOCK",
                        "mission-shell-unconfined",
                        "This shell operation cannot be confined to the mission directories by a hook. Use a structured file tool or an isolated execution environment.",
                        "high",
                    )
            for path in paths:
                if any(_within(path, root) for root in restricted):
                    return decide(
                        "BLOCK",
                        "mission-directory-deny",
                        "The resolved path is in a restricted directory.",
                        "high",
                    )
                if roots and not any(_within(path, root) for root in roots):
                    return decide(
                        "BLOCK",
                        "mission-directory-scope",
                        "The resolved path is outside the mission workspace.",
                        "high",
                    )
        except (ValueError, OSError, RuntimeError, TypeError):
            return decide(
                "BLOCK",
                "invalid-path",
                "A filesystem path could not be safely resolved.",
                "high",
            )
    try:
        urls = _url_hosts(args)
    except (ValueError, UnicodeError):
        return decide(
            "BLOCK",
            "invalid-network-destination",
            "A network hostname could not be safely classified.",
            "high",
        )
    if mission and urls:
        allowed = {str(x).lower() for x in mission.get("allowed_domains", [])}
        for host in urls:
            if host not in allowed:
                return decide(
                    "BLOCK",
                    "mission-network-scope",
                    "The destination is outside the mission network allowlist.",
                    "high",
                )
    if (
        mission
        and tool_name
        in {"web_search", "web_extract", "browse", "browser", "http_request", "fetch"}
        and not urls
    ):
        return decide(
            "BLOCK",
            "mission-network-unresolved",
            "The network destination is not explicit and cannot be checked against the mission allowlist.",
            "high",
        )
    for segment in segments:
        name = (
            segment[0]
            .replace("\\", "/")
            .rsplit("/", 1)[-1]
            .lower()
            .removesuffix(".exe")
        )
        lower = [part.lower() for part in segment]
        if name in {"cast", "solana", "bitcoin-cli", "wallet", "okx", "anchor"}:
            return decide(
                "APPROVAL_REQUIRED",
                "financial-operation",
                "Blockchain and financial operations require native human approval.",
                "critical",
            )
        if name in {
            "vercel",
            "fly",
            "heroku",
            "terraform",
            "kubectl",
            "aws",
            "gcloud",
            "az",
            "wrangler",
        } or (name == "npm" and "publish" in lower):
            if mission and not mission.get("allow_deployment", False):
                return decide(
                    "BLOCK",
                    "mission-deployment-deny",
                    "Deployment and cloud changes are outside mission authority.",
                    "high",
                )
            return decide(
                "APPROVAL_REQUIRED",
                "deployment",
                "Deployment and cloud commands require native human approval.",
                "high",
            )
        if name == "git" and any(
            x in lower
            for x in {
                "push",
                "commit",
                "checkout",
                "switch",
                "rebase",
                "merge",
                "restore",
            }
        ):
            return decide(
                "APPROVAL_REQUIRED",
                "repository-change",
                "Repository mutations require native human approval.",
                "medium",
            )
        # Even normal interpreters and build scripts execute arbitrary code.
        safe, _ = _safe_segment(segment)
        if not safe or re.search(
            r"\$\(|`|\$\{|\b(?:eval|iex|invoke-expression)\b", command, re.IGNORECASE
        ):
            return decide(
                "APPROVAL_REQUIRED",
                "opaque-execution",
                "Shell execution cannot be proven safe at hook level; native human approval is required.",
                "high",
            )
    if urls:
        return decide(
            "APPROVAL_REQUIRED",
            "network-access",
            "External network access requires native human approval.",
            "medium",
        )
    if command and ambiguous_shell:
        return decide(
            "APPROVAL_REQUIRED",
            "shell-expansion",
            "Shell expansion and redirection require native human approval.",
            "high",
        )
    structured_tools = {
        "read_file",
        "write_file",
        "edit_file",
        "file_read",
        "file_write",
        "file_edit",
        "list_directory",
        "search_files",
        "search",
        "grep",
        "glob",
    }
    if tool_name not in structured_tools and tool_name != "terminal":
        return decide(
            "APPROVAL_REQUIRED",
            "unclassified-tool",
            "This tool has no verified deterministic safety classifier; native human approval is required.",
            "high",
        )
    if tool_name in structured_tools and ("command" in args or "cmd" in args):
        return decide(
            "APPROVAL_REQUIRED",
            "unexpected-command",
            "A structured file tool cannot inherit shell-command safety classification.",
            "high",
        )
    if tool_name == "terminal" and not command.strip():
        return decide(
            "APPROVAL_REQUIRED",
            "unclassified-command",
            "Terminal operation has no inspectable command.",
            "high",
        )
    if tool_name in structured_tools and not operation_paths:
        return decide(
            "APPROVAL_REQUIRED",
            "unclassified-path",
            "The structured file operation has no inspectable path; native human approval is required.",
            "high",
        )
    if tool_name in {"search_files", "search", "grep", "glob"}:
        return decide(
            "BLOCK"
            if mission
            and (
                mission.get("allowed_directories")
                or mission.get("restricted_directories")
            )
            else "APPROVAL_REQUIRED",
            "recursive-search-unclassified",
            "A recursive search can traverse secret files and symlink targets that are not explicit in its arguments. Use an explicit file read or a verified isolated search surface.",
            "high",
        )
    if mission and tool_name in mission.get("required_approvals", []):
        return decide(
            "APPROVAL_REQUIRED",
            "mission-approval",
            "The mission requires native approval for this tool.",
            "medium",
        )
    return decide(
        "ALLOW", "safe-operation", "No mandatory or mission restriction matched."
    )
