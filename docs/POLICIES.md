# Operator policies

Mandatory Guard protections run before operator policies. Operator rules can
only add BLOCK or APPROVAL_REQUIRED restrictions. There is no ALLOW override.

The local configuration is `$SENTINEL_HOME/policies.json`, under the protected
Sentinel state directory. Missing initial configuration means no extra operator
rules. Malformed present configuration raises an actionable validation error;
the runtime must fail closed rather than silently discard it.

```json
{
  "rules": [
    {
      "id": "review-file-writes",
      "priority": 100,
      "enabled": true,
      "tools": ["write_*", "edit_file"],
      "decision": "APPROVAL_REQUIRED",
      "reason": "Review file mutations before execution"
    }
  ]
}
```

Every rule requires the six fields shown above. Optional `session_id` and
`agent_id` match exact host identity values. Optional `domains` is a nonempty
list of exact hostnames, excluding URL schemes, ports, paths and wildcards.
Optional `path_roots` is a nonempty list of absolute filesystem directories;
paths are resolved before comparison. All provided conditions must match.
Multiple values within tools, domains, or path_roots are alternatives. Tool
patterns use case-sensitive shell-style glob matching.

Rules are ordered by descending priority and then identifier. Among matching
rules, BLOCK always wins over APPROVAL_REQUIRED. The highest-priority rule
within that outcome supplies the explanation. Disabled rules have no effect.

The matcher inspects structured path arguments and explicit HTTP(S) URL
arguments. It does not decode arbitrary scripts, infer destinations from
runtime variables, or provide operating-system isolation. Mandatory Guard
handling escalates opaque shell execution independently.

`RuleSet(root).load()` and `.save(document)` return the normalized `{rules: []}`
document. `.evaluate(tool, args, identity)` reloads current configuration and
returns a decision dictionary or None. Saves validate before replacing the
file, flush and fsync a temporary file, and atomically replace the destination.
Concurrent valid updates use last-writer-wins semantics; no stale revision
merge is implied. Runtime code must protect this state path from agent tools.
