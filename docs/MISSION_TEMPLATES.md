# Mission templates

`sentinel.templates.mission_template(key, workspace, session_id)` returns a DRAFT mission with an explicit workspace directory. Activate it through Mission Control after choosing the exact session and network destinations. Templates contain policy fields consumed by the same engine as manually created missions; none bypasses mandatory protections.

- Safe Coding: local terminal and file development, no permitted network domains.
- Repository Maintenance: local maintenance and github.com destination permission.
- Research: file reads and web research tools; no terminal or file mutation.
- Deployment Investigation: terminal and read tools; deployment execution is outside mission authority.
- Local File Organization: file tools only, no terminal or web tools.
- Experimental Agent: local experimentation in an explicitly selected disposable workspace.
- Restricted Automation: file inspection tools only.

Tool identifiers are the verified core Hermes names. Runtime-specific or plugin tools must be explicitly added by the operator. Empty destination lists deny explicit URLs. Shell programs and scripts can conceal destinations and effects: scoped missions block unconfined shell operations, and these templates provide hook-level authority rather than operating-system isolation. All templates deny direct secret-path access and destructive commands through mandatory Guard rules. The `allow_deployment=False` field blocks recognized deployment commands; it does not promise an absolute deployment sandbox.

Expired missions remain associated with their sessions so expiry blocks execution instead of silently returning the session to unrestricted defaults. Paused missions also block execution. Unknown storage schema versions are rejected instead of guessed or rewritten.
