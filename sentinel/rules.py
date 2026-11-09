"""Validated, restrictive-only operator policy configuration."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import tempfile
from pathlib import Path

from .policy import _path_values, _resolve, _url_hosts, _within, approval_key


class PolicyValidationError(ValueError):
    """Configuration cannot be safely activated."""


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyValidationError(
                f"policies.json contains duplicate key '{key}'."
            )
        result[key] = value
    return result


def validate(document: dict) -> dict:
    """Return a normalized, detached policy document or an actionable error."""
    if not isinstance(document, dict) or set(document) != {"rules"}:
        raise PolicyValidationError(
            "Policy document must contain only a 'rules' array."
        )
    rules = document["rules"]
    if not isinstance(rules, list) or len(rules) > 500:
        raise PolicyValidationError(
            "rules must be an array containing at most 500 rules."
        )
    normalized = []
    ids = set()
    required = {"id", "priority", "enabled", "tools", "decision", "reason"}
    optional = {"session_id", "agent_id", "domains", "path_roots"}
    for index, rule in enumerate(rules):
        prefix = f"Rule {index + 1}"
        if (
            not isinstance(rule, dict)
            or not required.issubset(rule)
            or set(rule) - required - optional
        ):
            raise PolicyValidationError(
                f"{prefix}: expected fields {', '.join(sorted(required))}; optional {', '.join(sorted(optional))}."
            )
        identifier = rule["id"]
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", identifier
        ):
            raise PolicyValidationError(
                f"{prefix}: id must be a 1 to 80 character identifier using letters, numbers, '.', '_' or '-'."
            )
        if identifier in ids:
            raise PolicyValidationError(f"{prefix}: duplicate id '{identifier}'.")
        ids.add(identifier)
        if type(rule["priority"]) is not int or not 0 <= rule["priority"] <= 100000:
            raise PolicyValidationError(
                f"{identifier}: priority must be an integer from 0 to 100000."
            )
        if type(rule["enabled"]) is not bool:
            raise PolicyValidationError(f"{identifier}: enabled must be true or false.")
        if not isinstance(rule["decision"], str) or rule["decision"] not in {
            "BLOCK",
            "APPROVAL_REQUIRED",
        }:
            raise PolicyValidationError(
                f"{identifier}: decision must be BLOCK or APPROVAL_REQUIRED; mandatory protections cannot be overridden."
            )
        if (
            not isinstance(rule["reason"], str)
            or not rule["reason"].strip()
            or len(rule["reason"]) > 1000
        ):
            raise PolicyValidationError(
                f"{identifier}: reason must be a nonempty string of at most 1000 characters."
            )
        for field in ("tools", "domains", "path_roots"):
            if field not in rule:
                continue
            value = rule[field]
            if (
                not isinstance(value, list)
                or not value
                or len(value) > 100
                or any(
                    not isinstance(x, str) or not x.strip() or len(x) > 4096
                    for x in value
                )
            ):
                raise PolicyValidationError(
                    f"{identifier}: {field} must contain 1 to 100 nonempty strings."
                )
        for field in ("session_id", "agent_id"):
            if field in rule and (
                not isinstance(rule[field], str)
                or not rule[field].strip()
                or len(rule[field]) > 500
            ):
                raise PolicyValidationError(
                    f"{identifier}: {field} must be a nonempty string of at most 500 characters."
                )
        for domain in rule.get("domains", []):
            if (
                not re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", domain
                )
                or ".." in domain
            ):
                raise PolicyValidationError(
                    f"{identifier}: domains must be exact hostnames without scheme, path, port, or wildcard."
                )
        for root in rule.get("path_roots", []):
            if not Path(root).expanduser().is_absolute():
                raise PolicyValidationError(
                    f"{identifier}: path_roots must be absolute filesystem paths."
                )
        item = dict(rule)
        item["tools"] = list(rule["tools"])
        if "domains" in item:
            item["domains"] = [x.lower() for x in rule["domains"]]
        if "path_roots" in item:
            item["path_roots"] = [
                str(Path(x).expanduser().resolve()) for x in rule["path_roots"]
            ]
        normalized.append(item)
    return {
        "rules": sorted(normalized, key=lambda item: (-item["priority"], item["id"]))
    }


class RuleSet:
    """Atomic on-disk configuration, reloaded for each evaluation.

    A missing initial file means no additional operator restrictions. A
    present malformed file raises; callers must block on that exception.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "policies.json"

    def load(self) -> dict:
        if self.path.is_symlink():
            raise PolicyValidationError("policies.json must not be a symbolic link.")
        if not self.path.exists():
            return {"rules": []}
        if self.path.stat().st_size > 1024 * 1024:
            raise PolicyValidationError("policies.json exceeds the 1 MiB size limit.")
        try:
            return validate(
                json.loads(
                    self.path.read_text(encoding="utf-8"),
                    object_pairs_hook=_unique_keys,
                )
            )
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise PolicyValidationError(
                f"policies.json is not valid UTF-8 JSON: {exc}"
            ) from exc

    def save(self, document: dict) -> dict:
        normalized = validate(document)
        encoded = (json.dumps(normalized, indent=2, ensure_ascii=True) + "\n").encode()
        if len(encoded) > 1024 * 1024:
            raise PolicyValidationError("Policy document exceeds the 1 MiB size limit.")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise PolicyValidationError("policies.json must not be a symbolic link.")
        descriptor, filename = tempfile.mkstemp(
            prefix=".policies-", suffix=".json", dir=self.root
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.path)
        finally:
            Path(filename).unlink(missing_ok=True)
        return normalized

    def evaluate(self, tool: str, args: dict, identity: dict) -> dict | None:
        rules = self.load()["rules"]
        matches = []
        for rule in rules:
            if not rule["enabled"] or not any(
                fnmatch.fnmatchcase(tool, pattern) for pattern in rule["tools"]
            ):
                continue
            if any(
                rule.get(field) is not None and rule[field] != identity.get(field)
                for field in ("session_id", "agent_id")
            ):
                continue
            if "domains" in rule:
                try:
                    hosts = _url_hosts(args)
                except (ValueError, UnicodeError) as exc:
                    raise PolicyValidationError(
                        "Operation contains a malformed URL."
                    ) from exc
                if not hosts.intersection(rule["domains"]):
                    continue
            if "path_roots" in rule:
                cwd = Path(args.get("cwd", identity.get("cwd", Path.cwd()))).resolve()
                paths = [_resolve(value, cwd) for value in _path_values(args)]
                if not any(
                    _within(path, Path(root))
                    for path in paths
                    for root in rule["path_roots"]
                ):
                    continue
            matches.append(rule)
        if not matches:
            return None
        # BLOCK is stronger than escalation, independent of operator priority.
        rule = next(
            (item for item in matches if item["decision"] == "BLOCK"), matches[0]
        )
        return {
            "decision": rule["decision"],
            "rule": "operator:" + rule["id"],
            "reason": rule["reason"],
            "risk": "high" if rule["decision"] == "BLOCK" else "medium",
            "approval_key": approval_key(tool, args, identity),
        }
